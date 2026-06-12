from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from vpnforge.config import Paths, load_settings
from vpnforge.files import atomic_copy
from vpnforge.render import render_template, write_rendered
from vpnforge.services.certbot import certificate_path
from vpnforge.services.xray import template_context


def hysteria_certificate_path(paths: Paths) -> tuple[Path, Path]:
    certificate_dir = paths.hysteria_dir / "cert"
    return certificate_dir / "fullchain.pem", certificate_dir / "privkey.pem"


def sync_hysteria_certificate(paths: Paths, domain: str) -> None:
    source_fullchain, source_privkey = certificate_path(paths, domain)
    if not source_fullchain.is_file() or not source_privkey.is_file():
        raise FileNotFoundError("Let's Encrypt certificate files are missing")

    destination_fullchain, destination_privkey = hysteria_certificate_path(paths)
    destination_fullchain.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination_fullchain.parent, 0o700)
    atomic_copy(source_fullchain.resolve(), destination_fullchain, mode=0o600)
    atomic_copy(source_privkey.resolve(), destination_privkey, mode=0o600)


def remove_hysteria_outputs(paths: Paths) -> None:
    for path in (
        paths.hysteria_dir / "config.yaml",
        paths.hysteria_dir / "hysteria-client.yaml",
    ):
        path.unlink(missing_ok=True)
    shutil.rmtree(paths.hysteria_dir / "cert", ignore_errors=True)


def render_hysteria(paths: Paths, *, force: bool = False) -> bool:
    settings = load_settings(paths)
    if not settings.enable_hysteria:
        remove_hysteria_outputs(paths)
        return False

    context = template_context(paths, settings)
    server_content = render_template(paths, "hysteria/config.yaml.j2", context)
    client_content = render_template(paths, "hysteria/client.yaml.j2", context)
    if not isinstance(yaml.safe_load(server_content), dict):
        raise ValueError("Rendered Hysteria server config is not valid YAML")
    if not isinstance(yaml.safe_load(client_content), dict):
        raise ValueError("Rendered Hysteria client config is not valid YAML")

    changed = write_rendered(
        paths.hysteria_dir / "config.yaml",
        server_content,
        force=force,
        mode=0o600,
    )
    return (
        write_rendered(
            paths.hysteria_dir / "hysteria-client.yaml",
            client_content,
            force=force,
            mode=0o600,
        )
        or changed
    )
