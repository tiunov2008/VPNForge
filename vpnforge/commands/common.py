from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import typer
from rich.console import Console


console = Console()
T = TypeVar("T")


def execute(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except typer.Exit:
        raise
    except Exception as error:
        console.print(f"[red]Error:[/red] {error}")
        raise typer.Exit(1) from error
