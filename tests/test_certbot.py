from __future__ import annotations

import os

from vpnforge.services.certbot import sync_xray_certificate, xray_certificate_path
from vpnforge.services.hysteria import (
    hysteria_certificate_path,
    sync_hysteria_certificate,
)
from vpnforge.services.xray import XRAY_RUNTIME_GID, XRAY_RUNTIME_UID


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


from datetime import datetime, timedelta, timezone

from vpnforge.checks import certificate_renewal_checks
from vpnforge.config import create_settings, ensure_directories, write_settings
from vpnforge.services.certbot import renew_certificate
from vpnforge.state import load_state, update_state


class FakeRenewDocker:
    def __init__(self, live, *, new_certificate=None, running=("nginx", "xray", "hysteria")):
        self.live = live
        self.new_certificate = new_certificate
        self.running = set(running)
        self.events = []

    def is_running(self, service):
        return service in self.running

    def run(self, *arguments):
        self.events.append(("run", *arguments))
        if self.new_certificate and "--dry-run" not in arguments:
            (self.live / "fullchain.pem").write_text(self.new_certificate, encoding="utf-8")

    def exec(self, service, *command):
        self.events.append(("exec", service, *command))

    def restart(self, service):
        self.events.append(("restart", service))


def _installed(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com"))
    live = paths.certbot_conf_dir / "live" / "vpn.example.com"
    live.mkdir(parents=True)
    (live / "fullchain.pem").write_text("old-certificate\n", encoding="utf-8")
    (live / "privkey.pem").write_text("private-key\n", encoding="utf-8")
    sync_xray_certificate(paths, "vpn.example.com")
    sync_hysteria_certificate(paths, "vpn.example.com")
    return live


def test_renew_deploys_new_certificate_and_reloads_services(paths):
    live = _installed(paths)
    docker = FakeRenewDocker(live, new_certificate="new-certificate\n")

    assert renew_certificate(paths, docker) is True

    run = docker.events[0]
    assert run[:5] == ("run", "run", "--rm", "certbot", "renew")
    assert "--webroot" in run
    assert docker.events[1:] == [
        ("exec", "nginx", "nginx", "-s", "reload"),
        ("restart", "xray"),
        ("restart", "hysteria"),
    ]
    for fullchain, _ in (xray_certificate_path(paths), hysteria_certificate_path(paths)):
        assert fullchain.read_text(encoding="utf-8") == "new-certificate\n"
    state = load_state(paths)
    assert state["certificate_renew_checked_at"]
    assert state["certificate_deployed_at"]


def test_renew_without_new_certificate_does_not_restart(paths):
    live = _installed(paths)
    docker = FakeRenewDocker(live)

    assert renew_certificate(paths, docker) is False

    assert [event[0] for event in docker.events] == ["run"]
    assert "certificate_deployed_at" not in load_state(paths)


def test_renew_refreshes_stale_copies(paths):
    live = _installed(paths)
    (live / "fullchain.pem").write_text("renewed-earlier\n", encoding="utf-8")
    docker = FakeRenewDocker(live, running=("nginx",))

    assert renew_certificate(paths, docker) is True

    assert docker.events[1:] == [("exec", "nginx", "nginx", "-s", "reload")]
    assert xray_certificate_path(paths)[0].read_text(encoding="utf-8") == "renewed-earlier\n"


def test_renew_dry_run_skips_deploy(paths):
    live = _installed(paths)
    docker = FakeRenewDocker(live, new_certificate="new-certificate\n")

    assert renew_certificate(paths, docker, dry_run=True) is False

    assert "--dry-run" in docker.events[0]
    assert len(docker.events) == 1


def test_renewal_checks_report_last_run(paths):
    _installed(paths)
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)

    checks = certificate_renewal_checks(paths, "vpn.example.com", now=now)
    assert checks[-1].status == "WARN"
    assert "has not run yet" in checks[-1].message

    update_state(paths, certificate_renew_checked_at=(now - timedelta(hours=5)).isoformat())
    assert certificate_renewal_checks(paths, "vpn.example.com", now=now)[-1].status == "OK"

    update_state(paths, certificate_renew_checked_at=(now - timedelta(days=5)).isoformat())
    assert certificate_renewal_checks(paths, "vpn.example.com", now=now)[-1].status == "WARN"
