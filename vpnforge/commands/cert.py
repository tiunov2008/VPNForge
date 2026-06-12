from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.certbot import issue_certificate


console = Console()


def issue() -> None:
    paths = Paths.from_env()
    issue_certificate(paths)
    console.print("[green]Certificate is ready.[/green]")
