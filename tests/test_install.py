from __future__ import annotations

from vpnforge.services import installer


def test_full_install_workflow_order(monkeypatch, paths):
    events: list[str] = []

    monkeypatch.setattr(
        installer, "assert_install_environment", lambda *args: events.append("checks")
    )
    monkeypatch.setattr(
        installer,
        "generate_secrets",
        lambda *args, **kwargs: events.append("secrets") or [],
    )
    monkeypatch.setattr(
        installer, "render_xray", lambda *args, **kwargs: events.append("xray-render")
    )
    monkeypatch.setattr(
        installer,
        "render_nginx",
        lambda _paths, stage, **kwargs: events.append(f"nginx-render-{stage}"),
    )
    monkeypatch.setattr(
        installer,
        "use_nginx",
        lambda _paths, stage: events.append(f"nginx-use-{stage}"),
    )
    monkeypatch.setattr(
        installer, "issue_certificate", lambda *args: events.append("cert")
    )
    monkeypatch.setattr(
        installer, "update_state", lambda *args, **kwargs: events.append("state")
    )
    monkeypatch.setattr(
        installer, "run_doctor", lambda *args: events.append("doctor") or []
    )
    monkeypatch.setattr(
        installer,
        "template_context",
        lambda *args: {"subscription_url": "https://example.com/sub.txt"},
    )

    class FakeDocker:
        def __init__(self, _paths):
            pass

        def up(self, services):
            events.append("up-" + ",".join(services))

        def recreate(self, service):
            events.append("recreate-" + service)

        def restart(self, service):
            events.append("restart-" + service)

    monkeypatch.setattr(installer, "DockerCompose", FakeDocker)

    installer.install(paths, "example.com")

    assert events == [
        "checks",
        "secrets",
        "xray-render",
        "nginx-render-bootstrap",
        "nginx-use-bootstrap",
        "recreate-nginx",
        "cert",
        "nginx-render-final",
        "recreate-xray",
        "nginx-use-final",
        "restart-nginx",
        "state",
        "doctor",
    ]
    assert paths.env_file.is_file()
