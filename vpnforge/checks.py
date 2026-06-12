from __future__ import annotations

import json
import os
import shutil
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from rich.console import Console

from vpnforge.config import Paths, load_settings
from vpnforge.docker import DockerCompose, compose_files_exist
from vpnforge.services.certbot import certificate_exists
from vpnforge.services.nginx import active_stage
from vpnforge.services.xray import SECRET_NAMES, secret_path
from vpnforge.shell import runner


@dataclass(frozen=True)
class Check:
    status: str
    message: str


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def docker_available() -> bool:
    return shutil.which("docker") is not None


def compose_available() -> bool:
    if not docker_available():
        return False
    return (
        runner.run(
            ["docker", "compose", "version"], check=False, capture=True
        ).returncode
        == 0
    )


def public_ip() -> str | None:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as response:
            return response.read().decode("ascii").strip()
    except (OSError, urllib.error.URLError):
        return None


def domain_addresses(domain: str) -> set[str]:
    try:
        return {item[4][0] for item in socket.getaddrinfo(domain, None, socket.AF_INET)}
    except socket.gaierror:
        return set()


def challenge_reachable(domain: str) -> bool:
    request = urllib.request.Request(
        f"http://{domain}/.well-known/acme-challenge/vpnforge-doctor",
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status < 500
    except urllib.error.HTTPError as error:
        return error.code < 500
    except (OSError, urllib.error.URLError):
        return False


def assert_install_environment(paths: Paths, settings=None) -> None:
    failures: list[str] = []
    if not is_root():
        failures.append("VPNForge must run as root")
    if not docker_available():
        failures.append("Docker is not installed")
    elif not compose_available():
        failures.append("Docker Compose plugin is unavailable")
    if not compose_files_exist(paths):
        failures.append(f"Compose files are missing from {paths.compose_dir}")
    if settings is not None or paths.env_file.is_file():
        settings = settings or load_settings(paths)
        docker = DockerCompose(paths) if docker_available() else None
        expected = {
            settings.nginx_http_port: "nginx",
            settings.xray_reality_port: "xray",
            settings.xray_tls_port: "xray",
        }
        for port, service in expected.items():
            if not port_available(port) and not (
                docker and docker.is_running(service, settings)
            ):
                failures.append(f"Port {port} is already used by another process")
    if failures:
        raise RuntimeError("; ".join(failures))


def print_checks(checks: list[Check], console: Console | None = None) -> None:
    console = console or Console()
    colors = {"OK": "green", "WARN": "yellow", "FAIL": "red"}
    for check in checks:
        color = colors.get(check.status, "white")
        console.print(f"[{color}][{check.status}][/{color}] {check.message}")


def _command_details(stdout: str, stderr: str) -> str:
    return (stderr.strip() or stdout.strip()).replace("\n", " | ")


def run_doctor(paths: Paths) -> list[Check]:
    checks: list[Check] = []
    checks.append(Check("OK" if is_root() else "FAIL", "Running as root"))
    checks.append(Check("OK" if docker_available() else "FAIL", "Docker installed"))
    checks.append(
        Check("OK" if compose_available() else "FAIL", "Docker Compose available")
    )
    checks.append(
        Check("OK" if compose_files_exist(paths) else "FAIL", "Compose files available")
    )
    checks.append(
        Check(
            "OK" if paths.env_file.is_file() else "FAIL",
            f"Settings file: {paths.env_file}",
        )
    )

    try:
        settings = load_settings(paths)
    except (FileNotFoundError, ValueError) as error:
        checks.append(Check("FAIL", str(error)))
        return checks

    missing_secrets = [
        name for name in SECRET_NAMES if not secret_path(paths, name).is_file()
    ]
    checks.append(
        Check(
            "FAIL" if missing_secrets else "OK",
            "Secrets present"
            if not missing_secrets
            else f"Missing secrets: {', '.join(missing_secrets)}",
        )
    )
    if not missing_secrets:
        insecure = [
            name
            for name in SECRET_NAMES
            if secret_path(paths, name).stat().st_mode & 0o077
        ]
        checks.append(
            Check(
                "WARN" if insecure else "OK",
                "Secret permissions are 0600"
                if not insecure
                else f"Insecure secret permissions: {', '.join(insecure)}",
            )
        )
        if hasattr(os, "geteuid"):
            wrong_owner = [
                name
                for name in SECRET_NAMES
                if secret_path(paths, name).stat().st_uid != 0
            ]
            checks.append(
                Check(
                    "FAIL" if wrong_owner else "OK",
                    "Secrets owned by root"
                    if not wrong_owner
                    else f"Secrets not owned by root: {', '.join(wrong_owner)}",
                )
            )

    nginx_stage = active_stage(paths)
    checks.append(
        Check(
            "OK" if nginx_stage in ("bootstrap", "final") else "FAIL",
            f"Nginx active config: {nginx_stage or 'missing'}",
        )
    )
    xray_config = paths.xray_dir / "config.json"
    checks.append(
        Check("OK" if xray_config.is_file() else "FAIL", f"Xray config: {xray_config}")
    )
    if xray_config.is_file():
        try:
            json.loads(xray_config.read_text(encoding="utf-8"))
            checks.append(Check("OK", "Xray config is valid JSON"))
        except (json.JSONDecodeError, OSError):
            checks.append(Check("FAIL", "Xray config is not valid JSON"))
    has_certificate = certificate_exists(paths, settings.domain)
    checks.append(Check("OK" if has_certificate else "FAIL", "Certificate exists"))

    addresses = domain_addresses(settings.domain)
    server_ip = public_ip()
    if not addresses:
        checks.append(Check("FAIL", "Domain does not resolve"))
    elif server_ip and server_ip in addresses:
        checks.append(Check("OK", "Domain resolves to this server"))
    elif server_ip:
        checks.append(
            Check(
                "FAIL",
                f"Domain resolves to {', '.join(sorted(addresses))}, server IP is {server_ip}",
            )
        )
    else:
        checks.append(
            Check(
                "WARN",
                f"Domain resolves to {', '.join(sorted(addresses))}; public IP check unavailable",
            )
        )

    running_services: dict[str, bool] = {"nginx": False, "xray": False}
    if docker_available() and compose_available():
        docker = DockerCompose(paths)
        nginx_running = docker.is_running("nginx")
        xray_running = docker.is_running("xray")
        running_services = {"nginx": nginx_running, "xray": xray_running}
        checks.append(
            Check("OK" if nginx_running else "FAIL", "Nginx container running")
        )
        checks.append(Check("OK" if xray_running else "FAIL", "Xray container running"))
        if nginx_running:
            result = docker.exec("nginx", "nginx", "-t", check=False)
            valid = result.returncode == 0
            checks.append(Check("OK" if valid else "FAIL", "Nginx config valid"))
            if not valid:
                checks.append(
                    Check(
                        "FAIL",
                        f"Nginx validation: {_command_details(result.stdout, result.stderr)}",
                    )
                )
        else:
            result = docker.recent_logs("nginx")
            details = _command_details(result.stdout, result.stderr)
            if details:
                checks.append(Check("FAIL", f"Nginx logs: {details}"))
        if xray_running:
            result = docker.exec(
                "xray",
                "xray",
                "run",
                "-test",
                "-config",
                "/etc/xray/config.json",
                check=False,
            )
            valid = result.returncode == 0
            checks.append(Check("OK" if valid else "FAIL", "Xray config valid"))
            if not valid:
                checks.append(
                    Check(
                        "FAIL",
                        f"Xray validation: {_command_details(result.stdout, result.stderr)}",
                    )
                )
        else:
            result = docker.recent_logs("xray")
            details = _command_details(result.stdout, result.stderr)
            if details:
                checks.append(Check("FAIL", f"Xray logs: {details}"))
    else:
        checks.append(Check("FAIL", "Container status unavailable"))

    expected_ports = {
        settings.nginx_http_port: "nginx",
        settings.xray_reality_port: "xray",
        settings.xray_tls_port: "xray",
    }
    for port, service in expected_ports.items():
        available = port_available(port)
        if not available and running_services[service]:
            checks.append(
                Check("OK", f"Port {port} is occupied by expected service {service}")
            )
        elif not available:
            checks.append(
                Check("FAIL", f"Port {port} is occupied while {service} is not running")
            )
        else:
            checks.append(Check("WARN", f"Port {port} is free"))
    checks.append(
        Check(
            "OK" if challenge_reachable(settings.domain) else "WARN",
            "HTTP challenge path reachable",
        )
    )
    checks.append(Check("WARN", "Certbot renew timer not configured"))
    return checks
