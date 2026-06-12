from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from vpnforge.config import Paths
from vpnforge.files import atomic_write


def environment(paths: Paths) -> Environment:
    return Environment(
        loader=FileSystemLoader(paths.templates_dir),
        undefined=StrictUndefined,
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"), default_for_string=False
        ),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(paths: Paths, template_name: str, context: dict[str, Any]) -> str:
    return environment(paths).get_template(template_name).render(**context)


def write_rendered(
    path: Path, content: str, *, force: bool = False, mode: int = 0o644
) -> bool:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return False
        if not force:
            raise FileExistsError(
                f"Refusing to overwrite changed file without --force: {path}"
            )
    atomic_write(path, content, mode=mode)
    return True
