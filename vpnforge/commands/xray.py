from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.xray import render_xray


console = Console()


def render(force: bool) -> None:
    paths = Paths.from_env()
    render_xray(paths, force=force)
    console.print(
        f"[green]Xray config rendered:[/green] {paths.xray_dir / 'config.json'}"
    )
