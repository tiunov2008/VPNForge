from __future__ import annotations

import shutil
import os
from pathlib import Path

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.docker import DockerCompose
from vpnforge.services.bbr import configure_bbr
from vpnforge.shell import Runner, runner


console = Console()
CONTAINERS = (
    "vpnforge-nginx",
    "vpnforge-xray",
    "vpnforge-certbot",
    "vpnforge-hysteria",
)
NETWORKS = ("vpnforge",)


def _remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
        raise RuntimeError(f"Refusing to remove unsafe path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _stop_containers(paths: Paths, command_runner: Runner) -> None:
    if paths.compose_file.is_file():
        DockerCompose(paths, command_runner=command_runner).run(
            "down",
            "--remove-orphans",
            "--timeout",
            "10",
            check=False,
            capture=True,
        )
    command_runner.run(
        ["docker", "rm", "--force", *CONTAINERS],
        check=False,
        capture=True,
    )
    for network in NETWORKS:
        command_runner.run(
            ["docker", "network", "rm", network],
            check=False,
            capture=True,
        )


def _remove_wrapper() -> None:
    host_bin_dir = os.getenv("VPNFORGE_HOST_BIN_DIR")
    if not host_bin_dir:
        return
    wrapper = Path(host_bin_dir) / "vpnforge"
    wrapper.unlink(missing_ok=True)


def run(purge: bool, command_runner: Runner = runner) -> None:
    paths = Paths.from_env()
    _stop_containers(paths, command_runner)
    console.print("[green]Stopped VPNForge containers.[/green]")
    _remove_tree(paths.runtime_dir)
    console.print(f"[green]Removed runtime data:[/green] {paths.runtime_dir}")
    if purge:
        configure_bbr(paths, False)
        _remove_tree(paths.config_dir)
        _remove_wrapper()
        console.print(
            f"[green]Removed settings and secrets:[/green] {paths.config_dir}"
        )
    else:
        console.print(
            f"[yellow]Preserved settings and secrets:[/yellow] {paths.config_dir}"
        )
