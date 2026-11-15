from __future__ import annotations

from pathlib import Path


def test_install_script_installs_container_wrapper():
    root = Path(__file__).resolve().parents[1]
    content = (root / "install.sh").read_text(encoding="utf-8")

    assert "ghcr.io/tiunov2008/vpnforge:latest" in content
    assert "/usr/local/bin/vpnforge" in content
    assert "/var/run/docker.sock:/var/run/docker.sock" in content
    assert "/etc/vpnforge:/etc/vpnforge" in content
    assert "/var/lib/vpnforge:/var/lib/vpnforge" in content
    assert "INSTALL_ARGS+=(--force)" in content
    assert "/usr/local/bin:/host/usr/local/bin" in content
    assert "VPNFORGE_HOST_BIN_DIR=/host/usr/local/bin" in content
    assert "git clone" not in content
    assert "python3 -m venv" not in content


def test_install_script_schedules_certificate_renewal():
    root = Path(__file__).resolve().parents[1]
    content = (root / "install.sh").read_text(encoding="utf-8")

    assert "/etc/systemd/system/vpnforge-cert-renew.timer" in content
    assert "ExecStart=/usr/local/bin/vpnforge cert renew" in content
    assert "systemctl enable --now vpnforge-cert-renew.timer" in content
    assert "/etc/cron.d/vpnforge-cert-renew" in content
    assert content.index("install_cert_renew_schedule\n") < content.index(
        'exec /usr/local/bin/vpnforge "${INSTALL_ARGS[@]}"'
    )
