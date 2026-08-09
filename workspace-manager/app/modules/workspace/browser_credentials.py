"""Derive revisioned Browser credentials from the control-plane keyring."""

from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config.settings import get_settings

BROWSER_CREDENTIAL_ALGORITHM = "hkdf-sha256-v1"
_SALT = b"aileron-browser-credential\x00hkdf-sha256-v1"
_MAX_KEYRING_BYTES = 256 * 1024


class BrowserCredentialConfigurationError(RuntimeError):
    """Raised when the control-plane keyring is unavailable or invalid."""


@dataclass(frozen=True)
class BrowserCredentialPair:
    key_id: str
    algorithm: str
    revision: int
    user_password: str
    admin_password: str


class BrowserCredentialService:
    """Load a strict keyring and derive deterministic per-Workspace secrets."""

    def __init__(self, keyring_file: str | Path) -> None:
        self._path = Path(keyring_file)
        self._active_key_id, self._keys = self._load_keyring(self._path)

    @classmethod
    def from_settings(cls) -> "BrowserCredentialService":
        return cls(get_settings().BROWSER_CREDENTIAL_KEYRING_FILE)

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    @property
    def loaded_key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def derive(
        self,
        *,
        workspace_id: str,
        revision: int,
        key_id: str,
        algorithm: str,
    ) -> BrowserCredentialPair:
        if algorithm != BROWSER_CREDENTIAL_ALGORITHM:
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_ALGORITHM_UNSUPPORTED"
            )
        if type(revision) is not int or revision < 1:
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_REVISION_INVALID"
            )
        key = self._keys.get(key_id)
        if key is None:
            raise BrowserCredentialConfigurationError("BROWSER_CREDENTIAL_KEY_UNKNOWN")
        try:
            canonical_workspace = UUID(workspace_id)
        except ValueError as exc:
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_WORKSPACE_ID_INVALID"
            ) from exc
        user = self._derive_one(
            key, canonical_workspace.bytes, revision, key_id, b"user"
        )
        admin = self._derive_one(
            key, canonical_workspace.bytes, revision, key_id, b"admin"
        )
        if user == admin or user in {"neko", "admin"} or admin in {"neko", "admin"}:
            raise BrowserCredentialConfigurationError("BROWSER_CREDENTIAL_INVALID")
        return BrowserCredentialPair(
            key_id=key_id,
            algorithm=algorithm,
            revision=revision,
            user_password=user,
            admin_password=admin,
        )

    @staticmethod
    def _derive_one(
        key: bytes,
        workspace_bytes: bytes,
        revision: int,
        key_id: str,
        purpose: bytes,
    ) -> str:
        fields = (
            b"aileron-browser-credential",
            BROWSER_CREDENTIAL_ALGORITHM.encode("ascii"),
            workspace_bytes,
            struct.pack(">Q", revision),
            key_id.encode("utf-8"),
            purpose,
        )
        info = b"".join(struct.pack(">I", len(field)) + field for field in fields)
        value = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_SALT,
            info=info,
        ).derive(key)
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _load_keyring(path: Path) -> tuple[str, dict[str, bytes]]:
        try:
            stat_result = path.stat()
            if not path.is_file() or stat_result.st_size > _MAX_KEYRING_BYTES:
                raise BrowserCredentialConfigurationError(
                    "BROWSER_CREDENTIAL_KEYRING_INVALID"
                )
            if stat_result.st_mode & 0o007:
                raise BrowserCredentialConfigurationError(
                    "BROWSER_CREDENTIAL_KEYRING_PERMISSIONS_INVALID"
                )
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_KEYRING_UNAVAILABLE"
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("algorithm") != BROWSER_CREDENTIAL_ALGORITHM
            or not isinstance(payload.get("activeKeyId"), str)
            or not isinstance(payload.get("keys"), dict)
        ):
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_KEYRING_INVALID"
            )
        keys: dict[str, bytes] = {}
        for key_id, encoded in payload["keys"].items():
            if (
                not isinstance(key_id, str)
                or not key_id
                or len(key_id) > 128
                or not isinstance(encoded, str)
            ):
                raise BrowserCredentialConfigurationError(
                    "BROWSER_CREDENTIAL_KEYRING_INVALID"
                )
            try:
                material = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            except ValueError as exc:
                raise BrowserCredentialConfigurationError(
                    "BROWSER_CREDENTIAL_KEYRING_INVALID"
                ) from exc
            if len(material) != 32:
                raise BrowserCredentialConfigurationError(
                    "BROWSER_CREDENTIAL_KEYRING_INVALID"
                )
            keys[key_id] = material
        active_key_id = payload["activeKeyId"]
        if active_key_id not in keys:
            raise BrowserCredentialConfigurationError(
                "BROWSER_CREDENTIAL_KEYRING_INVALID"
            )
        return active_key_id, keys


__all__ = [
    "BROWSER_CREDENTIAL_ALGORITHM",
    "BrowserCredentialConfigurationError",
    "BrowserCredentialPair",
    "BrowserCredentialService",
]
