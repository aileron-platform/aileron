"""Runtime assertion development key bootstrap tests."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from scripts.generate_runtime_assertion_keys import (
    BROWSER_CREDENTIAL_KEYRING_FILENAME,
    PRIVATE_KEY_FILENAME,
    PUBLIC_KEY_SET_FILENAME,
    RUNTIME_DATABASE_CREDENTIAL_KEY_FILENAME,
    BrowserCredentialKeyringError,
    RuntimeDatabaseCredentialKeyError,
    RuntimeAssertionKeyError,
    ensure_browser_credential_keyring,
    ensure_runtime_database_credential_key,
    ensure_runtime_assertion_keys,
)


def test_generates_and_revalidates_matching_key_pair(tmp_path: Path) -> None:
    ensure_runtime_assertion_keys(tmp_path, "development-key-v1")

    private_key_file = tmp_path / PRIVATE_KEY_FILENAME
    public_key_set_file = tmp_path / PUBLIC_KEY_SET_FILENAME
    original_private_key = private_key_file.read_bytes()
    document = json.loads(public_key_set_file.read_text(encoding="utf-8"))

    assert document["keys"][0]["kid"] == "development-key-v1"
    assert document["keys"][0]["alg"] == "EdDSA"
    assert stat.S_IMODE(private_key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(public_key_set_file.stat().st_mode) == 0o644

    ensure_runtime_assertion_keys(tmp_path, "development-key-v1")
    assert private_key_file.read_bytes() == original_private_key


def test_rejects_incomplete_existing_key_pair(tmp_path: Path) -> None:
    (tmp_path / PRIVATE_KEY_FILENAME).write_text("incomplete", encoding="utf-8")

    with pytest.raises(RuntimeAssertionKeyError, match="must both exist"):
        ensure_runtime_assertion_keys(tmp_path, "development-key-v1")


def test_rejects_active_key_id_drift(tmp_path: Path) -> None:
    ensure_runtime_assertion_keys(tmp_path, "development-key-v1")

    with pytest.raises(RuntimeAssertionKeyError, match="does not match"):
        ensure_runtime_assertion_keys(tmp_path, "development-key-v2")


def test_generates_and_reuses_runtime_database_credential_key(
    tmp_path: Path,
) -> None:
    ensure_runtime_database_credential_key(tmp_path)

    key_file = tmp_path / RUNTIME_DATABASE_CREDENTIAL_KEY_FILENAME
    original_key = key_file.read_bytes()

    assert len(original_key) == 64
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600

    ensure_runtime_database_credential_key(tmp_path)
    assert key_file.read_bytes() == original_key


def test_rejects_insecure_runtime_database_credential_key_permissions(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / RUNTIME_DATABASE_CREDENTIAL_KEY_FILENAME
    key_file.write_bytes(b"a" * 64)
    key_file.chmod(0o644)

    with pytest.raises(RuntimeDatabaseCredentialKeyError, match="too broad"):
        ensure_runtime_database_credential_key(tmp_path)


def test_generates_and_reuses_browser_credential_keyring(tmp_path: Path) -> None:
    ensure_browser_credential_keyring(tmp_path, "development-browser-credential-v1")

    keyring_file = tmp_path / BROWSER_CREDENTIAL_KEYRING_FILENAME
    document = json.loads(keyring_file.read_text(encoding="utf-8"))

    assert document["algorithm"] == "hkdf-sha256-v1"
    assert document["activeKeyId"] == "development-browser-credential-v1"
    assert set(document["keys"]) == {"development-browser-credential-v1"}
    assert stat.S_IMODE(keyring_file.stat().st_mode) == 0o600

    original_key = document["keys"]["development-browser-credential-v1"]
    ensure_browser_credential_keyring(tmp_path, "development-browser-credential-v1")
    reloaded = json.loads(keyring_file.read_text(encoding="utf-8"))
    assert reloaded["keys"]["development-browser-credential-v1"] == original_key


def test_rejects_browser_credential_keyring_key_id_drift(tmp_path: Path) -> None:
    ensure_browser_credential_keyring(tmp_path, "development-browser-credential-v1")

    with pytest.raises(BrowserCredentialKeyringError, match="does not match"):
        ensure_browser_credential_keyring(tmp_path, "development-browser-credential-v2")


def test_rejects_insecure_browser_credential_keyring_permissions(
    tmp_path: Path,
) -> None:
    keyring_file = tmp_path / BROWSER_CREDENTIAL_KEYRING_FILENAME
    keyring_file.write_text(
        json.dumps(
            {
                "algorithm": "hkdf-sha256-v1",
                "activeKeyId": "development-browser-credential-v1",
                "keys": {"development-browser-credential-v1": "a" * 43},
            }
        ),
        encoding="utf-8",
    )
    keyring_file.chmod(0o644)

    with pytest.raises(BrowserCredentialKeyringError, match="too broad"):
        ensure_browser_credential_keyring(tmp_path, "development-browser-credential-v1")
