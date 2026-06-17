from __future__ import annotations

from vpnforge.commands import uninstall
from vpnforge.shell import CommandResult


class RecordingRunner:
    def __init__(self):
        self.commands: list[list[str]] = []

    def run(self, command, **kwargs):
        self.commands.append(list(command))
        return CommandResult(0)


def test_purge_stops_containers_before_cleanup(monkeypatch, paths):
    paths.runtime_dir.mkdir(parents=True)
    paths.config_dir.mkdir(parents=True)
    paths.compose_file.parent.mkdir(parents=True)
    paths.compose_file.write_text("name: vpnforge\n", encoding="utf-8")
    monkeypatch.setattr(uninstall.Paths, "from_env", classmethod(lambda cls: paths))
    events: list[object] = []
    command_runner = RecordingRunner()
    monkeypatch.setattr(
        uninstall,
        "configure_bbr",
        lambda _paths, enabled: events.append(("bbr", enabled)),
    )

    uninstall.run(purge=True, command_runner=command_runner)

    assert command_runner.commands[0][:7] == [
        "docker",
        "compose",
        "--project-name",
        "vpnforge",
        "-f",
        str(paths.compose_file),
        "down",
    ]
    assert ["docker", "rm", "--force", *uninstall.CONTAINERS] in command_runner.commands
    assert ["docker", "network", "rm", "vpnforge"] in command_runner.commands
    assert events == [("bbr", False)]
    assert not paths.runtime_dir.exists()
    assert not paths.config_dir.exists()


def test_purge_removes_host_wrapper_when_available(monkeypatch, paths, tmp_path):
    paths.runtime_dir.mkdir(parents=True)
    paths.config_dir.mkdir(parents=True)
    monkeypatch.setattr(uninstall.Paths, "from_env", classmethod(lambda cls: paths))
    monkeypatch.setattr(uninstall, "configure_bbr", lambda *args: None)
    host_bin = tmp_path / "host-bin"
    host_bin.mkdir()
    wrapper = host_bin / "vpnforge"
    wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("VPNFORGE_HOST_BIN_DIR", str(host_bin))

    uninstall.run(purge=True, command_runner=RecordingRunner())

    assert not wrapper.exists()
