from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

from vpnforge.config import Paths
from vpnforge.docker import DockerCompose


console = Console()


def _remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
        raise RuntimeError(f"Refusing to remove unsafe path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def run(purge: bool) -> None:
    paths = Paths.from_env()
    DockerCompose(paths).down()
    _remove_tree(paths.runtime_dir)
    console.print(f"[green]Removed runtime data:[/green] {paths.runtime_dir}")
    if purge:
        _remove_tree(paths.config_dir)
        console.print(
            f"[green]Removed settings and secrets:[/green] {paths.config_dir}"
        )
    else:
        console.print(
            f"[yellow]Preserved settings and secrets:[/yellow] {paths.config_dir}"
        )
