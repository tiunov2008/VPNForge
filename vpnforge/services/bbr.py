from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from vpnforge.config import Paths
from vpnforge.files import atomic_write
from vpnforge.shell import Runner, runner


BBR_CONFIG_NAME = "99-vpnforge-bbr.conf"
BBR_CONFIG = "net.core.default_qdisc=fq\nnet.ipv4.tcp_congestion_control=bbr\n"


@dataclass(frozen=True)
class BbrStatus:
    available: bool
    congestion_control: str
    default_qdisc: str

    @property
    def active(self) -> bool:
        return self.congestion_control == "bbr" and self.default_qdisc == "fq"


def bbr_config_path(paths: Paths) -> Path:
    return paths.sysctl_dir / BBR_CONFIG_NAME


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _sysctl_value(name: str, command_runner: Runner) -> str:
    result = command_runner.run(["sysctl", "-n", name], check=False, capture=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def bbr_status(command_runner: Runner = runner) -> BbrStatus:
    available = _sysctl_value(
        "net.ipv4.tcp_available_congestion_control", command_runner
    ).split()
    return BbrStatus(
        available="bbr" in available,
        congestion_control=_sysctl_value(
            "net.ipv4.tcp_congestion_control", command_runner
        ),
        default_qdisc=_sysctl_value("net.core.default_qdisc", command_runner),
    )


def apply_bbr(paths: Paths, command_runner: Runner = runner) -> BbrStatus:
    if not is_linux():
        raise RuntimeError("BBR can only be configured on Linux")
    if not is_root():
        raise RuntimeError("BBR configuration must run as root")

    status = bbr_status(command_runner)
    if not status.available:
        command_runner.run(["modprobe", "tcp_bbr"], check=False, capture=True)
        status = bbr_status(command_runner)
    if not status.available:
        raise RuntimeError("The running kernel does not provide TCP BBR")

    config_path = bbr_config_path(paths)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(config_path, BBR_CONFIG, mode=0o644)
    command_runner.run(["sysctl", "--system"])

    status = bbr_status(command_runner)
    if not status.active:
        raise RuntimeError(
            "BBR settings were written but are not active "
            f"(qdisc={status.default_qdisc or 'unknown'}, "
            f"congestion_control={status.congestion_control or 'unknown'})"
        )
    return status


def configure_bbr(
    paths: Paths, enabled: bool, command_runner: Runner = runner
) -> BbrStatus | None:
    if enabled:
        return apply_bbr(paths, command_runner)

    # Stop managing future boot settings without overriding an administrator's
    # currently active congestion-control choice.
    bbr_config_path(paths).unlink(missing_ok=True)
    return None
