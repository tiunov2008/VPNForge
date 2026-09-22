"""Certificate plumbing for the Dokploy deployment.

On a Dokploy host Traefik owns ports 80 and 443 and is the only ACME client,
so VPNForge does not run certbot there. Traefik stores what it obtains in a
single ``acme.json``; this module lifts the certificate for our domain out of
that file and writes a PEM pair that Xray, Hysteria and Nginx can read.

Until Traefik has actually issued the certificate -- which cannot happen before
DNS resolves and the domain is routed -- a self-signed placeholder keeps those
services bootable instead of crash-looping.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from vpnforge.files import atomic_write


DEFAULT_ACME_PATH = Path("/acme/acme.json")
PLACEHOLDER_MARKER = "VPNForge self-signed placeholder"


class CertificateNotFound(LookupError):
    """Traefik has not issued a certificate for the domain yet."""


@dataclass(frozen=True)
class CertificatePair:
    fullchain: str
    privkey: str

    @property
    def is_placeholder(self) -> bool:
        return PLACEHOLDER_MARKER in self.fullchain


def _domain_matches(domain: str, candidate: str) -> bool:
    candidate = candidate.strip().lower()
    domain = domain.strip().lower()
    if candidate == domain:
        return True
    if candidate.startswith("*."):
        # A wildcard covers exactly one label, so a.b.example.com is not
        # covered by *.example.com.
        suffix = candidate[1:]
        return domain.endswith(suffix) and "." not in domain[: -len(suffix)]
    return False


def _entry_names(entry: dict) -> list[str]:
    domain = entry.get("domain") or {}
    if not isinstance(domain, dict):
        return []
    names: list[str] = []
    main = domain.get("main")
    if isinstance(main, str):
        names.append(main)
    sans = domain.get("sans")
    if isinstance(sans, list):
        names.extend(name for name in sans if isinstance(name, str))
    return names


def _decode(value: str, label: str) -> str:
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"Malformed {label} in acme.json") from error


def extract_certificate(payload: dict, domain: str) -> CertificatePair:
    """Pull the PEM pair for ``domain`` out of a parsed acme.json."""
    if not isinstance(payload, dict):
        raise ValueError("acme.json must contain a JSON object")
    for resolver in payload.values():
        if not isinstance(resolver, dict):
            continue
        entries = resolver.get("Certificates") or resolver.get("certificates")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if not any(_domain_matches(domain, name) for name in _entry_names(entry)):
                continue
            certificate = entry.get("certificate")
            key = entry.get("key")
            if not isinstance(certificate, str) or not isinstance(key, str):
                continue
            return CertificatePair(
                fullchain=_decode(certificate, "certificate"),
                privkey=_decode(key, "private key"),
            )
    raise CertificateNotFound(
        f"acme.json has no certificate for {domain}. Attach the domain to the "
        "nginx service in Dokploy and wait for Traefik to finish the HTTP-01 "
        "challenge."
    )


def read_acme(path: Path) -> dict:
    if not path.is_file():
        raise CertificateNotFound(f"Traefik acme.json not found at {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        raise CertificateNotFound(f"Traefik acme.json is empty: {path}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Traefik acme.json is not valid JSON: {error}") from error


def generate_placeholder(domain: str) -> CertificatePair:
    """Self-signed pair so Xray and Hysteria can start before Traefik issues."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, domain),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, PLACEHOLDER_MARKER),
        ]
    )
    now = dt.datetime.now(dt.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return CertificatePair(
        fullchain=(
            f"# {PLACEHOLDER_MARKER} for {domain}\n"
            + certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
        ),
        privkey=key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode("ascii"),
    )


def certificate_files(tls_dir: Path) -> tuple[Path, Path]:
    return tls_dir / "fullchain.pem", tls_dir / "privkey.pem"


def write_pair(tls_dir: Path, pair: CertificatePair) -> bool:
    """Write the pair, returning True when the contents actually changed."""
    fullchain_path, privkey_path = certificate_files(tls_dir)
    unchanged = (
        fullchain_path.is_file()
        and privkey_path.is_file()
        and fullchain_path.read_text(encoding="utf-8") == pair.fullchain
        and privkey_path.read_text(encoding="utf-8") == pair.privkey
    )
    if unchanged:
        return False
    tls_dir.mkdir(parents=True, exist_ok=True)
    # Xray and Hysteria read these as their own unprivileged users from a
    # shared volume, so they stay readable but never writable.
    atomic_write(fullchain_path, pair.fullchain, mode=0o644)
    atomic_write(privkey_path, pair.privkey, mode=0o644)
    return True


def current_pair(tls_dir: Path) -> CertificatePair | None:
    fullchain_path, privkey_path = certificate_files(tls_dir)
    if not fullchain_path.is_file() or not privkey_path.is_file():
        return None
    return CertificatePair(
        fullchain=fullchain_path.read_text(encoding="utf-8"),
        privkey=privkey_path.read_text(encoding="utf-8"),
    )


def ensure_placeholder(tls_dir: Path, domain: str) -> bool:
    """Create a placeholder only when no certificate exists at all."""
    if current_pair(tls_dir) is not None:
        return False
    return write_pair(tls_dir, generate_placeholder(domain))


def sync_once(tls_dir: Path, domain: str, acme_path: Path) -> bool:
    """Copy Traefik's certificate into ``tls_dir``. True when it changed."""
    pair = extract_certificate(read_acme(acme_path), domain)
    return write_pair(tls_dir, pair)


def acme_path_from_env() -> Path:
    return Path(os.getenv("VPNFORGE_ACME_JSON", str(DEFAULT_ACME_PATH)))


def watch(
    tls_dir: Path,
    domain: str,
    acme_path: Path,
    *,
    interval: float = 60.0,
    iterations: int | None = None,
    sleep=time.sleep,
    on_event=None,
) -> None:
    """Poll acme.json until the real certificate appears, then track renewals.

    Traefik rewrites acme.json in place on renewal, so polling is what keeps
    the shared PEM pair current for Xray and Hysteria.
    """
    completed = 0
    while iterations is None or completed < iterations:
        try:
            changed = sync_once(tls_dir, domain, acme_path)
            if on_event:
                on_event("updated" if changed else "unchanged", None)
        except CertificateNotFound as error:
            if on_event:
                on_event("pending", error)
        except (ValueError, OSError) as error:
            if on_event:
                on_event("error", error)
        completed += 1
        if iterations is None or completed < iterations:
            sleep(interval)
