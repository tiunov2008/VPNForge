from __future__ import annotations

import os

from vpnforge.services.certbot import sync_xray_certificate, xray_certificate_path
from vpnforge.services.xray import XRAY_RUNTIME_GID, XRAY_RUNTIME_UID


def test_sync_xray_certificate_copies_files_with_runtime_permissions(paths):
    live = paths.certbot_conf_dir / "live" / "vpn.example.com"
    live.mkdir(parents=True)
    (live / "fullchain.pem").write_text("certificate\n", encoding="utf-8")
    (live / "privkey.pem").write_text("private-key\n", encoding="utf-8")

    sync_xray_certificate(paths, "vpn.example.com")

    fullchain, privkey = xray_certificate_path(paths)
    assert fullchain.read_text(encoding="utf-8") == "certificate\n"
    assert privkey.read_text(encoding="utf-8") == "private-key\n"

    if os.name == "posix":
        assert fullchain.stat().st_mode & 0o777 == 0o600
        assert privkey.stat().st_mode & 0o777 == 0o600
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            assert fullchain.stat().st_uid == XRAY_RUNTIME_UID
            assert privkey.stat().st_gid == XRAY_RUNTIME_GID
