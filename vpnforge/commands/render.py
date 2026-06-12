from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.nginx import render_nginx
from vpnforge.services.xray import render_xray


console = Console()


def run(force: bool) -> None:
    paths = Paths.from_env()
    render_xray(paths, force=force)
    render_nginx(paths, "bootstrap", force=force)
    render_nginx(paths, "final", force=force)
    console.print(f"[green]Configs rendered:[/green] {paths.generated_dir}")
