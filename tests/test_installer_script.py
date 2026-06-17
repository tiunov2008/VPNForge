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
    assert "git clone" not in content
    assert "python3 -m venv" not in content
