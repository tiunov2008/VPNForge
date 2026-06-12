from __future__ import annotations

from dataclasses import replace

from rich.console import Console

from vpnforge.config import (
    Paths,
    load_settings,
    validate_subscription_title,
    write_settings,
)


console = Console()


def set_value(key: str, value: str) -> None:
    paths = Paths.from_env()
    settings = load_settings(paths)
    if key != "subscription-title":
        raise ValueError(f"Unknown setting: {key}")

    title = validate_subscription_title(value)
    write_settings(
        paths,
        replace(settings, subscription_title=title),
        force=True,
    )
    console.print(f"[green]Updated subscription title:[/green] {title}")
