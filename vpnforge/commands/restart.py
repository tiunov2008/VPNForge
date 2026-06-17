from vpnforge.commands.up import SERVICES
from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.certbot import certificate_exists
from vpnforge.services.hysteria import sync_hysteria_certificate


def _enabled_services(paths: Paths) -> list[str]:
    settings = load_settings(paths)
    services = ["nginx"]
    if settings.enable_xray:
        services.append("xray")
    if settings.enable_hysteria:
        services.append("hysteria")
    return services


def run(service: str | None) -> None:
    paths = Paths.from_env()
    if service is None:
        docker = DockerCompose(paths)
        for enabled_service in _enabled_services(paths):
            docker.restart(enabled_service)
        return

    if service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    if service == "hysteria":
        settings = load_settings(paths)
        if not settings.enable_hysteria:
            raise RuntimeError("Hysteria is disabled in vpnforge.env")
        if not (paths.hysteria_dir / "config.yaml").is_file():
            raise FileNotFoundError(
                "Hysteria config.yaml is missing; run vpnforge hysteria render"
            )
        if not certificate_exists(paths, settings.domain):
            raise FileNotFoundError(
                "Let's Encrypt certificate is missing; run vpnforge cert issue"
            )
        sync_hysteria_certificate(paths, settings.domain)
    DockerCompose(paths).restart(service)
