from __future__ import annotations

import json
from typing import Any

from vpnforge.config import Paths
from vpnforge.files import atomic_write


DEFAULT_STATE: dict[str, Any] = {
    "nginx_stage": None,
    "certificate_issued": False,
    "xray_enabled": True,
    "hysteria_enabled": True,
    "installed": False,
}


def load_state(paths: Paths) -> dict[str, Any]:
    if not paths.state_file.is_file():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(paths.state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)
    return {**DEFAULT_STATE, **data}


def update_state(paths: Paths, **changes: Any) -> dict[str, Any]:
    state = load_state(paths)
    state.update(changes)
    atomic_write(
        paths.state_file, json.dumps(state, indent=2, sort_keys=True) + "\n", mode=0o600
    )
    return state
