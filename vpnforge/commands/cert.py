from __future__ import annotations

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.services.certbot import (
    certificate_days_remaining,
    configure_renewal,
    issue_certificate,
    renew_certificate,
    renewal_cron_path,
)


console = Console()


def issue() -> None:
    paths = Paths.from_env()
    issue_certificate(paths)
    console.print("[green]Certificate is ready.[/green]")


def renew(force: bool = False) -> None:
    paths = Paths.from_env()
    if renew_certificate(paths, force=force):
        console.print("[green]Certificate renewed and services reloaded.[/green]")
    else:
        console.print("[green]Certificate is not due for renewal yet.[/green]")
    days = certificate_days_remaining(paths, load_settings(paths).domain)
    if days is not None:
        console.print(f"Expires in {days} days.")


def schedule(disable: bool = False) -> None:
    paths = Paths.from_env()
    cron_path = configure_renewal(paths, not disable)
    if cron_path is None:
        console.print(
            f"[yellow]Removed renewal schedule:[/yellow] {renewal_cron_path(paths)}"
        )
    else:
        console.print(f"[green]Renewal scheduled twice a day:[/green] {cron_path}")
