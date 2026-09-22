"""One-shot initialisation for the Dokploy deployment.

Dokploy re-clones the repository on every deploy and runs ``docker compose up``
directly, so there is no host-side CLI step to render configuration. This
module is what the ``init`` service runs instead: it turns the environment
variables set in the Dokploy UI into the same rendered configs the host
installer produces, storing them in named volumes that survive redeploys.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from rich.console import Console

from vpnforge.config import (
    Paths,
    Settings,
    ensure_directories,
    settings_from_environment,
    write_settings,
)
from vpnforge.dokploy import certs
from vpnforge.services.hysteria import render_hysteria
from vpnforge.services.nginx import render_nginx, use_nginx
from vpnforge.services.xray import (
    generate_reality_keypair,
    generate_secrets,
    render_xray,
    template_context,
)
from vpnforge.state import update_state


HYSTERIA_PROFILE = "hysteria"


def _active_profiles(environ: Mapping[str, str]) -> set[str]:
    raw = environ.get("COMPOSE_PROFILES", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def assert_profile_consistency(
    settings: Settings, environ: Mapping[str, str]
) -> None:
    """Fail when ENABLE_HYSTERIA and COMPOSE_PROFILES disagree.

    Compose decides whether the Hysteria container runs, while ENABLE_HYSTERIA
    decides whether the subscription advertises it. If they drift apart the
    deployment still comes up, but hands clients an endpoint that answers
    nothing -- so catch it here instead.
    """
    if "COMPOSE_PROFILES" not in environ:
        return
    enabled_by_profile = HYSTERIA_PROFILE in _active_profiles(environ)
    if settings.enable_hysteria and not enabled_by_profile:
        raise RuntimeError(
            "ENABLE_HYSTERIA is true but COMPOSE_PROFILES does not contain "
            f"'{HYSTERIA_PROFILE}', so the Hysteria container will not start "
            "while the subscription still advertises it. Add "
            f"COMPOSE_PROFILES={HYSTERIA_PROFILE} in the Dokploy Environment "
            "tab, or set ENABLE_HYSTERIA=false."
        )
    if not settings.enable_hysteria and enabled_by_profile:
        raise RuntimeError(
            f"COMPOSE_PROFILES contains '{HYSTERIA_PROFILE}' but "
            "ENABLE_HYSTERIA is false, so the Hysteria container would start "
            "without a rendered config. Remove the profile, or set "
            "ENABLE_HYSTERIA=true."
        )


def bootstrap(
    paths: Paths,
    environ: Mapping[str, str] | None = None,
    *,
    console: Console | None = None,
) -> Settings:
    console = console or Console()
    environ = os.environ if environ is None else environ

    settings = settings_from_environment(environ)
    assert_profile_consistency(settings, environ)

    ensure_directories(paths)
    # The Dokploy Environment tab is the single source of truth here, so the
    # mirrored env file is always rewritten rather than treated as user state.
    write_settings(paths, settings, force=True)

    generated = generate_secrets(paths, reality_keys=generate_reality_keypair)
    console.print(
        f"[green]Secrets ready[/green] ({len(generated)} generated, "
        f"stored in {paths.secrets_dir})"
    )

    if certs.ensure_placeholder(paths.tls_dir, settings.domain):
        console.print(
            "[yellow]No certificate yet[/yellow] - wrote a self-signed "
            "placeholder so Xray and Hysteria can start. The cert sidecar "
            "replaces it once Traefik completes the HTTP-01 challenge."
        )
    acme_path = certs.acme_path_from_env()
    try:
        if certs.sync_once(paths.tls_dir, settings.domain, acme_path):
            console.print(
                f"[green]Certificate imported[/green] from {acme_path}"
            )
    except certs.CertificateNotFound:
        console.print(f"[dim]Traefik has no certificate yet ({acme_path})[/dim]")
    except (ValueError, OSError) as error:
        console.print(f"[yellow]Certificate import skipped:[/yellow] {error}")

    # Rendered files are VPNForge-owned and may need migrating between
    # releases, so they are always rewritten. Settings and secrets are not.
    render_xray(paths, force=True)
    render_hysteria(paths, force=True)
    render_nginx(paths, "dokploy", force=True)
    use_nginx(paths, "dokploy")

    update_state(
        paths,
        installed=True,
        xray_enabled=settings.enable_xray,
        hysteria_enabled=settings.enable_hysteria,
        deployment="dokploy",
    )

    context = template_context(paths)
    console.print(f"[green]Configs rendered:[/green] {paths.generated_dir}")
    console.print(f"Subscription: {context['subscription_url']}")
    if context["hysteria_client_url"]:
        console.print(f"Hysteria client: {context['hysteria_client_url']}")
    return settings


def describe(paths: Paths, console: Console | None = None) -> None:
    """Print the subscription endpoints for an already-bootstrapped stack."""
    console = console or Console()
    context = template_context(paths)
    settings = context["settings"]
    console.rule("VPNForge on Dokploy")
    console.print(f"Domain: [bold]{settings.domain}[/bold]")
    console.print(f"Subscription: {context['subscription_url']}")
    console.print(
        f"Config page: https://{settings.domain}/"
        f"{context['secrets']['subscription_path']}.html"
    )
    if context["hysteria_client_url"]:
        console.print(f"Hysteria client: {context['hysteria_client_url']}")
    pair = certs.current_pair(paths.tls_dir)
    if pair is None:
        console.print("[red]Certificate: missing[/red]")
    elif pair.is_placeholder:
        console.print(
            "[yellow]Certificate: self-signed placeholder[/yellow] "
            "(Traefik has not issued yet)"
        )
    else:
        console.print("[green]Certificate: issued by Traefik[/green]")
