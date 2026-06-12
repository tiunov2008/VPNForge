from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from vpnforge.files import atomic_write


DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ENV_UNQUOTED_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PORT_RANGE_RE = re.compile(r"^(\d{1,5})-(\d{1,5})$")


def format_env_value(value: str) -> str:
    if ENV_UNQUOTED_RE.fullmatch(value):
        return value
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class Paths:
    project_dir: Path
    config_dir: Path
    runtime_dir: Path

    @classmethod
    def from_env(cls) -> "Paths":
        package_root = Path(__file__).resolve().parent
        source_project = package_root.parent
        installed_project = Path(sys.prefix) / "share" / "vpnforge"
        default_project = (
            source_project
            if (source_project / "compose").is_dir()
            else installed_project
        )
        return cls(
            project_dir=Path(os.getenv("VPNFORGE_PROJECT_DIR", default_project)),
            config_dir=Path(os.getenv("VPNFORGE_CONFIG_DIR", "/etc/vpnforge")),
            runtime_dir=Path(os.getenv("VPNFORGE_RUNTIME_DIR", "/var/lib/vpnforge")),
        )

    @property
    def env_file(self) -> Path:
        return self.config_dir / "vpnforge.env"

    @property
    def secrets_dir(self) -> Path:
        return self.config_dir / "secrets"

    @property
    def generated_dir(self) -> Path:
        return self.runtime_dir / "generated"

    @property
    def nginx_dir(self) -> Path:
        return self.generated_dir / "nginx"

    @property
    def nginx_html_dir(self) -> Path:
        return self.nginx_dir / "html"

    @property
    def xray_dir(self) -> Path:
        return self.generated_dir / "xray"

    @property
    def hysteria_dir(self) -> Path:
        return self.generated_dir / "hysteria"

    @property
    def certbot_dir(self) -> Path:
        return self.runtime_dir / "certbot"

    @property
    def certbot_www_dir(self) -> Path:
        return self.certbot_dir / "www"

    @property
    def certbot_conf_dir(self) -> Path:
        return self.certbot_dir / "conf"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    @property
    def state_file(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def compose_dir(self) -> Path:
        return self.project_dir / "compose"

    @property
    def templates_dir(self) -> Path:
        return Path(__file__).resolve().parent / "templates"

    @property
    def sysctl_dir(self) -> Path:
        return Path(os.getenv("VPNFORGE_SYSCTL_DIR", "/etc/sysctl.d"))


@dataclass(frozen=True)
class HysteriaPortRange:
    start: int = 20000
    end: int = 50000

    def __post_init__(self) -> None:
        if not 1 <= self.start <= 65535 or not 1 <= self.end <= 65535:
            raise ValueError("Hysteria ports must be between 1 and 65535")
        if self.start >= self.end:
            raise ValueError("Hysteria port range start must be less than end")

    @classmethod
    def parse(cls, value: str) -> "HysteriaPortRange":
        match = PORT_RANGE_RE.fullmatch(value.strip())
        if not match:
            raise ValueError(
                "HYSTERIA_PORT_RANGE must use START-END format, for example 20000-50000"
            )
        return cls(start=int(match.group(1)), end=int(match.group(2)))

    def __str__(self) -> str:
        return f"{self.start}-{self.end}"


@dataclass(frozen=True)
class Settings:
    domain: str
    email: str
    enable_xray: bool = True
    nginx_http_port: int = 80
    xray_reality_port: int = 443
    xray_tls_port: int = 8443
    fingerprint: str = "firefox"
    subscription_title: str = "VPNForge"
    enable_hysteria: bool = True
    hysteria_port_range: HysteriaPortRange = HysteriaPortRange()
    enable_bbr: bool = False

    def as_env(self) -> str:
        return "\n".join(
            [
                f"DOMAIN={self.domain}",
                f"EMAIL={self.email}",
                f"ENABLE_XRAY={'true' if self.enable_xray else 'false'}",
                f"NGINX_HTTP_PORT={self.nginx_http_port}",
                f"XRAY_REALITY_PORT={self.xray_reality_port}",
                f"XRAY_TLS_PORT={self.xray_tls_port}",
                f"FINGERPRINT={self.fingerprint}",
                f"SUBSCRIPTION_TITLE={format_env_value(self.subscription_title)}",
                f"ENABLE_HYSTERIA={'true' if self.enable_hysteria else 'false'}",
                f"HYSTERIA_PORT_RANGE={self.hysteria_port_range}",
                f"ENABLE_BBR={'true' if self.enable_bbr else 'false'}",
                "",
            ]
        )


def validate_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if not DOMAIN_RE.fullmatch(domain):
        raise ValueError(f"Invalid domain: {domain}")
    return domain


def create_settings(domain: str, email: str | None = None) -> Settings:
    domain = validate_domain(domain)
    email = email or f"admin@{domain}"
    if not EMAIL_RE.fullmatch(email):
        raise ValueError(f"Invalid email: {email}")
    return Settings(domain=domain, email=email)


def validate_subscription_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValueError("Subscription title cannot be empty")
    if "\n" in title or "\r" in title:
        raise ValueError("Subscription title must be a single line")
    if len(title) > 128:
        raise ValueError("Subscription title cannot exceed 128 characters")
    return title


def parse_bool_setting(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return normalized == "true"


def write_settings(paths: Paths, settings: Settings, *, force: bool = False) -> bool:
    if paths.env_file.exists() and not force:
        return False
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(paths.env_file, settings.as_env(), mode=0o600)
    return True


def load_settings(paths: Paths) -> Settings:
    if not paths.env_file.is_file():
        raise FileNotFoundError(f"Settings file not found: {paths.env_file}")
    values = dotenv_values(paths.env_file, interpolate=False)
    domain = validate_domain(str(values.get("DOMAIN", "")))
    email = str(values.get("EMAIL", ""))
    if not email:
        raise ValueError("EMAIL is missing from vpnforge.env")
    if not EMAIL_RE.fullmatch(email):
        raise ValueError(f"Invalid EMAIL in vpnforge.env: {email}")
    return Settings(
        domain=domain,
        email=email,
        enable_xray=parse_bool_setting(
            str(values.get("ENABLE_XRAY", "true")), "ENABLE_XRAY"
        ),
        nginx_http_port=int(str(values.get("NGINX_HTTP_PORT", "80"))),
        xray_reality_port=int(str(values.get("XRAY_REALITY_PORT", "443"))),
        xray_tls_port=int(str(values.get("XRAY_TLS_PORT", "8443"))),
        fingerprint=str(values.get("FINGERPRINT", "firefox")),
        subscription_title=validate_subscription_title(
            str(values.get("SUBSCRIPTION_TITLE", "VPNForge"))
        ),
        enable_hysteria=parse_bool_setting(
            str(values.get("ENABLE_HYSTERIA", "true")), "ENABLE_HYSTERIA"
        ),
        hysteria_port_range=HysteriaPortRange.parse(
            str(values.get("HYSTERIA_PORT_RANGE", "20000-50000"))
        ),
        enable_bbr=parse_bool_setting(
            str(values.get("ENABLE_BBR", "false")), "ENABLE_BBR"
        ),
    )


def ensure_directories(paths: Paths) -> None:
    for directory in (
        paths.config_dir,
        paths.runtime_dir,
        paths.nginx_dir,
        paths.nginx_html_dir,
        paths.xray_dir,
        paths.hysteria_dir,
        paths.certbot_www_dir,
        paths.certbot_conf_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    paths.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(paths.secrets_dir, 0o700)
