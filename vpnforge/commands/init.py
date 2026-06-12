from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.installer import initialize


console = Console()


def run(domain: str, email: str | None, force: bool) -> None:
    paths = Paths.from_env()
    written = initialize(paths, domain, email, force=force)
    if written:
        console.print(f"[green]Settings created:[/green] {paths.env_file}")
    else:
        console.print(
            f"[yellow]Settings already exist, unchanged:[/yellow] {paths.env_file}"
        )
    console.print(f"Runtime directory: {paths.runtime_dir}")
