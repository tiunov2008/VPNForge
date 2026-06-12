from __future__ import annotations

import sys

from rich.console import Console

from vpnforge.checks import is_root
from vpnforge.config import Paths, load_settings
from vpnforge.shell import Runner, runner


console = Console()


def run(command_runner: Runner = runner) -> None:
    if not is_root():
        raise RuntimeError("VPNForge update must run as root")

    paths = Paths.from_env()
    if not (paths.project_dir / ".git").is_dir():
        raise RuntimeError(
            f"VPNForge project is not a Git checkout: {paths.project_dir}"
        )

    settings = load_settings(paths)
    command_runner.run(
        [
            "git",
            "-C",
            str(paths.project_dir),
            "pull",
            "--ff-only",
            "origin",
            "main",
        ]
    )
    command_runner.run(
        [sys.executable, "-m", "pip", "install", "-e", str(paths.project_dir)]
    )
    command_runner.run(
        [
            sys.executable,
            "-m",
            "vpnforge.cli",
            "install",
            "--domain",
            settings.domain,
            "--email",
            settings.email,
        ]
    )
    console.print("[green]VPNForge update completed.[/green]")
