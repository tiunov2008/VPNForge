from __future__ import annotations

import typer
from rich.console import Console

from vpnforge.config import Paths, settings_from_environment
from vpnforge.dokploy import certs
from vpnforge.dokploy.bootstrap import bootstrap, describe


console = Console()


def run_bootstrap() -> None:
    bootstrap(Paths.from_env(), console=console)


def run_info() -> None:
    describe(Paths.from_env(), console=console)


def run_certs(watch: bool, interval: float) -> None:
    if interval <= 0:
        raise ValueError("Interval must be greater than zero")
    paths = Paths.from_env()
    settings = settings_from_environment()
    acme_path = certs.acme_path_from_env()

    if not watch:
        if certs.sync_once(paths.tls_dir, settings.domain, acme_path):
            console.print(f"[green]Certificate updated[/green] in {paths.tls_dir}")
        else:
            console.print("[dim]Certificate already up to date[/dim]")
        return

    console.print(
        f"Watching {acme_path} for {settings.domain} every {interval:g}s"
    )
    # Xray and Hysteria do not reload a changed certificate on their own, so
    # report every replacement loudly: Dokploy surfaces these lines in the
    # service log and they are the cue to restart those two containers.
    seen_certificate = False

    def report(event: str, error: Exception | None) -> None:
        nonlocal seen_certificate
        if event == "updated":
            seen_certificate = True
            console.print(
                "[green]Certificate updated[/green] - restart the xray and "
                "hysteria containers to pick it up"
            )
        elif event == "unchanged" and not seen_certificate:
            seen_certificate = True
            console.print("[green]Certificate present and current[/green]")
        elif event == "pending":
            console.print(f"[yellow]Waiting for Traefik:[/yellow] {error}")
        elif event == "error":
            console.print(f"[red]Certificate sync failed:[/red] {error}")

    try:
        certs.watch(
            paths.tls_dir,
            settings.domain,
            acme_path,
            interval=interval,
            on_event=report,
        )
    except KeyboardInterrupt:  # pragma: no cover - signal handling
        raise typer.Exit(0)
