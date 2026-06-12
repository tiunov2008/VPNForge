from __future__ import annotations

from enum import Enum

import typer

from vpnforge.commands import bbr as bbr_command
from vpnforge.commands import cert as cert_command
from vpnforge.commands import config as config_command
from vpnforge.commands import doctor as doctor_command
from vpnforge.commands import down as down_command
from vpnforge.commands import init as init_command
from vpnforge.commands import hysteria as hysteria_command
from vpnforge.commands import install as install_command
from vpnforge.commands import logs as logs_command
from vpnforge.commands import nginx as nginx_command
from vpnforge.commands import render as render_command
from vpnforge.commands import restart as restart_command
from vpnforge.commands import secrets as secrets_command
from vpnforge.commands import uninstall as uninstall_command
from vpnforge.commands import update as update_command
from vpnforge.commands import up as up_command
from vpnforge.commands import xray as xray_command
from vpnforge.commands.common import execute


app = typer.Typer(help="Deploy and operate VPNForge.", no_args_is_help=True)
config_app = typer.Typer(help="Manage VPNForge settings.")
secrets_app = typer.Typer(help="Manage secret files.")
nginx_app = typer.Typer(help="Render and activate Nginx configs.")
cert_app = typer.Typer(help="Manage Let's Encrypt certificates.")
xray_app = typer.Typer(help="Manage Xray configuration.")
hysteria_app = typer.Typer(help="Manage Hysteria 2 configuration.")
bbr_app = typer.Typer(help="Manage Linux TCP BBR settings.")

app.add_typer(config_app, name="config")
app.add_typer(secrets_app, name="secrets")
app.add_typer(nginx_app, name="nginx")
app.add_typer(cert_app, name="cert")
app.add_typer(xray_app, name="xray")
app.add_typer(hysteria_app, name="hysteria")
app.add_typer(bbr_app, name="bbr")


class Stage(str, Enum):
    bootstrap = "bootstrap"
    final = "final"


class ConfigKey(str, Enum):
    subscription_title = "subscription-title"
    hysteria_enabled = "hysteria-enabled"
    hysteria_port_range = "hysteria-port-range"
    bbr_enabled = "bbr-enabled"


@app.command("install")
def install(
    domain: str = typer.Option(..., "--domain"),
    email: str | None = typer.Option(None, "--email"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    execute(lambda: install_command.run(domain, email, force))


@app.command("init")
def init(
    domain: str = typer.Option(..., "--domain"),
    email: str | None = typer.Option(None, "--email"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    execute(lambda: init_command.run(domain, email, force))


@secrets_app.command("generate")
def secrets_generate(force: bool = typer.Option(False, "--force")) -> None:
    execute(lambda: secrets_command.run(force))


@config_app.command("set")
def config_set(
    key: ConfigKey = typer.Argument(...),
    value: str = typer.Argument(...),
) -> None:
    execute(lambda: config_command.set_value(key.value, value))


@app.command("render")
def render(force: bool = typer.Option(False, "--force")) -> None:
    execute(lambda: render_command.run(force))


@nginx_app.command("render")
def nginx_render(
    stage: Stage = typer.Option(..., "--stage"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    execute(lambda: nginx_command.render(stage.value, force))


@nginx_app.command("use")
def nginx_use(stage: Stage = typer.Argument(...)) -> None:
    execute(lambda: nginx_command.use(stage.value))


@cert_app.command("issue")
def cert_issue() -> None:
    execute(cert_command.issue)


@xray_app.command("render")
def xray_render(force: bool = typer.Option(False, "--force")) -> None:
    execute(lambda: xray_command.render(force))


@hysteria_app.command("render")
def hysteria_render(force: bool = typer.Option(False, "--force")) -> None:
    execute(lambda: hysteria_command.render(force))


@bbr_app.command("apply")
def bbr_apply() -> None:
    execute(bbr_command.apply)


@app.command("up")
def up(service: str | None = typer.Argument(None)) -> None:
    execute(lambda: up_command.run(service))


@app.command("down")
def down() -> None:
    execute(down_command.run)


@app.command("restart")
def restart(service: str = typer.Argument(...)) -> None:
    execute(lambda: restart_command.run(service))


@app.command("logs")
def logs(
    service: str | None = typer.Argument(None),
    follow: bool = typer.Option(False, "--follow", "-f"),
) -> None:
    execute(lambda: logs_command.run(service, follow))


@app.command("doctor")
def doctor() -> None:
    execute(doctor_command.run)


@app.command("update")
def update() -> None:
    execute(update_command.run)


@app.command("uninstall")
def uninstall(
    purge: bool = typer.Option(False, "--purge"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    if not yes and not typer.confirm("Remove VPNForge containers and runtime files?"):
        raise typer.Abort()
    execute(lambda: uninstall_command.run(purge))


if __name__ == "__main__":
    app()
