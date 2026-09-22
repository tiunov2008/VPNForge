from __future__ import annotations

from pathlib import Path

import pytest
import yaml


COMPOSE_FILE = Path(__file__).resolve().parents[1] / "docker-compose.dokploy.yml"

# Ports a stock Dokploy install already owns: Traefik takes 80/tcp, 443/tcp and
# 443/udp (HTTP/3), the Dokploy UI takes 3000, and Swarm takes 2377/7946/4789.
DOKPLOY_RESERVED_PORTS = {80, 443, 3000, 2377, 7946, 4789}


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def published_ports(service: dict) -> list[int]:
    """Host ports a service publishes, resolving ${VAR:-default}."""
    ports = []
    for mapping in service.get("ports", []):
        published = str(mapping).rsplit(":", 1)[0]
        if published.startswith("${") and published.endswith("}"):
            published = published[2:-1].partition(":-")[2]
        ports.append(int(published))
    return ports


def test_compose_file_is_valid(compose):
    assert set(compose["services"]) == {"init", "certs", "nginx", "xray", "hysteria"}
    assert set(compose["volumes"]) == {
        "vpnforge-config",
        "vpnforge-runtime",
        "vpnforge-tls",
    }


def test_no_service_claims_a_dokploy_reserved_host_port(compose):
    for name, service in compose["services"].items():
        clashes = set(published_ports(service)) & DOKPLOY_RESERVED_PORTS
        assert not clashes, f"{name} publishes reserved host port(s) {clashes}"


def test_container_names_are_not_pinned(compose):
    # Dokploy appends a random suffix to the project name; a fixed
    # container_name collides as soon as two stacks exist and is rejected by
    # the template validator.
    for name, service in compose["services"].items():
        assert "container_name" not in service, name


def test_no_custom_networks_are_declared(compose):
    # Dokploy injects dokploy-network plus default into whichever service
    # carries the domain. The project default network already gives every
    # service name-based DNS.
    assert "networks" not in compose
    for name, service in compose["services"].items():
        assert "networks" not in service, name


def test_hysteria_uses_host_networking_without_a_port_range(compose):
    hysteria = compose["services"]["hysteria"]

    assert hysteria["network_mode"] == "host"
    assert hysteria["cap_add"] == ["NET_ADMIN"]
    assert hysteria["profiles"] == ["hysteria"]
    # Publishing the hop range through Docker spawns one docker-proxy per port
    # and never finishes starting.
    assert "ports" not in hysteria
    # A Dokploy domain here would inject networks: and Compose rejects that
    # alongside network_mode.
    assert "labels" not in hysteria


def test_xray_publishes_alternate_ports(compose):
    assert published_ports(compose["services"]["xray"]) == [2053, 8443]


def test_every_runtime_service_waits_for_init(compose):
    for name in ("certs", "nginx", "xray", "hysteria"):
        depends = compose["services"][name]["depends_on"]
        assert depends["init"]["condition"] == "service_completed_successfully", name
    assert compose["services"]["init"]["restart"] == "no"


def test_generated_state_lives_in_named_volumes(compose):
    # Dokploy deletes and re-clones the repository on every deploy, so nothing
    # generated may be stored relative to the source tree.
    for name, service in compose["services"].items():
        for mount in service.get("volumes", []):
            source = str(mount).split(":")[0]
            assert not source.startswith("."), f"{name} bind-mounts {source}"


def test_acme_is_mounted_as_a_directory_and_read_only(compose):
    for name in ("init", "certs"):
        mounts = [m for m in compose["services"][name]["volumes"] if "/acme" in m]
        assert len(mounts) == 1, name
        mount = mounts[0]
        # Binding the file itself would pin a stale inode when Traefik
        # rewrites acme.json, and would create a directory if it were absent.
        assert mount.endswith(":/acme:ro"), mount
        assert "acme.json" not in mount


def test_compose_file_carries_no_secrets(compose):
    content = COMPOSE_FILE.read_text(encoding="utf-8")
    for forbidden in (
        "XRAY_UUID",
        "REALITY_PRIVATE_KEY",
        "REALITY_SHORT_ID",
        "HYSTERIA_PASSWORD",
        "xray_uuid",
        "hysteria_password",
        "hysteria_obfs_password",
    ):
        assert forbidden not in content


def test_domain_is_mandatory(compose):
    for name in ("init", "certs"):
        assert compose["services"][name]["environment"]["DOMAIN"].startswith(
            "${DOMAIN:?"
        ), name


def test_hysteria_port_range_avoids_the_ephemeral_range(compose):
    # The Linux default ip_local_port_range starts at 32768; a hop range that
    # overlaps it collides with the host's own outbound connections.
    default = compose["services"]["init"]["environment"]["HYSTERIA_PORT_RANGE"]
    start, end = (int(part) for part in default.split(":-")[-1].rstrip("}").split("-"))
    assert start < end
    assert end <= 32768


def test_nginx_reloads_so_it_picks_up_a_renewed_certificate(compose):
    script = compose["services"]["nginx"]["command"][-1]

    # Hysteria re-reads certs per handshake and Xray re-checks hourly, but
    # nginx only reads them at startup, so it needs an explicit reload loop.
    assert "-s reload" in script
    assert "-t" in script
    # Every ${...} here must be Compose interpolation, resolved before the
    # container starts. A '$$' escape would survive into the shell, where it
    # expands to the process ID instead.
    assert "$$" not in script


def test_hysteria_has_a_single_switch(compose):
    # Forwarding ENABLE_HYSTERIA as well would give the user two switches for
    # one thing, which can disagree. COMPOSE_PROFILES alone decides.
    init_env = compose["services"]["init"]["environment"]
    assert "COMPOSE_PROFILES" in init_env
    assert "ENABLE_HYSTERIA" not in init_env


def test_vpnforge_services_pull_a_prebuilt_image(compose):
    # Dokploy passes --build unconditionally, so a build: section would rebuild
    # the image on the server at every deploy. The published tag is the slim
    # runtime target, without the Docker CLI the host installer needs.
    for name in ("init", "certs"):
        service = compose["services"][name]
        assert "build" not in service, name
        assert service["image"].startswith("${VPNFORGE_IMAGE:-"), name
        assert ":dokploy}" in service["image"], name
