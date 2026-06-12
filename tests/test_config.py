from __future__ import annotations

import os
import stat

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
    assert write_settings(paths, create_settings("other.example")) is False
    assert load_settings(paths).domain == "example.com"
    assert load_settings(paths).email == "admin@example.com"
    if os.name == "posix":
        assert stat.S_IMODE(paths.secrets_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(paths.env_file.stat().st_mode) == 0o600

    assert write_settings(paths, create_settings("other.example"), force=True) is True
    assert load_settings(paths).domain == "other.example"
