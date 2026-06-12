from __future__ import annotations

import json
import os
import re
import secrets as random_secrets
import uuid
from pathlib import Path

from vpnforge.config import Paths, Settings, load_settings
from vpnforge.files import atomic_write
from vpnforge.render import render_template, write_rendered
from vpnforge.shell import Runner, runner


XRAY_IMAGE = "ghcr.io/xtls/xray-core:latest"
SECRET_NAMES = (
    "xray_uuid",
    "reality_private_key",
    "reality_public_key",
    "reality_short_id",
    "xhttp_path",
    "subscription_path",
)


def secret_path(paths: Paths, name: str) -> Path:
    if name not in SECRET_NAMES:
        raise ValueError(f"Unknown secret: {name}")
    return paths.secrets_dir / name


def _write_secret(path: Path, value: str) -> None:
    atomic_write(path, value.strip() + "\n", mode=0o600)
    os.chmod(path, 0o600)


def _generate_reality_keys(command_runner: Runner) -> tuple[str, str]:
    result = command_runner.run(
        ["docker", "run", "--rm", XRAY_IMAGE, "x25519"],
        capture=True,
    )
    private_match = re.search(r"(?im)^Private key:\s*(\S+)", result.stdout)
    public_match = re.search(r"(?im)^(?:Public key|Password):\s*(\S+)", result.stdout)
    if not private_match or not public_match:
        raise RuntimeError("Could not parse Xray x25519 output")
    return private_match.group(1), public_match.group(1)


def generate_secrets(
    paths: Paths, *, force: bool = False, command_runner: Runner = runner
) -> list[str]:
    paths.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(paths.secrets_dir, 0o700)
    generated: list[str] = []

    simple_values = {
        "xray_uuid": str(uuid.uuid4()),
        "reality_short_id": random_secrets.token_hex(8),
        "xhttp_path": random_secrets.token_hex(6),
        "subscription_path": random_secrets.token_hex(10),
    }
    for name, value in simple_values.items():
        path = secret_path(paths, name)
        if path.exists() and not force:
            continue
        _write_secret(path, value)
        generated.append(name)

    private_path = secret_path(paths, "reality_private_key")
    public_path = secret_path(paths, "reality_public_key")
    if force or not private_path.exists() or not public_path.exists():
        private_key, public_key = _generate_reality_keys(command_runner)
        _write_secret(private_path, private_key)
        _write_secret(public_path, public_key)
        generated.extend(["reality_private_key", "reality_public_key"])

    return generated


def load_secrets(paths: Paths) -> dict[str, str]:
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in SECRET_NAMES:
        path = secret_path(paths, name)
        if not path.is_file():
            missing.append(str(path))
            continue
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            missing.append(str(path))
            continue
        values[name] = value
    if missing:
        raise FileNotFoundError("Missing or empty secrets: " + ", ".join(missing))
    try:
        uuid.UUID(values["xray_uuid"])
    except ValueError as error:
        raise ValueError("Invalid xray_uuid secret") from error
    if not re.fullmatch(r"[0-9a-fA-F]{16}", values["reality_short_id"]):
        raise ValueError("Invalid reality_short_id secret")
    if not re.fullmatch(r"[a-z0-9]{6,32}", values["xhttp_path"]):
        raise ValueError("Invalid xhttp_path secret")
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", values["subscription_path"]):
        raise ValueError("Invalid subscription_path secret")
    return values


EXTRA_QUERY = (
    "%7B%22xmux%22%3A%7B%22cMaxReuseTimes%22%3A%221000-3000%22%2C"
    "%22maxConcurrency%22%3A%223-5%22%2C%22maxConnections%22%3A0%2C"
    "%22hKeepAlivePeriod%22%3A0%2C%22hMaxRequestTimes%22%3A%22400-700%22%2C"
    "%22hMaxReusableSecs%22%3A%221200-1800%22%7D%2C%22headers%22%3A%7B%7D%2C"
    "%22noGRPCHeader%22%3Afalse%2C%22xPaddingBytes%22%3A%22400-800%22%2C"
    "%22scMaxEachPostBytes%22%3A1500000%2C%22scMinPostsIntervalMs%22%3A20%2C"
    "%22scStreamUpServerSecs%22%3A%2260-240%22%7D"
)


def client_links(settings: Settings, values: dict[str, str]) -> list[dict[str, str]]:
    domain = settings.domain
    uuid_value = values["xray_uuid"]
    path = values["xhttp_path"]
    fingerprint = settings.fingerprint
    public_key = values["reality_public_key"]
    short_id = values["reality_short_id"]
    reality_port = settings.xray_reality_port
    tls_port = settings.xray_tls_port
    return [
        {
            "title": "VLESS XHTTP REALITY EXTRA",
            "link": f"vless://{uuid_value}@{domain}:{reality_port}?security=reality&type=xhttp&headerType=&path=%2F{path}&host=&mode=stream-one&extra={EXTRA_QUERY}&sni={domain}&fp={fingerprint}&pbk={public_key}&sid={short_id}&spx=%2F#vlessXHTTPrealityEXTRA-autoXRAY",
        },
        {
            "title": "VLESS RAW REALITY VISION",
            "link": f"vless://{uuid_value}@{domain}:{reality_port}?security=reality&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni={domain}&fp={fingerprint}&pbk={public_key}&sid={short_id}&spx=%2F#vlessRAWrealityVISION-autoXRAY",
        },
        {
            "title": "VLESS RAW TLS VISION",
            "link": f"vless://{uuid_value}@{domain}:{tls_port}?security=tls&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni={domain}&fp={fingerprint}&spx=%2F#vlessRAWtlsVision-autoXRAY",
        },
        {
            "title": "VLESS XHTTP TLS EXTRA",
            "link": f"vless://{uuid_value}@{domain}:{tls_port}?security=tls&type=xhttp&headerType=&path=%2F{path}&host=&mode=auto&extra={EXTRA_QUERY}&sni={domain}&fp={fingerprint}&spx=%2F#vlessXHTTPtls-autoXRAY",
        },
        {
            "title": "VLESS WS TLS",
            "link": f"vless://{uuid_value}@{domain}:{tls_port}?security=tls&type=ws&headerType=&path=%2F{path}22&host=&sni={domain}&fp={fingerprint}&spx=%2F#vlessWStls-autoXRAY",
        },
        {
            "title": "VLESS GRPC TLS",
            "link": f"vless://{uuid_value}@{domain}:{tls_port}?security=tls&type=grpc&headerType=&serviceName={path}11&host=&sni={domain}&fp={fingerprint}&spx=%2F#vlessGRPCtls-autoXRAY",
        },
    ]


def template_context(
    paths: Paths, settings: Settings | None = None
) -> dict[str, object]:
    settings = settings or load_settings(paths)
    values = load_secrets(paths)
    links = client_links(settings, values)
    return {
        "settings": settings,
        "secrets": values,
        "client_links": links,
        "subscription_url": f"https://{settings.domain}/{values['subscription_path']}.txt",
    }


def render_xray(paths: Paths, *, force: bool = False) -> bool:
    content = render_template(paths, "xray/config.json.j2", template_context(paths))
    json.loads(content)
    return write_rendered(
        paths.xray_dir / "config.json", content, force=force, mode=0o600
    )
