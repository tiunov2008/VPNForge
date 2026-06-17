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
    monkeypatch.setattr(
        "vpnforge.cli.hysteria_command.render",
        lambda *args: calls.append("hysteria-render"),
    )
    monkeypatch.setattr("vpnforge.cli.bbr_command.apply", lambda: calls.append("bbr"))
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
        ["hysteria", "render"],
        ["bbr", "apply"],
        ["up", "nginx"],
        ["up", "hysteria"],
        ["down"],
        ["restart"],
        ["restart", "nginx"],
        ["restart", "hysteria"],
        ["logs", "xray"],
        ["logs", "hysteria"],
        ["doctor"],
        ["status"],
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
        "hysteria-render",
        "bbr",
        "up",
        "up",
        "down",
        "restart",
        "restart",
        "restart",
        "logs",
        "logs",
        "doctor",
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


def test_config_set_updates_hysteria_settings(path_environment):
    init_result = runner.invoke(app, ["init", "--domain", "example.com"])
    assert init_result.exit_code == 0, init_result.output

    enabled_result = runner.invoke(app, ["config", "set", "hysteria-enabled", "false"])
    range_result = runner.invoke(
        app, ["config", "set", "hysteria-port-range", "21000-22000"]
    )

    assert enabled_result.exit_code == 0, enabled_result.output
    assert range_result.exit_code == 0, range_result.output
    content = path_environment.env_file.read_text(encoding="utf-8")
    assert "ENABLE_HYSTERIA=false" in content
    assert "HYSTERIA_PORT_RANGE=21000-22000" in content


def test_config_set_updates_bbr_setting(path_environment):
    init_result = runner.invoke(app, ["init", "--domain", "example.com"])
    assert init_result.exit_code == 0, init_result.output

    result = runner.invoke(app, ["config", "set", "bbr-enabled", "true"])

    assert result.exit_code == 0, result.output
    assert "ENABLE_BBR=true" in path_environment.env_file.read_text(encoding="utf-8")
