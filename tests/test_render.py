from __future__ import annotations

import json

import pytest

from vpnforge.config import create_settings, ensure_directories, write_settings
from vpnforge.files import atomic_write
from vpnforge.services.nginx import active_stage, render_nginx, use_nginx
from vpnforge.services.xray import SECRET_NAMES, render_xray, secret_path


VALUES = {
    "xray_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "reality_private_key": "private-key",
    "reality_public_key": "public-key",
    "reality_short_id": "0011223344556677",
    "xhttp_path": "aabbccddeeff",
    "subscription_path": "00112233445566778899",
}


def prepare(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com", "admin@example.com"))
    for name in SECRET_NAMES:
        atomic_write(secret_path(paths, name), VALUES[name] + "\n", mode=0o600)


def test_rendered_configs_are_valid_and_complete(paths):
    prepare(paths)
    assert render_xray(paths) is True
    assert render_nginx(paths, "bootstrap") is True
    assert render_nginx(paths, "final") is True

    xray = json.loads((paths.xray_dir / "config.json").read_text(encoding="utf-8"))
    assert "{{" not in (paths.xray_dir / "config.json").read_text(encoding="utf-8")
    assert len(xray["inbounds"]) == 6
    assert (
        xray["inbounds"][0]["streamSettings"]["realitySettings"]["privateKey"]
        == "private-key"
    )
    certificates = xray["inbounds"][2]["streamSettings"]["tlsSettings"]["certificates"]
    assert certificates[0]["keyFile"] == "/etc/xray/cert/privkey.pem"

    final = (paths.nginx_dir / "final.conf").read_text(encoding="utf-8")
    assert "{{" not in final
    assert "listen 8080 ssl proxy_protocol" in final
    assert "/aabbccddeeff11" in final
    assert "00112233445566778899.txt" in final

    links = (
        (paths.nginx_html_dir / "subscription.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(links) == 6
    assert all(link.startswith("vless://") for link in links)
    assert "public-key" in links[0]

    use_nginx(paths, "bootstrap")
    assert active_stage(paths) == "bootstrap"
    use_nginx(paths, "final")
    assert active_stage(paths) == "final"


def test_render_does_not_silently_replace_changed_file(paths):
    prepare(paths)
    render_xray(paths)
    config = paths.xray_dir / "config.json"
    config.write_text("changed\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        render_xray(paths)
    assert render_xray(paths, force=True) is True
