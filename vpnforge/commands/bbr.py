from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.services.bbr import configure_bbr


console = Console()


def apply() -> None:
    paths = Paths.from_env()
    settings = load_settings(paths)
    status = configure_bbr(paths, settings.enable_bbr)
    if status is None:
        console.print("[yellow]BBR management disabled.[/yellow]")
    else:
        console.print("[green]BBR enabled with fq qdisc.[/green]")
