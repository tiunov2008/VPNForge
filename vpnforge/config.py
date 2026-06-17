from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, DotEnvSettingsSource, SettingsConfigDict
from pydantic_settings.sources.utils import parse_env_vars

from vpnforge.files import atomic_write


ENV_UNQUOTED_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PORT_RANGE_RE = re.compile(r"^(\d{1,5})-(\d{1,5})$")


def format_env_value(value: str) -> str:
    if ENV_UNQUOTED_RE.fullmatch(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def _validate_domain_value(value: str) -> str:
    domain = value.strip().lower()
    if not domain:
        raise ValueError("Invalid domain: empty")
    labels = domain.split(".")
    if len(labels) < 2:
        raise ValueError(f"Invalid domain: {domain}")
    if len(domain) > 253:
        raise ValueError(f"Invalid domain: {domain}")
    for label in labels:
        if not label or len(label) > 63:
            raise ValueError(f"Invalid domain: {domain}")
        if label.startswith("-") or label.endswith("-"):
            raise ValueError(f"Invalid domain: {domain}")
        if not all(char.isascii() and (char.isalnum() or char == "-") for char in label):
            raise ValueError(f"Invalid domain: {domain}")
    tld = labels[-1]
    if len(tld) < 2 or not all(char.isascii() and char.isalpha() for char in tld):
        raise ValueError(f"Invalid domain: {domain}")
    return domain


class Paths(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_dir: Path
    config_dir: Path
    runtime_dir: Path

    def __init__(
        self,
        project_dir: Path | str | None = None,
        config_dir: Path | str | None = None,
        runtime_dir: Path | str | None = None,
        **data: Any,
    ) -> None:
        if project_dir is not None:
            data["project_dir"] = project_dir
        if config_dir is not None:
            data["config_dir"] = config_dir
        if runtime_dir is not None:
            data["runtime_dir"] = runtime_dir
        super().__init__(**data)

    @classmethod
    def from_env(cls) -> "Paths":
        package_root = Path(__file__).resolve().parent
        source_project = package_root.parent
        installed_project = Path(sys.prefix) / "share" / "vpnforge"
        default_project = (
            source_project
            if (source_project / "pyproject.toml").is_file()
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
    def compose_file(self) -> Path:
        return self.generated_dir / "docker-compose.yml"

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


class HysteriaPortRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int = Field(default=20000, ge=1, le=65535)
    end: int = Field(default=50000, ge=1, le=65535)

    def __init__(
        self,
        start: int | None = None,
        end: int | None = None,
        **data: Any,
    ) -> None:
        if start is not None:
            data["start"] = start
        if end is not None:
            data["end"] = end
        super().__init__(**data)

    @model_validator(mode="after")
    def validate_order(self) -> "HysteriaPortRange":
        if self.start >= self.end:
            raise ValueError("Hysteria port range start must be less than end")
        return self

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


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    domain: str
    email: EmailStr
    enable_xray: bool = True
    nginx_http_port: int = Field(default=80, ge=1, le=65535)
    xray_reality_port: int = Field(default=443, ge=1, le=65535)
    xray_tls_port: int = Field(default=8443, ge=1, le=65535)
    fingerprint: str = "firefox"
    subscription_title: str = "VPNForge"
    enable_hysteria: bool = True
    hysteria_port_range: HysteriaPortRange = Field(
        default_factory=HysteriaPortRange
    )
    enable_bbr: bool = False

    @field_validator("domain", mode="before")
    @classmethod
    def validate_domain_field(cls, value: Any) -> str:
        return _validate_domain_value(str(value))

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value)

    @field_validator("subscription_title", mode="before")
    @classmethod
    def validate_subscription_title_field(cls, value: Any) -> str:
        return _validate_subscription_title_value(str(value))

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


class _LiteralDotEnvSettingsSource(DotEnvSettingsSource):
    @staticmethod
    def _static_read_env_file(
        file_path: Path,
        *,
        encoding: str | None = None,
        case_sensitive: bool = False,
        ignore_empty: bool = False,
        parse_none_str: str | None = None,
    ) -> Mapping[str, str | None]:
        file_vars = dotenv_values(
            file_path,
            encoding=encoding or "utf-8",
            interpolate=False,
        )
        return parse_env_vars(file_vars, case_sensitive, ignore_empty, parse_none_str)


class _EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    DOMAIN: str
    EMAIL: EmailStr
    ENABLE_XRAY: bool = True
    NGINX_HTTP_PORT: int = Field(default=80, ge=1, le=65535)
    XRAY_REALITY_PORT: int = Field(default=443, ge=1, le=65535)
    XRAY_TLS_PORT: int = Field(default=8443, ge=1, le=65535)
    FINGERPRINT: str = "firefox"
    SUBSCRIPTION_TITLE: str = "VPNForge"
    ENABLE_HYSTERIA: bool = True
    HYSTERIA_PORT_RANGE: str = "20000-50000"
    ENABLE_BBR: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        literal_dotenv_settings = _LiteralDotEnvSettingsSource(
            settings_cls,
            env_file=dotenv_settings.env_file,
            env_file_encoding=dotenv_settings.env_file_encoding,
            case_sensitive=dotenv_settings.case_sensitive,
            env_prefix=dotenv_settings.env_prefix,
            env_nested_delimiter=dotenv_settings.env_nested_delimiter,
            env_nested_max_split=dotenv_settings.env_nested_max_split,
            env_ignore_empty=dotenv_settings.env_ignore_empty,
            env_parse_none_str=dotenv_settings.env_parse_none_str,
            env_parse_enums=dotenv_settings.env_parse_enums,
        )
        return (init_settings, literal_dotenv_settings)

    def to_settings(self) -> Settings:
        return Settings(
            domain=self.DOMAIN,
            email=str(self.EMAIL),
            enable_xray=self.ENABLE_XRAY,
            nginx_http_port=self.NGINX_HTTP_PORT,
            xray_reality_port=self.XRAY_REALITY_PORT,
            xray_tls_port=self.XRAY_TLS_PORT,
            fingerprint=self.FINGERPRINT,
            subscription_title=self.SUBSCRIPTION_TITLE,
            enable_hysteria=self.ENABLE_HYSTERIA,
            hysteria_port_range=HysteriaPortRange.parse(self.HYSTERIA_PORT_RANGE),
            enable_bbr=self.ENABLE_BBR,
        )


def validate_domain(domain: str) -> str:
    return _validate_domain_value(domain)


def create_settings(domain: str, email: str | None = None) -> Settings:
    domain = validate_domain(domain)
    return Settings(domain=domain, email=email or f"admin@{domain}")


def _validate_subscription_title_value(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValueError("Subscription title cannot be empty")
    if "\n" in title or "\r" in title:
        raise ValueError("Subscription title must be a single line")
    if len(title) > 128:
        raise ValueError("Subscription title cannot exceed 128 characters")
    return title


def validate_subscription_title(title: str) -> str:
    return _validate_subscription_title_value(title)


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
    try:
        return _EnvSettings(_env_file=paths.env_file).to_settings()
    except ValueError as error:
        raise ValueError(f"Invalid settings file {paths.env_file}: {error}") from error


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
