from __future__ import annotations

import os
import subprocess
import urllib.request
from pathlib import Path

import pytest

from vpnforge.config import Paths, Settings, ensure_directories, write_settings
from vpnforge.docker import DockerCompose
from vpnforge.services.nginx import render_nginx, use_nginx
from vpnforge.services.xray import generate_secrets, render_xray


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("VPNFORGE_RUN_INTEGRATION") != "1" or os.name != "posix",
        reason="set VPNFORGE_RUN_INTEGRATION=1 on a Linux Docker host",
    ),
]


def test_compose_nginx_xray_and_webroot(tmp_path: Path):
    project_dir = Path(__file__).resolve().parents[2]
    paths = Paths(project_dir, tmp_path / "etc", tmp_path / "runtime")
    settings = Settings(
        domain="vpnforge.test",
        email="admin@vpnforge.test",
        nginx_http_port=18080,
        xray_reality_port=18443,
        xray_tls_port=18444,
    )
    ensure_directories(paths)
    write_settings(paths, settings)
    generate_secrets(paths)

    live = paths.certbot_conf_dir / "live" / settings.domain
    live.mkdir(parents=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            f"/CN={settings.domain}",
            "-keyout",
            str(live / "privkey.pem"),
            "-out",
            str(live / "fullchain.pem"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    render_xray(paths)
    render_nginx(paths, "final")
    use_nginx(paths, "final")
    challenge = paths.certbot_www_dir / ".well-known" / "acme-challenge" / "probe"
    challenge.parent.mkdir(parents=True)
    challenge.write_text("vpnforge-ok\n", encoding="utf-8")

    docker = DockerCompose(paths)
    try:
        docker.up(["nginx", "xray"])
        assert docker.exec("nginx", "nginx", "-t").returncode == 0
        assert (
            docker.exec(
                "xray", "xray", "run", "-test", "-config", "/etc/xray/config.json"
            ).returncode
            == 0
        )
        with urllib.request.urlopen(
            "http://127.0.0.1:18080/.well-known/acme-challenge/probe",
            timeout=10,
        ) as response:
            assert response.read() == b"vpnforge-ok\n"
    finally:
        docker.down()
