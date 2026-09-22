from __future__ import annotations

import base64
import json

import pytest

from vpnforge.dokploy import certs


def acme_payload(domain: str, fullchain: str, privkey: str, *, sans=None) -> dict:
    return {
        "letsencrypt": {
            "Account": {"Email": "admin@example.com"},
            "Certificates": [
                {
                    "domain": {"main": "unrelated.example.org"},
                    "certificate": base64.b64encode(b"other").decode("ascii"),
                    "key": base64.b64encode(b"other").decode("ascii"),
                },
                {
                    "domain": {"main": domain, "sans": sans or []},
                    "certificate": base64.b64encode(
                        fullchain.encode("utf-8")
                    ).decode("ascii"),
                    "key": base64.b64encode(privkey.encode("utf-8")).decode("ascii"),
                    "Store": "default",
                },
            ],
        }
    }


def test_extract_certificate_picks_the_matching_domain():
    payload = acme_payload("vpn.example.com", "CHAIN", "KEY")

    pair = certs.extract_certificate(payload, "vpn.example.com")

    assert pair.fullchain == "CHAIN"
    assert pair.privkey == "KEY"
    assert pair.is_placeholder is False


def test_extract_certificate_matches_sans_and_wildcards():
    payload = acme_payload(
        "example.com", "CHAIN", "KEY", sans=["alias.example.com"]
    )
    assert certs.extract_certificate(payload, "alias.example.com").fullchain == "CHAIN"

    wildcard = acme_payload("*.example.com", "CHAIN", "KEY")
    assert certs.extract_certificate(wildcard, "vpn.example.com").fullchain == "CHAIN"
    # A wildcard covers a single label only.
    with pytest.raises(certs.CertificateNotFound):
        certs.extract_certificate(wildcard, "a.b.example.com")


def test_extract_certificate_reports_a_missing_domain():
    payload = acme_payload("vpn.example.com", "CHAIN", "KEY")

    with pytest.raises(certs.CertificateNotFound) as error:
        certs.extract_certificate(payload, "other.example.com")

    assert "other.example.com" in str(error.value)


def test_extract_certificate_rejects_malformed_base64():
    payload = acme_payload("vpn.example.com", "CHAIN", "KEY")
    payload["letsencrypt"]["Certificates"][1]["certificate"] = "not base64!"

    with pytest.raises(ValueError):
        certs.extract_certificate(payload, "vpn.example.com")


def test_read_acme_reports_missing_and_empty_files(tmp_path):
    with pytest.raises(certs.CertificateNotFound):
        certs.read_acme(tmp_path / "absent.json")

    empty = tmp_path / "acme.json"
    empty.write_text("   ", encoding="utf-8")
    with pytest.raises(certs.CertificateNotFound):
        certs.read_acme(empty)

    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    with pytest.raises(ValueError):
        certs.read_acme(broken)


def test_sync_once_is_idempotent(tmp_path):
    acme = tmp_path / "acme.json"
    acme.write_text(
        json.dumps(acme_payload("vpn.example.com", "CHAIN", "KEY")), encoding="utf-8"
    )
    tls_dir = tmp_path / "tls"

    assert certs.sync_once(tls_dir, "vpn.example.com", acme) is True
    assert certs.sync_once(tls_dir, "vpn.example.com", acme) is False

    fullchain, privkey = certs.certificate_files(tls_dir)
    assert fullchain.read_text(encoding="utf-8") == "CHAIN"
    assert privkey.read_text(encoding="utf-8") == "KEY"


def test_sync_once_picks_up_a_renewal(tmp_path):
    acme = tmp_path / "acme.json"
    acme.write_text(
        json.dumps(acme_payload("vpn.example.com", "CHAIN", "KEY")), encoding="utf-8"
    )
    tls_dir = tmp_path / "tls"
    certs.sync_once(tls_dir, "vpn.example.com", acme)

    acme.write_text(
        json.dumps(acme_payload("vpn.example.com", "RENEWED", "NEWKEY")),
        encoding="utf-8",
    )

    assert certs.sync_once(tls_dir, "vpn.example.com", acme) is True
    fullchain, _ = certs.certificate_files(tls_dir)
    assert fullchain.read_text(encoding="utf-8") == "RENEWED"


def test_placeholder_is_only_written_when_nothing_exists(tmp_path):
    tls_dir = tmp_path / "tls"

    assert certs.ensure_placeholder(tls_dir, "vpn.example.com") is True
    pair = certs.current_pair(tls_dir)
    assert pair is not None and pair.is_placeholder is True
    assert "BEGIN CERTIFICATE" in pair.fullchain
    assert "PRIVATE KEY" in pair.privkey

    assert certs.ensure_placeholder(tls_dir, "vpn.example.com") is False


def test_real_certificate_replaces_the_placeholder(tmp_path):
    tls_dir = tmp_path / "tls"
    certs.ensure_placeholder(tls_dir, "vpn.example.com")
    acme = tmp_path / "acme.json"
    acme.write_text(
        json.dumps(acme_payload("vpn.example.com", "CHAIN", "KEY")), encoding="utf-8"
    )

    assert certs.sync_once(tls_dir, "vpn.example.com", acme) is True

    pair = certs.current_pair(tls_dir)
    assert pair is not None and pair.is_placeholder is False


def test_watch_reports_pending_then_updated(tmp_path):
    acme = tmp_path / "acme.json"
    tls_dir = tmp_path / "tls"
    events: list[str] = []

    def fake_sleep(_seconds: float) -> None:
        # Traefik finishes the challenge between the first and second poll.
        acme.write_text(
            json.dumps(acme_payload("vpn.example.com", "CHAIN", "KEY")),
            encoding="utf-8",
        )

    certs.watch(
        tls_dir,
        "vpn.example.com",
        acme,
        interval=0,
        iterations=3,
        sleep=fake_sleep,
        on_event=lambda event, _error: events.append(event),
    )

    assert events == ["pending", "updated", "unchanged"]


def test_watch_survives_a_corrupt_acme_file(tmp_path):
    acme = tmp_path / "acme.json"
    acme.write_text("{ broken", encoding="utf-8")
    events: list[str] = []

    certs.watch(
        tmp_path / "tls",
        "vpn.example.com",
        acme,
        interval=0,
        iterations=2,
        sleep=lambda _s: None,
        on_event=lambda event, _error: events.append(event),
    )

    assert events == ["error", "error"]


def test_acme_path_from_env(monkeypatch):
    monkeypatch.delenv("VPNFORGE_ACME_JSON", raising=False)
    assert certs.acme_path_from_env() == certs.DEFAULT_ACME_PATH

    monkeypatch.setenv("VPNFORGE_ACME_JSON", "/custom/acme.json")
    assert str(certs.acme_path_from_env()).replace("\\", "/") == "/custom/acme.json"
