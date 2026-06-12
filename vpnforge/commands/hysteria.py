from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.services.hysteria import render_hysteria


console = Console()


def render(force: bool) -> None:
    paths = Paths.from_env()
    render_hysteria(paths, force=force)
    if not load_settings(paths).enable_hysteria:
        console.print("[yellow]Hysteria is disabled; generated files removed.[/yellow]")
        return
    console.print(
        f"[green]Hysteria config rendered:[/green] {paths.hysteria_dir / 'config.yaml'}"
    )
