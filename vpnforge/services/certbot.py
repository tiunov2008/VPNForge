from __future__ import annotations

import ssl
from datetime import datetime, timezone
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
    if settings.enable_hysteria:
        from vpnforge.services.hysteria import sync_hysteria_certificate

        sync_hysteria_certificate(paths, settings.domain)
    update_state(paths, certificate_issued=True)


def certificate_expiry(paths: Paths, domain: str) -> datetime | None:
    fullchain, _ = certificate_path(paths, domain)
    if not fullchain.is_file():
        return None
    try:
        decoded = ssl._ssl._test_decode_cert(str(fullchain.resolve()))  # type: ignore[attr-defined]
        expires = ssl.cert_time_to_seconds(decoded["notAfter"])
    except (AttributeError, KeyError, OSError, ValueError, ssl.SSLError):
        return None
    return datetime.fromtimestamp(expires, tz=timezone.utc)


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.resolve().read_bytes()
    except OSError:
        return None


def _certificate_copies_outdated(paths: Paths, domain: str, hysteria: bool) -> bool:
    source_fullchain, source_privkey = certificate_path(paths, domain)
    expected = (_read_bytes(source_fullchain), _read_bytes(source_privkey))
    copies = [xray_certificate_path(paths)]
    if hysteria:
        from vpnforge.services.hysteria import hysteria_certificate_path

        copies.append(hysteria_certificate_path(paths))
    return any(
        (_read_bytes(fullchain), _read_bytes(privkey)) != expected
        for fullchain, privkey in copies
    )


def renew_certificate(
    paths: Paths,
    docker: DockerCompose | None = None,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """Renew the Let's Encrypt certificate and reload services when it changed.

    Returns True when a new certificate was deployed to Nginx, Xray and Hysteria.
    """
    settings = load_settings(paths)
    docker = docker or DockerCompose(paths)
    if not certificate_exists(paths, settings.domain):
        raise FileNotFoundError(
            "Let's Encrypt certificate is missing; run vpnforge cert issue"
        )
    if not docker.is_running("nginx"):
        raise RuntimeError(
            "Nginx must be running to answer the HTTP challenge during renewal"
        )

    fullchain, _ = certificate_path(paths, settings.domain)
    before = _read_bytes(fullchain)
    arguments = [
        "run",
        "--rm",
        "certbot",
        "renew",
        "--cert-name",
        settings.domain,
        "--webroot",
        "--webroot-path",
        "/var/www/certbot",
        "--non-interactive",
    ]
    if dry_run:
        arguments.append("--dry-run")
    if force:
        arguments.append("--force-renewal")
    docker.run(*arguments)
    if dry_run:
        return False

    renewed = _read_bytes(fullchain) != before
    changed = renewed or _certificate_copies_outdated(
        paths, settings.domain, settings.enable_hysteria
    )
    if changed:
        sync_xray_certificate(paths, settings.domain)
        if settings.enable_hysteria:
            from vpnforge.services.hysteria import sync_hysteria_certificate

            sync_hysteria_certificate(paths, settings.domain)
        docker.exec("nginx", "nginx", "-s", "reload")
        for service, enabled in (
            ("xray", settings.enable_xray),
            ("hysteria", settings.enable_hysteria),
        ):
            if enabled and docker.is_running(service):
                docker.restart(service)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes: dict[str, str] = {"certificate_renew_checked_at": now}
    if changed:
        changes["certificate_deployed_at"] = now
    update_state(paths, **changes)
    return changed
