from __future__ import annotations

from vpnforge.services import installer
from vpnforge.shell import CommandResult


def test_full_install_workflow_order(monkeypatch, paths):
    events: list[str] = []
    forces: dict[str, object] = {}

    def generate_secrets(*args, **kwargs):
        forces["secrets"] = kwargs["force"]
        events.append("secrets")
        return []

    def render_xray(*args, **kwargs):
        forces["xray"] = kwargs["force"]
        events.append("xray-render")

    def render_nginx(_paths, stage, **kwargs):
        forces.setdefault("nginx", []).append(kwargs["force"])
        events.append(f"nginx-render-{stage}")

    monkeypatch.setattr(
        installer, "assert_install_environment", lambda *args: events.append("checks")
    )
    monkeypatch.setattr(
        installer,
        "generate_secrets",
        generate_secrets,
    )
    monkeypatch.setattr(
        installer,
        "render_xray",
        render_xray,
    )
    monkeypatch.setattr(
        installer,
        "render_nginx",
        render_nginx,
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

        def validate_xray(self):
            events.append("validate-xray")
            return CommandResult(0)

        def validate_nginx(self):
            events.append("validate-nginx")
            return CommandResult(0)

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
        "validate-xray",
        "recreate-xray",
        "nginx-use-final",
        "validate-nginx",
        "restart-nginx",
        "state",
        "doctor",
    ]
    assert forces == {"secrets": False, "xray": True, "nginx": [True, True]}
    assert paths.env_file.is_file()
