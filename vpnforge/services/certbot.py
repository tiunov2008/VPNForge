from __future__ import annotations

from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.nginx import active_stage
from vpnforge.state import update_state


def certificate_path(paths: Paths, domain: str) -> tuple:
    live = paths.certbot_conf_dir / "live" / domain
    return live / "fullchain.pem", live / "privkey.pem"


def certificate_exists(paths: Paths, domain: str) -> bool:
    return all(path.is_file() for path in certificate_path(paths, domain))


def issue_certificate(paths: Paths, docker: DockerCompose | None = None) -> None:
    settings = load_settings(paths)
    docker = docker or DockerCompose(paths)
    if active_stage(paths) != "bootstrap":
        raise RuntimeError(
            "Nginx bootstrap config must be active before issuing a certificate"
        )
    if not docker.is_running("nginx"):
        raise RuntimeError("Nginx must be running before issuing a certificate")
    docker.run(
        "run",
        "--rm",
        "certbot",
        "certonly",
        "--webroot",
        "--webroot-path",
        "/var/www/certbot",
        "--domain",
        settings.domain,
        "--email",
        settings.email,
        "--agree-tos",
        "--non-interactive",
        "--keep-until-expiring",
    )
    if not certificate_exists(paths, settings.domain):
        raise RuntimeError("Certbot completed but certificate files were not found")
    update_state(paths, certificate_issued=True)
