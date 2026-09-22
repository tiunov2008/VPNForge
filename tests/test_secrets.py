from __future__ import annotations

import os
import stat

from vpnforge.config import ensure_directories
from vpnforge.services.xray import (
    SECRET_NAMES,
    generate_secrets,
    load_secrets,
    secret_path,
)
from vpnforge.shell import CommandResult


class FakeRunner:
    def __init__(self, output="Private key: private-key\nPassword: public-key\n"):
        self.calls = 0
        self.output = output

    def run(self, command, **kwargs):
        self.calls += 1
        return CommandResult(0, self.output, "")


def test_secret_generation_preserves_existing_values(paths):
    ensure_directories(paths)
    runner = FakeRunner()

    generated = generate_secrets(paths, command_runner=runner)
    first_values = load_secrets(paths)
    assert set(generated) == set(SECRET_NAMES)
    assert runner.calls == 1
    assert first_values["reality_private_key"] == "private-key"
    assert first_values["reality_public_key"] == "public-key"
    if os.name == "posix":
        for name in SECRET_NAMES:
            assert stat.S_IMODE(secret_path(paths, name).stat().st_mode) == 0o600

    assert generate_secrets(paths, command_runner=runner) == []
    assert load_secrets(paths) == first_values
    assert runner.calls == 1

    regenerated = generate_secrets(paths, force=True, command_runner=runner)
    assert set(regenerated) == set(SECRET_NAMES)
    assert runner.calls == 2


def test_secret_generation_parses_current_xray_output(paths):
    ensure_directories(paths)
    runner = FakeRunner(
        "PrivateKey: oD7Tb2RgH1qr1FAxp1e0I_dClI7-mH7PPEGDegQs7mg\n"
        "Password (PublicKey): anVToH_9tkrThuNFbim3buL2y_5ZBGdbMXLSkNy0oVU\n"
        "Hash32: Ux2ja6GbCA0wpWlQjQA0UYb-Wbymy5H4Z8WHTQt82dA\n"
    )

    generate_secrets(paths, command_runner=runner)
    values = load_secrets(paths)

    assert values["reality_private_key"] == (
        "oD7Tb2RgH1qr1FAxp1e0I_dClI7-mH7PPEGDegQs7mg"
    )
    assert values["reality_public_key"] == (
        "anVToH_9tkrThuNFbim3buL2y_5ZBGdbMXLSkNy0oVU"
    )


def test_local_reality_keypair_matches_xray_encoding(paths):
    from base64 import urlsafe_b64decode

    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    from vpnforge.services.xray import generate_reality_keypair

    private_key, public_key = generate_reality_keypair()

    def decode(value: str) -> bytes:
        assert "=" not in value
        return urlsafe_b64decode(value + "=" * (-len(value) % 4))

    private_raw = decode(private_key)
    assert len(private_raw) == 32
    assert len(decode(public_key)) == 32

    derived = (
        X25519PrivateKey.from_private_bytes(private_raw)
        .public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    assert decode(public_key) == derived


def test_generate_secrets_can_use_local_reality_keys(paths):
    ensure_directories(paths)
    runner = FakeRunner()

    generated = generate_secrets(
        paths,
        command_runner=runner,
        reality_keys=lambda: ("local-private", "local-public"),
    )

    assert set(generated) == set(SECRET_NAMES)
    assert runner.calls == 0
    values = {
        name: secret_path(paths, name).read_text(encoding="utf-8").strip()
        for name in ("reality_private_key", "reality_public_key")
    }
    assert values == {
        "reality_private_key": "local-private",
        "reality_public_key": "local-public",
    }
