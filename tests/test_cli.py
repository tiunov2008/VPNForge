from __future__ import annotations

from typer.testing import CliRunner

from vpnforge.cli import app


runner = CliRunner()


def test_cli_dispatches_all_public_commands(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "vpnforge.cli.install_command.run", lambda *args: calls.append("install")
    )
    monkeypatch.setattr(
        "vpnforge.cli.init_command.run", lambda *args: calls.append("init")
    )
    monkeypatch.setattr(
        "vpnforge.cli.config_command.set_value", lambda *args: calls.append("config")
    )
    monkeypatch.setattr(
        "vpnforge.cli.secrets_command.run", lambda *args: calls.append("secrets")
    )
    monkeypatch.setattr(
        "vpnforge.cli.render_command.run", lambda *args: calls.append("render")
    )
    monkeypatch.setattr(
        "vpnforge.cli.nginx_command.render", lambda *args: calls.append("nginx-render")
    )
    monkeypatch.setattr(
        "vpnforge.cli.nginx_command.use", lambda *args: calls.append("nginx-use")
    )
    monkeypatch.setattr("vpnforge.cli.cert_command.issue", lambda: calls.append("cert"))
    monkeypatch.setattr(
        "vpnforge.cli.xray_command.render", lambda *args: calls.append("xray-render")
    )
    monkeypatch.setattr("vpnforge.cli.up_command.run", lambda *args: calls.append("up"))
    monkeypatch.setattr("vpnforge.cli.down_command.run", lambda: calls.append("down"))
    monkeypatch.setattr(
        "vpnforge.cli.restart_command.run", lambda *args: calls.append("restart")
    )
    monkeypatch.setattr(
        "vpnforge.cli.logs_command.run", lambda *args: calls.append("logs")
    )
    monkeypatch.setattr(
        "vpnforge.cli.doctor_command.run", lambda: calls.append("doctor")
    )
    monkeypatch.setattr(
        "vpnforge.cli.uninstall_command.run", lambda *args: calls.append("uninstall")
    )
    monkeypatch.setattr(
        "vpnforge.cli.update_command.run", lambda: calls.append("update")
    )

    commands = [
        ["install", "--domain", "example.com"],
        ["init", "--domain", "example.com"],
        ["config", "set", "subscription-title", "My VPN"],
        ["secrets", "generate"],
        ["render"],
        ["nginx", "render", "--stage", "bootstrap"],
        ["nginx", "use", "final"],
        ["cert", "issue"],
        ["xray", "render"],
        ["up", "nginx"],
        ["down"],
        ["restart", "nginx"],
        ["logs", "xray"],
        ["doctor"],
        ["update"],
        ["uninstall", "--yes"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code == 0, (command, result.output, result.exception)

    assert calls == [
        "install",
        "init",
        "config",
        "secrets",
        "render",
        "nginx-render",
        "nginx-use",
        "cert",
        "xray-render",
        "up",
        "down",
        "restart",
        "logs",
        "doctor",
        "update",
        "uninstall",
    ]


def test_init_command_uses_redirected_paths(path_environment):
    result = runner.invoke(app, ["init", "--domain", "example.com"])
    assert result.exit_code == 0, result.output
    assert path_environment.env_file.is_file()


def test_config_set_updates_subscription_title(path_environment):
    init_result = runner.invoke(app, ["init", "--domain", "example.com"])
    assert init_result.exit_code == 0, init_result.output

    result = runner.invoke(
        app,
        ["config", "set", "subscription-title", "Моя подписка"],
    )

    assert result.exit_code == 0, result.output
    assert 'SUBSCRIPTION_TITLE="Моя подписка"' in path_environment.env_file.read_text(
        encoding="utf-8"
    )
