from __future__ import annotations

from rich.console import Console

from vpnforge.checks import assert_install_environment, print_checks, run_doctor
from vpnforge.config import (
    Paths,
    create_settings,
    ensure_directories,
    load_settings,
    write_settings,
)
from vpnforge.docker import DockerCompose
from vpnforge.services.certbot import issue_certificate
from vpnforge.services.nginx import render_nginx, use_nginx
from vpnforge.services.xray import generate_secrets, render_xray, template_context
from vpnforge.state import update_state


console = Console()


def initialize(
    paths: Paths, domain: str, email: str | None = None, *, force: bool = False
) -> bool:
    ensure_directories(paths)
    settings = create_settings(domain, email)
    return write_settings(paths, settings, force=force)


def install(
    paths: Paths, domain: str, email: str | None = None, *, force: bool = False
) -> None:
    settings = create_settings(domain, email)
    assert_install_environment(paths, settings)
    console.rule("VPNForge initialization")
    ensure_directories(paths)
    settings_written = write_settings(paths, settings, force=force)
    if not settings_written:
        existing = load_settings(paths)
        if existing.domain != settings.domain or existing.email != settings.email:
            raise RuntimeError(
                f"Existing settings use {existing.domain} / {existing.email}; rerun with --force to replace them"
            )
    generated = generate_secrets(paths, force=force)
    console.print(f"[green]Secrets ready[/green] ({len(generated)} generated)")

    # Generated runtime files are owned by VPNForge and may need migrations
    # between releases. User settings and secrets still require --force.
    render_xray(paths, force=True)
    render_nginx(paths, "bootstrap", force=True)
    use_nginx(paths, "bootstrap")

    docker = DockerCompose(paths)
    docker.recreate("nginx")
    issue_certificate(paths, docker)

    render_nginx(paths, "final", force=True)
    xray_validation = docker.validate_xray()
    if xray_validation.returncode != 0:
        details = xray_validation.stderr.strip() or xray_validation.stdout.strip()
        raise RuntimeError(f"Xray config validation failed:\n{details}")
    docker.recreate("xray")
    use_nginx(paths, "final")
    nginx_validation = docker.validate_nginx()
    if nginx_validation.returncode != 0:
        use_nginx(paths, "bootstrap")
        details = nginx_validation.stderr.strip() or nginx_validation.stdout.strip()
        raise RuntimeError(f"Nginx final config validation failed:\n{details}")
    docker.restart("nginx")
    update_state(paths, installed=True, xray_enabled=True)

    checks = run_doctor(paths)
    print_checks(checks, console)
    failures = [check for check in checks if check.status == "FAIL"]
    if failures:
        raise RuntimeError("Installation completed with failed diagnostics")

    context = template_context(paths)
    console.rule("VPNForge installed")
    console.print(f"Domain: [bold]{domain}[/bold]")
    console.print(f"Configs: {paths.generated_dir}")
    console.print(f"Secrets: {paths.secrets_dir}")
    console.print(f"Subscription: {context['subscription_url']}")
    console.print("Logs: vpnforge logs nginx / vpnforge logs xray")
    console.print("Diagnostics: vpnforge doctor")
