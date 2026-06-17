from __future__ import annotations

import os

from vpnforge.config import Paths


DEFAULT_IMAGE = "ghcr.io/tiunov2008/vpnforge:latest"


def image_name() -> str:
    return os.getenv("VPNFORGE_IMAGE", DEFAULT_IMAGE)


def cli_container_command(paths: Paths, image: str, *arguments: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "--privileged",
        "--network",
        "host",
        "-e",
        f"VPNFORGE_IMAGE={image}",
        "-e",
        f"VPNFORGE_PROJECT_DIR={paths.project_dir}",
        "-e",
        f"VPNFORGE_CONFIG_DIR={paths.config_dir}",
        "-e",
        f"VPNFORGE_RUNTIME_DIR={paths.runtime_dir}",
        "-e",
        f"VPNFORGE_SYSCTL_DIR={paths.sysctl_dir}",
        "-v",
        f"{paths.config_dir}:{paths.config_dir}",
        "-v",
        f"{paths.runtime_dir}:{paths.runtime_dir}",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{paths.sysctl_dir}:{paths.sysctl_dir}",
        "-v",
        "/lib/modules:/lib/modules:ro",
        image,
        *arguments,
    ]
