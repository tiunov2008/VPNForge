from __future__ import annotations

from rich.console import Console

from vpnforge.config import (
    HysteriaPortRange,
    Paths,
    load_settings,
    parse_bool_setting,
    validate_subscription_title,
    write_settings,
)


console = Console()


def set_value(key: str, value: str) -> None:
    paths = Paths.from_env()
    settings = load_settings(paths)
    if key == "subscription-title":
        changes = {"subscription_title": validate_subscription_title(value)}
    elif key == "hysteria-enabled":
        changes = {"enable_hysteria": parse_bool_setting(value, "hysteria-enabled")}
    elif key == "hysteria-port-range":
        changes = {"hysteria_port_range": HysteriaPortRange.parse(value)}
    elif key == "bbr-enabled":
        changes = {"enable_bbr": parse_bool_setting(value, "bbr-enabled")}
    else:
        raise ValueError(f"Unknown setting: {key}")

    write_settings(
        paths,
        settings.model_copy(update=changes),
        force=True,
    )
    console.print(f"[green]Updated {key}:[/green] {value.strip()}")
