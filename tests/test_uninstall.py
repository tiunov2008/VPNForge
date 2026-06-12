from __future__ import annotations

from vpnforge.commands import uninstall


def test_purge_stops_bbr_management(monkeypatch, paths):
    paths.runtime_dir.mkdir(parents=True)
    paths.config_dir.mkdir(parents=True)
    events: list[object] = []

    class FakeDocker:
        def __init__(self, _paths):
            pass

        def down(self):
            events.append("down")

    monkeypatch.setattr(uninstall, "DockerCompose", FakeDocker)
    monkeypatch.setattr(
        uninstall,
        "configure_bbr",
        lambda _paths, enabled: events.append(("bbr", enabled)),
    )

    uninstall.run(purge=True)

    assert events == ["down", ("bbr", False)]
