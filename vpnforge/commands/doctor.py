from __future__ import annotations

import typer

from vpnforge.checks import print_checks, run_doctor
from vpnforge.config import Paths


def run() -> None:
    checks = run_doctor(Paths.from_env())
    print_checks(checks)
    if any(check.status == "FAIL" for check in checks):
        raise typer.Exit(1)
