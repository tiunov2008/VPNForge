from __future__ import annotations

import base64
import json

import pytest
import yaml

from vpnforge.config import create_settings, ensure_directories, write_settings
from vpnforge.files import atomic_write
from vpnforge.services.nginx import active_stage, render_nginx, use_nginx
from vpnforge.services.hysteria import render_hysteria
from vpnforge.services.xray import (
    SECRET_NAMES,
    client_links,
    render_xray,
    secret_path,
)


VALUES = {
    "xray_uuid": "123e4567-e89b-12d3-a456-426614174000",
    "reality_private_key": "private-key",
    "reality_public_key": "public-key",
    "reality_short_id": "0011223344556677",
    "xhttp_path": "aabbccddeeff",
    "subscription_path": "00112233445566778899",
    "hysteria_password": "hysteria-password-1234567890",
    "hysteria_obfs_password": "hysteria-obfs-1234567890",
}


def prepare(paths):
    ensure_directories(paths)
    settings = create_settings("vpn.example.com", "admin@example.com").model_copy(
        update={"subscription_title": "Моя подписка"}
    )
    write_settings(paths, settings)
    for name in SECRET_NAMES:
        atomic_write(secret_path(paths, name), VALUES[name] + "\n", mode=0o600)


def test_rendered_configs_are_valid_and_complete(paths):
    prepare(paths)
    assert render_xray(paths) is True
    assert render_hysteria(paths) is True
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
    assert "00112233445566778899.hysteria.yaml" in final
    encoded_title = base64.b64encode("Моя подписка".encode()).decode()
    assert f'add_header profile-title "base64:{encoded_title}" always;' in final

    links = (
        (paths.nginx_html_dir / "subscription.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(links) == 7
    assert all(link.startswith("vless://") for link in links[:6])
    assert all("autoXRAY" not in link for link in links)
    assert all("VPNForge" in link for link in links[:6])
    assert links[-1].startswith("hysteria2://")
    assert ":20000-50000/" in links[-1]
    assert "public-key" in links[0]

    server = yaml.safe_load(
        (paths.hysteria_dir / "config.yaml").read_text(encoding="utf-8")
    )
    client = yaml.safe_load(
        (paths.hysteria_dir / "hysteria-client.yaml").read_text(encoding="utf-8")
    )
    assert server["listen"] == ":20000-50000"
    assert server["obfs"]["type"] == "salamander"
    assert client["server"] == "vpn.example.com:20000-50000"
    assert client["transport"]["udp"]["minHopInterval"] == "15s"
    web_client = yaml.safe_load(
        (paths.nginx_html_dir / "00112233445566778899.hysteria.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert web_client == client

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


def test_disabling_hysteria_removes_generated_client_files(paths):
    prepare(paths)
    render_hysteria(paths)
    render_nginx(paths, "final")
    settings = create_settings("vpn.example.com", "admin@example.com").model_copy(
        update={
            "subscription_title": "Моя подписка",
            "enable_hysteria": False,
        }
    )
    write_settings(paths, settings, force=True)

    render_hysteria(paths, force=True)
    render_nginx(paths, "final", force=True)

    assert not (paths.hysteria_dir / "config.yaml").exists()
    assert not (paths.hysteria_dir / "hysteria-client.yaml").exists()
    assert not list(paths.nginx_html_dir.glob("*.hysteria.yaml"))
    subscription = (paths.nginx_html_dir / "subscription.txt").read_text(
        encoding="utf-8"
    )
    assert "hysteria2://" not in subscription
    final = (paths.nginx_dir / "final.conf").read_text(encoding="utf-8")
    assert ".hysteria.yaml" not in final


def test_hysteria_render_is_idempotent_and_requires_force(paths):
    prepare(paths)
    assert render_hysteria(paths) is True
    assert render_hysteria(paths) is False
    config = paths.hysteria_dir / "config.yaml"
    config.write_text("changed\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        render_hysteria(paths)
    assert render_hysteria(paths, force=True) is True


def test_hysteria_uri_percent_encodes_credentials():
    settings = create_settings("vpn.example.com")
    values = {
        **VALUES,
        "hysteria_password": "password with:/?#@symbols",
        "hysteria_obfs_password": "obfs with:/?#@symbols",
    }

    uri = client_links(settings, values)[-1]["link"]

    assert "password%20with%3A%2F%3F%23%40symbols" in uri
    assert "obfs%20with%3A%2F%3F%23%40symbols" in uri
