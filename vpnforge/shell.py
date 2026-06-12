from __future__ import annotations

import shlex
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console


console = Console()


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandError(RuntimeError):
    def __init__(self, command: Sequence[str], result: CommandResult):
        self.command = list(command)
        self.result = result
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit code {result.returncode}"
        )
        super().__init__(f"Command failed: {shlex.join(self.command)}: {message}")


class Runner:
    def run(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
        capture: bool = False,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        console.print(f"[dim]$ {shlex.join(command)}[/dim]")
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            text=True,
            capture_output=capture,
            check=False,
        )
        result = CommandResult(
            completed.returncode, completed.stdout or "", completed.stderr or ""
        )
        if check and result.returncode != 0:
            raise CommandError(command, result)
        return result


runner = Runner()
