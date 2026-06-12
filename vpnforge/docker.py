from __future__ import annotations

import os

from vpnforge.config import Paths, Settings, load_settings
from vpnforge.shell import CommandResult, Runner, runner


COMPOSE_FILES = (
    "compose.base.yml",
    "compose.nginx.yml",
    "compose.certbot.yml",
    "compose.xray.yml",
    "compose.hysteria.yml",
)


class DockerCompose:
    def __init__(self, paths: Paths, command_runner: Runner = runner):
        self.paths = paths
        self.runner = command_runner

    def command(self, *arguments: str) -> list[str]:
        command = ["docker", "compose", "--project-name", "vpnforge"]
        for filename in COMPOSE_FILES:
            command.extend(["-f", str(self.paths.compose_dir / filename)])
        command.extend(arguments)
        return command

    def environment(self, settings: Settings | None = None) -> dict[str, str]:
        if settings is None and self.paths.env_file.is_file():
            settings = load_settings(self.paths)
        return {
            **os.environ,
            "VPNFORGE_RUNTIME_DIR": str(self.paths.runtime_dir),
            "VPNFORGE_NGINX_HTTP_PORT": str(
                settings.nginx_http_port if settings else 80
            ),
            "VPNFORGE_XRAY_REALITY_PORT": str(
                settings.xray_reality_port if settings else 443
            ),
            "VPNFORGE_XRAY_TLS_PORT": str(settings.xray_tls_port if settings else 8443),
        }

    def run(
        self,
        *arguments: str,
        check: bool = True,
        capture: bool = False,
        settings: Settings | None = None,
    ) -> CommandResult:
        return self.runner.run(
            self.command(*arguments),
            check=check,
            capture=capture,
            cwd=self.paths.project_dir,
            env=self.environment(settings),
        )

    def up(self, services: list[str] | None = None) -> None:
        self.run("up", "-d", *(services or []))

    def down(self) -> None:
        self.run("down", "--remove-orphans")

    def restart(self, service: str) -> None:
        self.recreate(service)

    def recreate(self, service: str) -> None:
        self.run("up", "-d", "--force-recreate", "--no-deps", service)

    def remove(self, service: str) -> None:
        self.run("rm", "--stop", "--force", service, check=False)

    def logs(self, service: str | None = None, *, follow: bool = False) -> None:
        args = ["logs"]
        if follow:
            args.append("--follow")
        if service:
            args.append(service)
        self.run(*args)

    def recent_logs(self, service: str, *, tail: int = 50) -> CommandResult:
        return self.run(
            "logs",
            "--no-color",
            "--tail",
            str(tail),
            service,
            check=False,
            capture=True,
        )

    def is_running(self, service: str, settings: Settings | None = None) -> bool:
        result = self.run(
            "ps",
            "--status",
            "running",
            "--services",
            check=False,
            capture=True,
            settings=settings,
        )
        return service in result.stdout.splitlines()

    def exec(self, service: str, *command: str, check: bool = True) -> CommandResult:
        return self.run("exec", "-T", service, *command, check=check, capture=True)

    def validate_nginx(self) -> CommandResult:
        return self.run(
            "run",
            "--rm",
            "--no-deps",
            "nginx",
            "nginx",
            "-t",
            check=False,
            capture=True,
        )

    def validate_xray(self) -> CommandResult:
        return self.run(
            "run",
            "--rm",
            "--no-deps",
            "xray",
            "run",
            "-test",
            "-config",
            "/etc/xray/config.json",
            check=False,
            capture=True,
        )


def compose_files_exist(paths: Paths) -> bool:
    return all((paths.compose_dir / filename).is_file() for filename in COMPOSE_FILES)
