from pathlib import Path

import yaml


def test_compose_files_do_not_contain_secrets():
    root = Path(__file__).resolve().parents[1]
    content = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "compose").glob("*.yml")
    )
    for forbidden in (
        "XRAY_UUID",
        "REALITY_PRIVATE_KEY",
        "REALITY_SHORT_ID",
        "xray_uuid",
        "hysteria_password",
        "hysteria_obfs_password",
    ):
        assert forbidden not in content


def test_compose_files_are_valid_yaml():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "compose").glob("*.yml"):
        assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict)


def test_hysteria_uses_host_network_and_net_admin():
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load(
        (root / "compose" / "compose.hysteria.yml").read_text(encoding="utf-8")
    )
    service = compose["services"]["hysteria"]

    assert service["network_mode"] == "host"
    assert service["cap_add"] == ["NET_ADMIN"]
    assert "ports" not in service
