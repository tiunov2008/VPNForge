from __future__ import annotations

import os
import stat

import pytest

from vpnforge.config import (
    HysteriaPortRange,
    Settings,
    create_settings,
    ensure_directories,
    load_settings,
    write_settings,
)


def test_settings_and_directories_are_idempotent(paths):
    ensure_directories(paths)
    settings = create_settings("Example.COM")

    assert write_settings(paths, settings) is True
    assert "SUBSCRIPTION_TITLE=VPNForge" in paths.env_file.read_text(encoding="utf-8")
    assert write_settings(paths, create_settings("other.example")) is False
    assert load_settings(paths).domain == "example.com"
    assert load_settings(paths).email == "admin@example.com"
    assert load_settings(paths).enable_hysteria is True
    assert str(load_settings(paths).hysteria_port_range) == "20000-50000"
    assert load_settings(paths).enable_bbr is False
    if os.name == "posix":
        assert stat.S_IMODE(paths.secrets_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(paths.env_file.stat().st_mode) == 0o600

    assert write_settings(paths, create_settings("other.example"), force=True) is True
    assert load_settings(paths).domain == "other.example"


def test_subscription_title_round_trips_unicode_and_defaults_for_old_config(paths):
    ensure_directories(paths)
    settings = create_settings("example.com").model_copy(
        update={"subscription_title": "Моя подписка"}
    )
    write_settings(paths, settings)

    assert 'SUBSCRIPTION_TITLE="Моя подписка"' in paths.env_file.read_text(
        encoding="utf-8"
    )
    assert load_settings(paths).subscription_title == "Моя подписка"

    legacy = (
        settings.as_env()
        .replace('SUBSCRIPTION_TITLE="Моя подписка"\n', "")
        .replace("ENABLE_HYSTERIA=true\n", "")
        .replace("HYSTERIA_PORT_RANGE=20000-50000\n", "")
        .replace("ENABLE_BBR=false\n", "")
    )
    paths.env_file.write_text(legacy, encoding="utf-8")
    assert load_settings(paths).subscription_title == "VPNForge"
    assert load_settings(paths).enable_hysteria is True
    assert str(load_settings(paths).hysteria_port_range) == "20000-50000"
    assert load_settings(paths).enable_bbr is False


def test_env_values_are_not_interpolated(paths):
    ensure_directories(paths)
    paths.env_file.write_text(
        "DOMAIN=example.com\n"
        "EMAIL=admin@example.com\n"
        "SUBSCRIPTION_TITLE=${DOMAIN}\n",
        encoding="utf-8",
    )

    assert load_settings(paths).subscription_title == "${DOMAIN}"


def test_hysteria_settings_round_trip_and_validate(paths):
    ensure_directories(paths)
    settings = create_settings("example.com").model_copy(
        update={
            "enable_hysteria": False,
            "hysteria_port_range": HysteriaPortRange(start=21000, end=22000),
        }
    )
    write_settings(paths, settings)

    loaded = load_settings(paths)
    assert loaded.enable_hysteria is False
    assert loaded.hysteria_port_range == HysteriaPortRange(21000, 22000)

    with pytest.raises(ValueError):
        HysteriaPortRange.parse("50000-20000")
    with pytest.raises(ValueError):
        HysteriaPortRange.parse("0-20000")


@pytest.mark.parametrize("domain", ["", "localhost", "bad", "-bad.com", "bad-.com"])
def test_invalid_domains_are_rejected(domain):
    with pytest.raises(ValueError):
        create_settings(domain)


def test_invalid_email_is_rejected(paths):
    with pytest.raises(ValueError):
        create_settings("example.com", "bad@")

    ensure_directories(paths)
    paths.env_file.write_text(
        create_settings("example.com").as_env().replace(
            "EMAIL=admin@example.com\n", "EMAIL=bad@\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_settings(paths)


def test_settings_validate_bool_and_port_values(paths):
    ensure_directories(paths)
    paths.env_file.write_text(
        create_settings("example.com")
        .as_env()
        .replace("ENABLE_XRAY=true\n", "ENABLE_XRAY=false\n")
        .replace("NGINX_HTTP_PORT=80\n", "NGINX_HTTP_PORT=8080\n"),
        encoding="utf-8",
    )
    loaded = load_settings(paths)
    assert loaded.enable_xray is False
    assert loaded.nginx_http_port == 8080

    with pytest.raises(ValueError):
        Settings(domain="example.com", email="admin@example.com", nginx_http_port=0)
