from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.certbot import certificate_exists, sync_xray_certificate
from vpnforge.services.hysteria import sync_hysteria_certificate


console = Console()
SERVICES = {"nginx", "xray", "hysteria"}


def run(service: str | None) -> None:
    if service and service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    paths = Paths.from_env()
    settings = load_settings(paths)
    if service == "hysteria" and not settings.enable_hysteria:
        raise RuntimeError("Hysteria is disabled in vpnforge.env")
    services = [service] if service else ["nginx"]
    if not service and settings.enable_xray:
        services.append("xray")
    if not service and settings.enable_hysteria:
        services.append("hysteria")
    if "nginx" in services and not (paths.nginx_dir / "active.conf").is_file():
        raise FileNotFoundError(
            "Nginx active.conf is missing; render and activate a stage first"
        )
    if "xray" in services:
        if not (paths.xray_dir / "config.json").is_file():
            raise FileNotFoundError(
                "Xray config.json is missing; run vpnforge xray render"
            )
        if not certificate_exists(paths, settings.domain):
            raise FileNotFoundError(
                "Let's Encrypt certificate is missing; run vpnforge cert issue"
            )
        sync_xray_certificate(paths, settings.domain)
    if "hysteria" in services:
        if not (paths.hysteria_dir / "config.yaml").is_file():
            raise FileNotFoundError(
                "Hysteria config.yaml is missing; run vpnforge hysteria render"
            )
        if not certificate_exists(paths, settings.domain):
            raise FileNotFoundError(
                "Let's Encrypt certificate is missing; run vpnforge cert issue"
            )
        sync_hysteria_certificate(paths, settings.domain)
    docker = DockerCompose(paths)
    if not settings.enable_hysteria:
        docker.remove("hysteria")
    docker.up(services)
    console.print(f"[green]Started:[/green] {', '.join(services)}")
