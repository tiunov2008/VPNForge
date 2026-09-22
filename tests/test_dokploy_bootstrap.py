from __future__ import annotations

import json

import pytest
import yaml

from vpnforge.config import load_settings, settings_from_environment
from vpnforge.dokploy import certs
from vpnforge.dokploy.bootstrap import apply_compose_profiles, bootstrap
from vpnforge.services.nginx import active_stage
from vpnforge.services.xray import load_secrets
from vpnforge.state import load_state


BASE_ENV = {
    "DOMAIN": "vpn.example.com",
    "COMPOSE_PROFILES": "hysteria",
}


@pytest.fixture(autouse=True)
def isolated_tls_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VPNFORGE_TLS_DIR", raising=False)
    monkeypatch.delenv("VPNFORGE_ACME_JSON", raising=False)


def test_bootstrap_renders_a_complete_stack(paths):
    settings = bootstrap(paths, BASE_ENV)

    assert settings.domain == "vpn.example.com"
    assert settings.email == "admin@vpn.example.com"
    # The environment is the source of truth, but it is mirrored to disk so the
    # rest of the CLI keeps working inside the container.
    assert load_settings(paths).domain == "vpn.example.com"

    assert json.loads((paths.xray_dir / "config.json").read_text(encoding="utf-8"))
    assert yaml.safe_load(
        (paths.hysteria_dir / "config.yaml").read_text(encoding="utf-8")
    )
    assert (paths.nginx_dir / "dokploy.conf").is_file()
    assert (paths.nginx_dir / "nginx.conf").is_file()
    assert active_stage(paths) == "dokploy"

    subscription_path = load_secrets(paths)["subscription_path"]
    for name in (
        "index.html",
        "config.html",
        "subscription.txt",
        f"{subscription_path}.hysteria.yaml",
    ):
        assert (paths.nginx_html_dir / name).is_file(), name

    state = load_state(paths)
    assert state["installed"] is True
    assert state["deployment"] == "dokploy"


def test_bootstrap_writes_a_placeholder_certificate(paths):
    bootstrap(paths, BASE_ENV)

    pair = certs.current_pair(paths.tls_dir)
    assert pair is not None
    assert pair.is_placeholder is True


def test_bootstrap_imports_an_existing_traefik_certificate(paths, monkeypatch):
    acme = paths.runtime_dir / "acme.json"
    acme.parent.mkdir(parents=True, exist_ok=True)
    acme.write_text(
        json.dumps(
            {
                "letsencrypt": {
                    "Certificates": [
                        {
                            "domain": {"main": "vpn.example.com"},
                            "certificate": "Q0hBSU4=",
                            "key": "S0VZ",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VPNFORGE_ACME_JSON", str(acme))

    bootstrap(paths, BASE_ENV)

    pair = certs.current_pair(paths.tls_dir)
    assert pair is not None
    assert pair.is_placeholder is False
    assert pair.fullchain == "CHAIN"


def test_bootstrap_keeps_secrets_stable_across_redeploys(paths):
    bootstrap(paths, BASE_ENV)
    first = load_secrets(paths)

    bootstrap(paths, BASE_ENV)

    # Regenerating these would invalidate every link already handed to clients.
    assert load_secrets(paths) == first


def test_bootstrap_renders_nginx_against_the_runtime_volume(paths):
    bootstrap(paths, BASE_ENV)

    config = (paths.nginx_dir / "dokploy.conf").read_text(encoding="utf-8")
    assert f"root {str(paths.nginx_html_dir).replace(chr(92), '/')};" in config
    assert "/etc/nginx/tls/fullchain.pem" in config
    # Container port 80 is free; only the host 80 belongs to Traefik.
    assert "listen 80;" in config
    # The Xray fallback listeners have to survive into the Dokploy variant.
    for listener in ("listen 8080 ssl proxy_protocol;", "listen 8081 proxy_protocol;"):
        assert listener in config

    main = (paths.nginx_dir / "nginx.conf").read_text(encoding="utf-8")
    assert str(paths.nginx_dir / "active.conf").replace("\\", "/") in main


def test_bootstrap_honours_port_and_title_overrides(paths):
    settings = bootstrap(
        paths,
        {
            **BASE_ENV,
            "XRAY_REALITY_PORT": "2053",
            "XRAY_TLS_PORT": "9443",
            "SUBSCRIPTION_TITLE": "Моя подписка",
        },
    )

    assert settings.xray_reality_port == 2053
    assert settings.xray_tls_port == 9443
    assert settings.subscription_title == "Моя подписка"
    links = (paths.nginx_html_dir / "subscription.txt").read_text(encoding="utf-8")
    assert ":2053?" in links
    assert ":9443?" in links


def test_bootstrap_without_hysteria(paths):
    settings = bootstrap(paths, {"DOMAIN": "vpn.example.com", "COMPOSE_PROFILES": ""})

    assert settings.enable_hysteria is False
    assert not (paths.hysteria_dir / "config.yaml").exists()
    # The TXT subscription never carries hysteria2:// links; the config page is
    # where they are published, so that is what has to lose them.
    assert "hysteria2://" not in (
        paths.nginx_html_dir / "config.html"
    ).read_text(encoding="utf-8")
    assert not list(paths.nginx_html_dir.glob("*.hysteria.yaml"))


def test_compose_profile_is_the_only_hysteria_switch(paths):
    # An empty profile list wins over ENABLE_HYSTERIA: Compose would not create
    # the container, so advertising Hysteria would hand clients a dead endpoint.
    off = bootstrap(
        paths,
        {
            "DOMAIN": "vpn.example.com",
            "COMPOSE_PROFILES": "",
            "ENABLE_HYSTERIA": "true",
        },
    )
    assert off.enable_hysteria is False

    # And an active profile wins the other way: the container would start with
    # no rendered config and crash-loop.
    on = bootstrap(
        paths,
        {
            "DOMAIN": "vpn.example.com",
            "COMPOSE_PROFILES": "hysteria",
            "ENABLE_HYSTERIA": "false",
        },
    )
    assert on.enable_hysteria is True
    assert (paths.hysteria_dir / "config.yaml").is_file()
    assert "hysteria2://" in (
        paths.nginx_html_dir / "config.html"
    ).read_text(encoding="utf-8")


def test_profiles_are_ignored_outside_compose():
    settings = settings_from_environment({"DOMAIN": "vpn.example.com"})

    # No COMPOSE_PROFILES at all means the caller is not Dokploy.
    assert apply_compose_profiles(settings, {}).enable_hysteria is True


def test_profile_list_is_parsed_as_a_comma_separated_list():
    settings = settings_from_environment(
        {"DOMAIN": "vpn.example.com", "ENABLE_HYSTERIA": "false"}
    )

    updated = apply_compose_profiles(settings, {"COMPOSE_PROFILES": "other, hysteria"})

    assert updated.enable_hysteria is True
    assert apply_compose_profiles(
        settings, {"COMPOSE_PROFILES": "other,unrelated"}
    ).enable_hysteria is False


def test_bootstrap_requires_a_domain(paths):
    with pytest.raises(ValueError, match="DOMAIN"):
        bootstrap(paths, {})
