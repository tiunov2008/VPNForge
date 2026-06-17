from __future__ import annotations

import yaml

from vpnforge.config import create_settings, ensure_directories, write_settings
from vpnforge.docker import DockerCompose, compose_files_exist
from vpnforge.services.compose import render_compose


def test_compose_template_does_not_contain_secrets(paths):
    content = (paths.templates_dir / "compose" / "docker-compose.yml.j2").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "XRAY_UUID",
        "REALITY_PRIVATE_KEY",
        "REALITY_SHORT_ID",
        "xray_uuid",
        "hysteria_password",
        "hysteria_obfs_password",
    ):
        assert forbidden not in content


def test_render_compose_creates_valid_generated_file(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com"))

    assert render_compose(paths) is True

    compose = yaml.safe_load(paths.compose_file.read_text(encoding="utf-8"))
    assert isinstance(compose, dict)
    assert compose_files_exist(paths) is True
    assert compose["services"]["nginx"]["container_name"] == "vpnforge-nginx"


def test_docker_compose_uses_generated_compose_file(paths):
    docker = DockerCompose(paths)

    assert docker.command("ps") == [
        "docker",
        "compose",
        "--project-name",
        "vpnforge",
        "-f",
        str(paths.compose_file),
        "ps",
    ]


def test_hysteria_uses_host_network_and_net_admin(paths):
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com"))
    render_compose(paths)
    compose = yaml.safe_load(paths.compose_file.read_text(encoding="utf-8"))
    service = compose["services"]["hysteria"]

    assert service["network_mode"] == "host"
    assert service["cap_add"] == ["NET_ADMIN"]
    assert "ports" not in service
