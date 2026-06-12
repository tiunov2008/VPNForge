from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.nginx import NginxStage, render_nginx, use_nginx


console = Console()


def render(stage: NginxStage, force: bool) -> None:
    paths = Paths.from_env()
    render_nginx(paths, stage, force=force)
    console.print(f"[green]Nginx {stage} config rendered.[/green]")


def use(stage: NginxStage) -> None:
    paths = Paths.from_env()
    use_nginx(paths, stage)
    console.print(f"[green]Nginx active config: {stage}[/green]")
