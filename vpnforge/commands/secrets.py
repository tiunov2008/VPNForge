from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, ensure_directories
from vpnforge.services.xray import generate_secrets


console = Console()


def run(force: bool) -> None:
    paths = Paths.from_env()
    ensure_directories(paths)
    generated = generate_secrets(paths, force=force)
    if generated:
        console.print(f"[green]Generated secrets:[/green] {', '.join(generated)}")
    else:
        console.print("[yellow]Secrets already exist, unchanged.[/yellow]")
