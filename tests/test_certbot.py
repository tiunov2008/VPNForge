from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from vpnforge.config import (
    create_settings,
    ensure_directories,
    write_settings,
)
from vpnforge.services.certbot import (
    certificate_days_remaining,
    certificate_expiry,
    configure_renewal,
    renew_certificate,
    renewal_cron_path,
    sync_xray_certificate,
    xray_certificate_path,
)
from vpnforge.services.hysteria import (
    hysteria_certificate_path,
    sync_hysteria_certificate,
)
from vpnforge.services.xray import XRAY_RUNTIME_GID, XRAY_RUNTIME_UID
from vpnforge.shell import CommandResult
from vpnforge.state import load_state


def test_sync_xray_certificate_copies_files_with_runtime_permissions(paths):
    live = paths.certbot_conf_dir / "live" / "vpn.example.com"
    live.mkdir(parents=True)
    (live / "fullchain.pem").write_text("certificate\n", encoding="utf-8")
    (live / "privkey.pem").write_text("private-key\n", encoding="utf-8")

    sync_xray_certificate(paths, "vpn.example.com")

    fullchain, privkey = xray_certificate_path(paths)
    assert fullchain.read_text(encoding="utf-8") == "certificate\n"
    assert privkey.read_text(encoding="utf-8") == "private-key\n"

    if os.name == "posix":
        assert fullchain.stat().st_mode & 0o777 == 0o600
        assert privkey.stat().st_mode & 0o777 == 0o600
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            assert fullchain.stat().st_uid == XRAY_RUNTIME_UID
            assert privkey.stat().st_gid == XRAY_RUNTIME_GID


def test_sync_hysteria_certificate_copies_private_runtime_files(paths):
    live = paths.certbot_conf_dir / "live" / "vpn.example.com"
    live.mkdir(parents=True)
    (live / "fullchain.pem").write_text("certificate\n", encoding="utf-8")
    (live / "privkey.pem").write_text("private-key\n", encoding="utf-8")

    sync_hysteria_certificate(paths, "vpn.example.com")

    fullchain, privkey = hysteria_certificate_path(paths)
    assert fullchain.read_text(encoding="utf-8") == "certificate\n"
    assert privkey.read_text(encoding="utf-8") == "private-key\n"
    if os.name == "posix":
        assert fullchain.stat().st_mode & 0o777 == 0o600
        assert privkey.stat().st_mode & 0o777 == 0o600


