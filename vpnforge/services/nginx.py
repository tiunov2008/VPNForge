from __future__ import annotations

from typing import Literal

from vpnforge.config import Paths
from vpnforge.files import atomic_copy
from vpnforge.render import render_template, write_rendered
from vpnforge.services.xray import template_context
from vpnforge.state import update_state


NginxStage = Literal["bootstrap", "final"]


def stage_path(paths: Paths, stage: NginxStage):
    return paths.nginx_dir / f"{stage}.conf"


def render_nginx(paths: Paths, stage: NginxStage, *, force: bool = False) -> bool:
    if stage not in ("bootstrap", "final"):
        raise ValueError(f"Unknown nginx stage: {stage}")
    context = template_context(paths)
    changed = write_rendered(
        stage_path(paths, stage),
        render_template(paths, f"nginx/{stage}.conf.j2", context),
        force=force,
    )
    if stage == "final":
        web_outputs = [
            ("web/index.html.j2", "index.html"),
            ("web/config.html.j2", "config.html"),
            ("web/subscription.txt.j2", "subscription.txt"),
        ]
        settings = context["settings"]
        secrets = context["secrets"]
        hysteria_output = f"{secrets['subscription_path']}.hysteria.yaml"
        for stale in paths.nginx_html_dir.glob("*.hysteria.yaml"):
            if not settings.enable_hysteria or stale.name != hysteria_output:
                stale.unlink()
                changed = True
        if settings.enable_hysteria:
            web_outputs.append(("hysteria/client.yaml.j2", hysteria_output))
        for template_name, output_name in web_outputs:
            changed = (
                write_rendered(
                    paths.nginx_html_dir / output_name,
                    render_template(paths, template_name, context),
                    force=force,
                )
                or changed
            )
    return changed


def use_nginx(paths: Paths, stage: NginxStage) -> None:
    source = stage_path(paths, stage)
    if not source.is_file():
        raise FileNotFoundError(f"Nginx {stage} config is not rendered: {source}")
    atomic_copy(source, paths.nginx_dir / "active.conf")
    update_state(paths, nginx_stage=stage)


def active_stage(paths: Paths) -> str | None:
    active = paths.nginx_dir / "active.conf"
    if not active.is_file():
        return None
    active_content = active.read_text(encoding="utf-8")
    for stage in ("bootstrap", "final"):
        candidate = stage_path(paths, stage)
        if (
            candidate.is_file()
            and candidate.read_text(encoding="utf-8") == active_content
        ):
            return stage
    return "custom"
