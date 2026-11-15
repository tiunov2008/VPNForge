from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.services.certbot import issue_certificate, renew_certificate


console = Console()


def issue() -> None:
    paths = Paths.from_env()
    issue_certificate(paths)
    console.print("[green]Certificate is ready.[/green]")


def renew(dry_run: bool = False, force: bool = False) -> None:
    paths = Paths.from_env()
    if not paths.env_file.is_file():
        console.print("[yellow]VPNForge is not installed; nothing to renew.[/yellow]")
        return
    changed = renew_certificate(paths, dry_run=dry_run, force=force)
    if dry_run:
        console.print("[green]Certificate renewal dry run succeeded.[/green]")
    elif changed:
        console.print(
            "[green]Certificate renewed; Nginx, Xray and Hysteria reloaded.[/green]"
        )
    else:
        console.print("[green]Certificate is not due for renewal.[/green]")
