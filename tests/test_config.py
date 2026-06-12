from __future__ import annotations

import os
import stat
from dataclasses import replace

from vpnforge.config import (
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
    if os.name == "posix":
        assert stat.S_IMODE(paths.secrets_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(paths.env_file.stat().st_mode) == 0o600

    assert write_settings(paths, create_settings("other.example"), force=True) is True
    assert load_settings(paths).domain == "other.example"


def test_subscription_title_round_trips_unicode_and_defaults_for_old_config(paths):
    ensure_directories(paths)
    settings = replace(
        create_settings("example.com"), subscription_title="Моя подписка"
    )
    write_settings(paths, settings)

    assert 'SUBSCRIPTION_TITLE="Моя подписка"' in paths.env_file.read_text(
        encoding="utf-8"
    )
    assert load_settings(paths).subscription_title == "Моя подписка"

    legacy = settings.as_env().replace('SUBSCRIPTION_TITLE="Моя подписка"\n', "")
    paths.env_file.write_text(legacy, encoding="utf-8")
    assert load_settings(paths).subscription_title == "VPNForge"
