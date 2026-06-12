from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.certbot import certificate_exists


console = Console()
SERVICES = {"nginx", "xray"}


def run(service: str | None) -> None:
    if service and service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    paths = Paths.from_env()
    settings = load_settings(paths)
    services = (
        [service] if service else ["nginx"] + (["xray"] if settings.enable_xray else [])
    )
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
    DockerCompose(paths).up(services)
    console.print(f"[green]Started:[/green] {', '.join(services)}")
