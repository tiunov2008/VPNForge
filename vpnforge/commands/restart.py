from vpnforge.commands.up import SERVICES
from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.certbot import certificate_exists
from vpnforge.services.hysteria import sync_hysteria_certificate


def run(service: str) -> None:
    if service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    paths = Paths.from_env()
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
