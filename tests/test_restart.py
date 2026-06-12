from __future__ import annotations

from vpnforge.commands import restart
from vpnforge.config import ensure_directories, write_settings
from vpnforge.config import create_settings


def test_restart_hysteria_syncs_certificate(monkeypatch, path_environment):
    paths = path_environment
    ensure_directories(paths)
    settings = create_settings("vpn.example.com")
    write_settings(paths, settings)
    (paths.hysteria_dir / "config.yaml").write_text("listen: :20000-50000\n")
    events: list[object] = []

    monkeypatch.setattr(restart, "certificate_exists", lambda *args: True)
    monkeypatch.setattr(
        restart,
        "sync_hysteria_certificate",
        lambda *args: events.append("sync"),
    )

    class FakeDocker:
        def __init__(self, _paths):
            pass

        def restart(self, service):
            events.append(("restart", service))

    monkeypatch.setattr(restart, "DockerCompose", FakeDocker)

    restart.run("hysteria")

    assert events == ["sync", ("restart", "hysteria")]
