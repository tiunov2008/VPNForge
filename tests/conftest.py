from __future__ import annotations

from pathlib import Path

import pytest

from vpnforge.config import Paths


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    project_dir = Path(__file__).resolve().parents[1]
    return Paths(
        project_dir=project_dir,
        config_dir=tmp_path / "etc" / "vpnforge",
        runtime_dir=tmp_path / "var" / "lib" / "vpnforge",
    )


@pytest.fixture(autouse=True)
def isolated_cron_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Keep the renewal job out of the real /etc/cron.d during tests."""
    cron_dir = tmp_path / "etc" / "cron.d"
    cron_dir.mkdir(parents=True)
    monkeypatch.setenv("VPNFORGE_CRON_DIR", str(cron_dir))
    return cron_dir


@pytest.fixture
def path_environment(monkeypatch: pytest.MonkeyPatch, paths: Paths) -> Paths:
    monkeypatch.setenv("VPNFORGE_PROJECT_DIR", str(paths.project_dir))
    monkeypatch.setenv("VPNFORGE_CONFIG_DIR", str(paths.config_dir))
    monkeypatch.setenv("VPNFORGE_RUNTIME_DIR", str(paths.runtime_dir))
    return paths
