from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from vpnforge.config import Paths, Settings, load_settings
from vpnforge.docker import DockerCompose
from vpnforge.files import atomic_copy, atomic_write
from vpnforge.services.nginx import active_stage
from vpnforge.services.xray import secure_xray_runtime_path
from vpnforge.state import update_state


RENEWAL_CRON_NAME = "vpnforge-renew"
RENEWAL_LOG = "/var/log/vpnforge-renew.log"
# Certbot renews a certificate once it enters its last 30 days, so twice-daily
# attempts are the documented cadence: the extra runs are cheap no-ops.
RENEWAL_CRON = f"""# Managed by VPNForge. Renews the Let's Encrypt certificate.
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 3,15 * * * root /usr/local/bin/vpnforge cert renew >>{RENEWAL_LOG} 2>&1
"""
PEM_CERTIFICATE_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----",
    re.DOTALL,
)


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


def renewal_cron_path(paths: Paths) -> Path:
    return paths.cron_dir / RENEWAL_CRON_NAME


def configure_renewal(paths: Paths, enabled: bool = True) -> Path | None:
    """Install or remove the host cron job that runs `vpnforge cert renew`."""
    cron_path = renewal_cron_path(paths)
    if not enabled:
        cron_path.unlink(missing_ok=True)
        return None
    if not paths.cron_dir.is_dir():
        raise FileNotFoundError(
            f"Cron directory is not available: {paths.cron_dir}; "
            "renew the certificate manually with 'vpnforge cert renew'"
        )
    # Cron ignores group- or world-writable files in /etc/cron.d.
    atomic_write(cron_path, RENEWAL_CRON, mode=0o644)
    return cron_path


def _certificate_digest(paths: Paths, domain: str) -> str | None:
    fullchain, _ = certificate_path(paths, domain)
    if not fullchain.is_file():
        return None
    return hashlib.sha256(fullchain.read_bytes()).hexdigest()


def _der_elements(data: bytes, start: int, end: int) -> Iterator[tuple[int, int, int]]:
    index = start
    while index + 1 < end:
        tag = data[index]
        length = data[index + 1]
        index += 2
        if length & 0x80:
            count = length & 0x7F
            if count == 0 or index + count > end:
                return
            length = int.from_bytes(data[index : index + count], "big")
            index += count
        if index + length > end:
            return
        yield tag, index, index + length
        index += length


def _find_not_after(data: bytes, start: int, end: int) -> tuple[int, bytes] | None:
    """Depth-first search for the Validity SEQUENCE { notBefore, notAfter }."""
    for tag, body_start, body_end in _der_elements(data, start, end):
        if tag != 0x30:
            continue
        children = list(_der_elements(data, body_start, body_end))
        if len(children) == 2 and all(child[0] in (0x17, 0x18) for child in children):
            child_tag, child_start, child_end = children[1]
            return child_tag, data[child_start:child_end]
        found = _find_not_after(data, body_start, body_end)
        if found is not None:
            return found
    return None


def certificate_expiry(paths: Paths, domain: str) -> datetime | None:
    """Read notAfter from the leaf certificate without extra dependencies."""
    fullchain, _ = certificate_path(paths, domain)
    if not fullchain.is_file():
        return None
    match = PEM_CERTIFICATE_RE.search(fullchain.read_text(encoding="utf-8"))
    if match is None:
        return None
    try:
        der = base64.b64decode("".join(match.group(1).split()), validate=True)
    except (binascii.Error, ValueError):
        return None
    found = _find_not_after(der, 0, len(der))
    if found is None:
        return None
    tag, raw = found
    text = raw.decode("ascii", errors="ignore")
    pattern = "%y%m%d%H%M%SZ" if tag == 0x17 else "%Y%m%d%H%M%SZ"
    try:
        return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def certificate_days_remaining(paths: Paths, domain: str) -> int | None:
    expiry = certificate_expiry(paths, domain)
    if expiry is None:
        return None
    return (expiry - datetime.now(timezone.utc)).days


def reload_certificate_consumers(
    paths: Paths,
    settings: Settings | None = None,
    docker: DockerCompose | None = None,
) -> list[str]:
    """Copy the renewed certificate to every service and restart them."""
    settings = settings or load_settings(paths)
    docker = docker or DockerCompose(paths)
    reloaded = ["nginx"]
    if settings.enable_xray:
        sync_xray_certificate(paths, settings.domain)
        reloaded.append("xray")
    if settings.enable_hysteria:
        from vpnforge.services.hysteria import sync_hysteria_certificate

        sync_hysteria_certificate(paths, settings.domain)
        reloaded.append("hysteria")
    for service in reloaded:
        docker.restart(service)
    return reloaded


def renew_certificate(
    paths: Paths, docker: DockerCompose | None = None, *, force: bool = False
) -> bool:
    """Renew the certificate and reload its consumers when it actually changed."""
    settings = load_settings(paths)
    docker = docker or DockerCompose(paths)
    if not certificate_exists(paths, settings.domain):
        raise RuntimeError(
            "No certificate to renew; run 'vpnforge cert issue' first"
        )
    if not docker.is_running("nginx"):
        raise RuntimeError(
            "Nginx must be running so Certbot can answer the ACME challenge"
        )
    before = _certificate_digest(paths, settings.domain)
    arguments = ["run", "--rm", "certbot", "renew", "--non-interactive"]
    if force:
        arguments.append("--force-renewal")
    docker.run(*arguments)
    if _certificate_digest(paths, settings.domain) == before:
        return False
    reload_certificate_consumers(paths, settings, docker)
    update_state(
        paths,
        certificate_renewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return True
