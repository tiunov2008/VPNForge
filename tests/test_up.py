from __future__ import annotations

from vpnforge.commands import up
from vpnforge.config import Settings, ensure_directories, write_settings


def test_up_removes_disabled_hysteria(monkeypatch, path_environment):
    paths = path_environment
    ensure_directories(paths)
    write_settings(
        paths,
        Settings(
            domain="vpn.example.com",
            email="admin@vpn.example.com",
            enable_xray=False,
            enable_hysteria=False,
        ),
    )
    (paths.nginx_dir / "active.conf").write_text("server {}\n", encoding="utf-8")
    events: list[object] = []

    class FakeDocker:
        def __init__(self, _paths):
            pass

        def remove(self, service):
            events.append(("remove", service))

        def up(self, services):
            events.append(("up", services))

    monkeypatch.setattr(up, "DockerCompose", FakeDocker)

    up.run(None)

    assert events == [("remove", "hysteria"), ("up", ["nginx"])]
