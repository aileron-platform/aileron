#!/usr/bin/env python3
"""Create or validate Docker development Manager private material."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
from pathlib import Path
from tempfile import NamedTemporaryFile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_KEY_FILENAME = "private-key.pem"
PUBLIC_KEY_SET_FILENAME = "jwks.json"
RUNTIME_DATABASE_CREDENTIAL_KEY_FILENAME = "runtime-database-credential.key"
BROWSER_CREDENTIAL_KEYRING_FILENAME = "browser-credential-keyring.json"
BROWSER_CREDENTIAL_KEYRING_ALGORITHM = "hkdf-sha256-v1"
BROWSER_CREDENTIAL_KEYRING_KEY_ID = "development-browser-credential-v1"
_RUNTIME_DATABASE_CREDENTIAL_PATTERN = re.compile(rb"^[A-Za-z0-9_-]{64}$")


class RuntimeAssertionKeyError(RuntimeError):
    """Raised when existing development key material is incomplete or invalid."""


class RuntimeDatabaseCredentialKeyError(RuntimeError):
    """Raised when the Manager database credential key is invalid."""


class BrowserCredentialKeyringError(RuntimeError):
    """Raised when the Manager browser credential keyring is invalid."""


def _public_jwk(private_key: Ed25519PrivateKey, key_id: str) -> dict[str, str]:
    raw_public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encoded_public_key = base64.urlsafe_b64encode(raw_public_key).rstrip(b"=")
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
        "kid": key_id,
        "x": encoded_public_key.decode("ascii"),
    }


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    try:
        private_key = serialization.load_pem_private_key(
            path.read_bytes(),
            password=None,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeAssertionKeyError("Existing private key is invalid") from exc
    if not isinstance(private_key, Ed25519PrivateKey):
        raise RuntimeAssertionKeyError("Existing private key must use Ed25519")
    return private_key


def _validate_existing_key_set(
    path: Path,
    *,
    expected_key: dict[str, str],
) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeAssertionKeyError("Existing public key set is invalid") from exc
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise RuntimeAssertionKeyError("Existing public key set is invalid")
    matching_keys = [
        key
        for key in document["keys"]
        if isinstance(key, dict) and key.get("kid") == expected_key["kid"]
    ]
    if matching_keys != [expected_key]:
        raise RuntimeAssertionKeyError(
            "Existing public key set does not match the active private key"
        )


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary_file:
        temporary_path = Path(temporary_file.name)
        try:
            os.fchmod(temporary_file.fileno(), mode)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path.replace(path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def ensure_runtime_assertion_keys(output_directory: Path, key_id: str) -> None:
    """Create both files once, or validate the complete existing pair."""

    if not key_id or key_id != key_id.strip():
        raise RuntimeAssertionKeyError("Active key ID is invalid")

    output_directory.mkdir(parents=True, exist_ok=True)
    private_key_file = output_directory / PRIVATE_KEY_FILENAME
    public_key_set_file = output_directory / PUBLIC_KEY_SET_FILENAME
    existing_count = sum(
        path.exists() for path in (private_key_file, public_key_set_file)
    )
    if existing_count == 1:
        raise RuntimeAssertionKeyError(
            "Runtime assertion private and public key files must both exist"
        )
    if existing_count == 2:
        private_key = _load_private_key(private_key_file)
        _validate_existing_key_set(
            public_key_set_file,
            expected_key=_public_jwk(private_key, key_id),
        )
        return

    private_key = Ed25519PrivateKey.generate()
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_set_bytes = (
        json.dumps(
            {"keys": [_public_jwk(private_key, key_id)]},
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _atomic_write(private_key_file, private_key_bytes, 0o600)
    try:
        _atomic_write(public_key_set_file, public_key_set_bytes, 0o644)
    except Exception:
        private_key_file.unlink(missing_ok=True)
        raise


def ensure_runtime_database_credential_key(output_directory: Path) -> None:
    """Create one durable development HMAC key or validate the existing file."""

    output_directory.mkdir(parents=True, exist_ok=True)
    key_file = output_directory / RUNTIME_DATABASE_CREDENTIAL_KEY_FILENAME
    if key_file.exists():
        try:
            value = key_file.read_bytes()
            mode = key_file.stat().st_mode & 0o777
        except OSError as exc:
            raise RuntimeDatabaseCredentialKeyError(
                "Existing Runtime database credential key is unreadable"
            ) from exc
        if not _RUNTIME_DATABASE_CREDENTIAL_PATTERN.fullmatch(value):
            raise RuntimeDatabaseCredentialKeyError(
                "Existing Runtime database credential key is invalid"
            )
        if mode & 0o077:
            raise RuntimeDatabaseCredentialKeyError(
                "Existing Runtime database credential key permissions are too broad"
            )
        return

    value = secrets.token_urlsafe(48).encode("ascii")
    _atomic_write(key_file, value, 0o600)


def ensure_browser_credential_keyring(output_directory: Path, key_id: str) -> None:
    """Create one durable development browser credential keyring, or validate the existing file."""

    if not key_id or key_id != key_id.strip():
        raise BrowserCredentialKeyringError("Active key ID is invalid")

    output_directory.mkdir(parents=True, exist_ok=True)
    keyring_file = output_directory / BROWSER_CREDENTIAL_KEYRING_FILENAME
    if keyring_file.exists():
        try:
            document = json.loads(keyring_file.read_text(encoding="utf-8"))
            mode = keyring_file.stat().st_mode & 0o777
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrowserCredentialKeyringError(
                "Existing browser credential keyring is invalid"
            ) from exc
        if (
            not isinstance(document, dict)
            or document.get("algorithm") != BROWSER_CREDENTIAL_KEYRING_ALGORITHM
            or document.get("activeKeyId") != key_id
            or not isinstance(document.get("keys"), dict)
            or key_id not in document["keys"]
        ):
            raise BrowserCredentialKeyringError(
                "Existing browser credential keyring does not match the active key ID"
            )
        if mode & 0o077:
            raise BrowserCredentialKeyringError(
                "Existing browser credential keyring permissions are too broad"
            )
        return

    key_value = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    content = (
        json.dumps(
            {
                "algorithm": BROWSER_CREDENTIAL_KEYRING_ALGORITHM,
                "activeKeyId": key_id,
                "keys": {key_id: key_value},
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _atomic_write(keyring_file, content, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--key-id", required=True)
    arguments = parser.parse_args()
    try:
        ensure_runtime_assertion_keys(arguments.output_directory, arguments.key_id)
        ensure_runtime_database_credential_key(arguments.output_directory)
        ensure_browser_credential_keyring(
            arguments.output_directory, BROWSER_CREDENTIAL_KEYRING_KEY_ID
        )
    except (
        RuntimeAssertionKeyError,
        RuntimeDatabaseCredentialKeyError,
        BrowserCredentialKeyringError,
    ) as exc:
        parser.error(str(exc))
    print("Manager private material is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
