from __future__ import annotations

import pytest

from vpnforge.commands import update
from vpnforge.config import Paths, create_settings, ensure_directories, write_settings
from vpnforge.shell import CommandResult


class RecordingRunner:
    def __init__(self):
        self.commands: list[list[str]] = []

    def run(self, command, **kwargs):
        self.commands.append(list(command))
        return CommandResult(0)


def test_update_pulls_image_and_runs_fresh_cli_container(monkeypatch, tmp_path):
    paths = Paths(
        project_dir=tmp_path / "project",
        config_dir=tmp_path / "etc" / "vpnforge",
        runtime_dir=tmp_path / "var" / "lib" / "vpnforge",
    )
    ensure_directories(paths)
    write_settings(paths, create_settings("vpn.example.com", "admin@example.com"))
    monkeypatch.setattr(update.Paths, "from_env", classmethod(lambda cls: paths))
    monkeypatch.setattr(update, "is_root", lambda: True)
    monkeypatch.setenv("VPNFORGE_IMAGE", "example/vpnforge:test")
    command_runner = RecordingRunner()

    update.run(command_runner)

    assert command_runner.commands[0] == ["docker", "pull", "example/vpnforge:test"]
    fresh_cli = command_runner.commands[1]
    assert fresh_cli[:3] == ["docker", "run", "--rm"]
    assert "example/vpnforge:test" in fresh_cli
    assert fresh_cli[-5:] == [
        "install",
        "--domain",
        "vpn.example.com",
        "--email",
        "admin@example.com",
    ]


def test_update_requires_root(monkeypatch):
    monkeypatch.setattr(update, "is_root", lambda: False)

    with pytest.raises(RuntimeError, match="must run as root"):
        update.run(RecordingRunner())
