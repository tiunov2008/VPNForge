from __future__ import annotations

from pathlib import Path

from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.files import atomic_copy
from vpnforge.services.nginx import active_stage
from vpnforge.services.xray import secure_xray_runtime_path
from vpnforge.state import update_state


def certificate_path(paths: Paths, domain: str) -> tuple[Path, Path]:
    live = paths.certbot_conf_dir / "live" / domain
    return live / "fullchain.pem", live / "privkey.pem"


def certificate_exists(paths: Paths, domain: str) -> bool:
    return all(path.is_file() for path in certificate_path(paths, domain))


def xray_certificate_path(paths: Paths) -> tuple[Path, Path]:
    certificate_dir = paths.xray_dir / "cert"
    return certificate_dir / "fullchain.pem", certificate_dir / "privkey.pem"


def sync_xray_certificate(paths: Paths, domain: str) -> None:
    source_fullchain, source_privkey = certificate_path(paths, domain)
    if not source_fullchain.is_file() or not source_privkey.is_file():
        raise FileNotFoundError("Let's Encrypt certificate files are missing")

    destination_fullchain, destination_privkey = xray_certificate_path(paths)
    destination_fullchain.parent.mkdir(parents=True, exist_ok=True)
    secure_xray_runtime_path(destination_fullchain.parent, directory=True)
    atomic_copy(source_fullchain.resolve(), destination_fullchain, mode=0o600)
    atomic_copy(source_privkey.resolve(), destination_privkey, mode=0o600)
    secure_xray_runtime_path(destination_fullchain)
    secure_xray_runtime_path(destination_privkey)


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
    sync_xray_certificate(paths, settings.domain)
    update_state(paths, certificate_issued=True)