TEST_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIDFTCCAf2gAwIBAgIUUO5Nw+y/cQadwVKN0pfBZyrjb2UwDQYJKoZIhvcNAQEL
BQAwGjEYMBYGA1UEAwwPdnBuLmV4YW1wbGUuY29tMB4XDTI2MDkxOTEwMjE0NFoX
DTQ2MDQwMjEwMjE0NFowGjEYMBYGA1UEAwwPdnBuLmV4YW1wbGUuY29tMIIBIjAN
BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtZc133HDB5iOR/3auqdzKEpYjavj
REA7ugJH9bjDgS69CtIIA3WtA5yAGz9ikaMpQYivJvBKmHp/m3XwIIuGgi/TrBze
t8KOepmfsy7a76LRF+61a1Y2vP298snJI4+XJag1QvHy3SxTgVSc27nKtGXsOx81
9JogEf4Z6ytjEfmz3DYSD/xSw8HfeAF/Lmzqsdc2gA/0TLuJAK0T6xzsnA5AFfmp
eO119ni8Hh8GFe0t/mnsFWYnQRxLYst76pGAumdBLH3ZvONXub5WAq/LVFnuO82s
OaxuP75dgFsmOCAgoX64J+z5IlZcvL5ZWC1UN1Cokxu3bijiLBLP4Pt5ZQIDAQAB
o1MwUTAdBgNVHQ4EFgQUJQJ7eePyxOVFpWDsv1Vcr0NAUqMwHwYDVR0jBBgwFoAU
JQJ7eePyxOVFpWDsv1Vcr0NAUqMwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0B
AQsFAAOCAQEAGlNmc8Hy8pAVP70NNn4fJ2e4pbhl5eJVNrMvi+brcLRlZANgrLOj
Z477lH8QGh3GXZEEe3YCP4fdawvPUUPq0KedQJlCsUUbsZuuKdWeK4dKYLTLj1td
XwFRz114JbEwPtiw2PVl34BiUeNuoLyK1p9cE3e9SLL8gVwewn5jd1mPPlMnDew0
X5ZUfioF1VV7NfyHlIpttI3wdEkDDFmxPmdjhOgv59o3bWrbhcl1ssbnnBUx+D1E
obQMN4zr6UNwjF375qQEPx3yryc4X0pJbpDcFcnXNy+X42oL41aEt+/esuhmLzQw
NWUIxVTy6yYOst6JYbUursIwyByLu12iDw==
-----END CERTIFICATE-----
"""


class FakeDocker:
    def __init__(self, *, nginx_running=True, on_renew=None):
        self.nginx_running = nginx_running
        self.on_renew = on_renew
        self.commands: list[tuple[str, ...]] = []
        self.restarted: list[str] = []

    def is_running(self, service, settings=None):
        return service == "nginx" and self.nginx_running

    def run(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if self.on_renew is not None:
            self.on_renew()
        return CommandResult(0)

    def restart(self, service):
        self.restarted.append(service)


def write_certificate(paths, domain="vpn.example.com", body=TEST_CERTIFICATE):
    live = paths.certbot_conf_dir / "live" / domain
    live.mkdir(parents=True, exist_ok=True)
    (live / "fullchain.pem").write_text(body, encoding="utf-8")
    (live / "privkey.pem").write_text("private-key\n", encoding="utf-8")


def test_certificate_expiry_is_parsed_without_extra_dependencies(paths):
    write_certificate(paths)

    expiry = certificate_expiry(paths, "vpn.example.com")

    assert expiry == datetime(2046, 4, 2, 10, 21, 44, tzinfo=timezone.utc)
    assert certificate_days_remaining(paths, "vpn.example.com") > 0


def test_certificate_expiry_is_none_for_unreadable_certificate(paths):
    assert certificate_expiry(paths, "vpn.example.com") is None
    write_certificate(paths, body="not a certificate\n")
    assert certificate_expiry(paths, "vpn.example.com") is None


def test_configure_renewal_writes_and_removes_cron_job(paths):
    cron_path = configure_renewal(paths)

    assert cron_path == renewal_cron_path(paths)
    content = cron_path.read_text(encoding="utf-8")
    assert "/usr/local/bin/vpnforge cert renew" in content
    if os.name == "posix":
        # Cron silently ignores group- or world-writable job files.
        assert cron_path.stat().st_mode & 0o022 == 0

    assert configure_renewal(paths, False) is None
    assert not cron_path.exists()


def test_renew_reloads_services_only_when_the_certificate_changed(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com", "admin@example.com"))
    write_certificate(paths)

    unchanged = FakeDocker()
    assert renew_certificate(paths, unchanged) is False
    assert unchanged.commands[0][:4] == ("run", "--rm", "certbot", "renew")
    assert unchanged.restarted == []

    renewed = FakeDocker(
        on_renew=lambda: write_certificate(
            paths, body=TEST_CERTIFICATE.replace("MIIDFTCCAf2", "MIIDFTCCAf3")
        )
    )
    assert renew_certificate(paths, renewed) is True
    assert renewed.restarted == ["nginx", "xray", "hysteria"]
    fullchain, _ = xray_certificate_path(paths)
    assert fullchain.is_file()
    assert load_state(paths)["certificate_renewed_at"] is not None


def test_renew_requires_running_nginx(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com", "admin@example.com"))
    write_certificate(paths)

    with pytest.raises(RuntimeError, match="Nginx must be running"):
        renew_certificate(paths, FakeDocker(nginx_running=False))


def test_renew_requires_an_existing_certificate(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com", "admin@example.com"))

    with pytest.raises(RuntimeError, match="cert issue"):
        renew_certificate(paths, FakeDocker())
