from __future__ import annotations

from rich.console import Console

from vpnforge.checks import is_root
from vpnforge.config import Paths, load_settings
from vpnforge.container import cli_container_command, image_name
from vpnforge.shell import Runner, runner


console = Console()


def run(command_runner: Runner = runner) -> None:
    if not is_root():
        raise RuntimeError("VPNForge update must run as root")

    paths = Paths.from_env()
    settings = load_settings(paths)
    image = image_name()
    command_runner.run(["docker", "pull", image])
    command_runner.run(
        cli_container_command(
            paths,
            image,
            "install",
            "--domain",
            settings.domain,
            "--email",
            settings.email,
        )
    )
    console.print("[green]VPNForge update completed.[/green]")
