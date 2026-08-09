"""Verify short-lived Manager Ed25519 assertions without shared secrets."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config.settings import Settings, get_settings

RUNTIME_DRAIN_AUDIENCE = "workspace-runtime-drain"
BROWSER_PAIRING_AUDIENCE = "workspace-browser-extension"
RUNTIME_COMMAND_AUDIENCE = "workspace-runtime-command"
MAX_ASSERTION_TTL_SECONDS = 60
_MAX_ASSERTION_BYTES = 16 * 1024
_MAX_JWKS_BYTES = 256 * 1024


@dataclass(frozen=True)
class ManagerAssertionInvalid(Exception):
    error_code: str = "RUNTIME_ASSERTION_INVALID"


@dataclass(frozen=True)
class ManagerAssertionConflict(Exception):
    error_code: str


@dataclass(frozen=True)
class RuntimeDrainClaims:
    workspace_id: str
    expected_runtime_instance_id: str
    expected_mounted_revision: int
    target_revision: int
    drain_attempt_id: str
    deadline: int
    job_id: str
    issued_at: int
    expires_at: int
    jti: str


@dataclass(frozen=True)
class BrowserPairingClaims:
    actor_user_id: str
    workspace_id: str
    runtime_instance_id: str
    browser_workload_identity: str
    pairing_session_id: str
    issued_at: int
    expires_at: int
    jti: str


@dataclass(frozen=True)
class RuntimeCommandClaims:
    workspace_id: str
    runtime_instance_id: str
    action: str
    issued_at: int
    expires_at: int
    jti: str


class ManagerAssertionVerifier:
    """Validate audience-bound assertions and consume every JTI once."""

    def __init__(
        self,
        *,
        public_key_set_file: str | Path,
        issuer: str,
        workspace_id: str,
        runtime_instance_id: str,
        mounted_revision: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._issuer = self._required_text(issuer)
        self._workspace_id = self._required_text(workspace_id)
        self._runtime_instance_id = self._required_text(runtime_instance_id)
        self._mounted_revision = self._revision(mounted_revision)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._public_keys = self._load_public_keys(Path(public_key_set_file))
        self._consumed_jtis: dict[str, int] = {}

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None
    ) -> "ManagerAssertionVerifier":
        resolved = settings or get_settings()
        return cls(
            public_key_set_file=resolved.AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE,
            issuer=resolved.AILERON_RUNTIME_ASSERTION_ISSUER,
            workspace_id=resolved.AILERON_WORKSPACE_ID,
            runtime_instance_id=resolved.AILERON_RUNTIME_INSTANCE_ID,
            mounted_revision=resolved.AILERON_KB_MOUNT_REVISION,
        )

    def verify_runtime_drain(self, assertion: str) -> RuntimeDrainClaims:
        claims = self._verify(assertion, audience=RUNTIME_DRAIN_AUDIENCE)
        self._require_common_claims(claims, action="drain")

        expected_instance = self._claim_text(claims, "expectedRuntimeInstanceId")
        expected_revision = self._claim_revision(claims, "expectedMountedRevision")
        if expected_instance != self._runtime_instance_id:
            raise ManagerAssertionConflict("WORKSPACE_RUNTIME_INSTANCE_MISMATCH")
        if expected_revision != self._mounted_revision:
            raise ManagerAssertionConflict("WORKSPACE_RUNTIME_REVISION_MISMATCH")

        deadline = self._claim_epoch(claims, "deadline")
        if deadline < self._claim_epoch(claims, "exp"):
            raise ManagerAssertionInvalid()
        return RuntimeDrainClaims(
            workspace_id=self._claim_text(claims, "workspaceId"),
            expected_runtime_instance_id=expected_instance,
            expected_mounted_revision=expected_revision,
            target_revision=self._claim_revision(claims, "targetRevision"),
            drain_attempt_id=self._claim_text(claims, "drainAttemptId"),
            deadline=deadline,
            job_id=self._claim_text(claims, "jobId"),
            issued_at=self._claim_epoch(claims, "iat"),
            expires_at=self._claim_epoch(claims, "exp"),
            jti=self._claim_text(claims, "jti"),
        )

    def verify_browser_pairing(self, assertion: str) -> BrowserPairingClaims:
        """Verify and return the Manager-signed identity for one relay socket.

        Browser workloads cannot be replaced independently inside one runtime
        generation. Browser restart recycles the complete generation, so the
        signed runtime instance fence authenticates the workload identity claim
        without comparing it to a predictable container or Pod name.
        """

        claims = self._verify(assertion, audience=BROWSER_PAIRING_AUDIENCE)
        self._require_common_claims(claims, action="browser_automation")
        runtime_instance_id = self._claim_text(claims, "runtimeInstanceId")
        workload_identity = self._claim_text(claims, "browserWorkloadIdentity")
        if runtime_instance_id != self._runtime_instance_id:
            raise ManagerAssertionConflict("WORKSPACE_RUNTIME_INSTANCE_MISMATCH")
        return BrowserPairingClaims(
            actor_user_id=self._claim_text(claims, "actorUserId"),
            workspace_id=self._claim_text(claims, "workspaceId"),
            runtime_instance_id=runtime_instance_id,
            browser_workload_identity=workload_identity,
            pairing_session_id=self._claim_text(claims, "pairingSessionId"),
            issued_at=self._claim_epoch(claims, "iat"),
            expires_at=self._claim_epoch(claims, "exp"),
            jti=self._claim_text(claims, "jti"),
        )

    def verify_runtime_command(
        self, assertion: str, *, action: str
    ) -> RuntimeCommandClaims:
        """Verify one Manager command for this exact Runtime generation."""

        required_action = self._required_text(action)
        claims = self._verify(assertion, audience=RUNTIME_COMMAND_AUDIENCE)
        self._require_common_claims(claims, action=required_action)
        runtime_instance_id = self._claim_text(claims, "runtimeInstanceId")
        if runtime_instance_id != self._runtime_instance_id:
            raise ManagerAssertionConflict("WORKSPACE_RUNTIME_INSTANCE_MISMATCH")
        return RuntimeCommandClaims(
            workspace_id=self._claim_text(claims, "workspaceId"),
            runtime_instance_id=runtime_instance_id,
            action=required_action,
            issued_at=self._claim_epoch(claims, "iat"),
            expires_at=self._claim_epoch(claims, "exp"),
            jti=self._claim_text(claims, "jti"),
        )

    def _verify(
        self,
        assertion: str,
        *,
        audience: str,
        maximum_ttl_seconds: int = MAX_ASSERTION_TTL_SECONDS,
    ) -> dict[str, Any]:
        if (
            not isinstance(assertion, str)
            or not assertion
            or len(assertion.encode("utf-8")) > _MAX_ASSERTION_BYTES
        ):
            raise ManagerAssertionInvalid()
        parts = assertion.split(".")
        if len(parts) != 3:
            raise ManagerAssertionInvalid()
        encoded_header, encoded_claims, encoded_signature = parts
        header = self._decode_json(encoded_header)
        claims = self._decode_json(encoded_claims)
        if (
            header.get("alg") != "EdDSA"
            or header.get("typ") != "JWT"
            or not isinstance(header.get("kid"), str)
        ):
            raise ManagerAssertionInvalid()
        public_key = self._public_keys.get(header["kid"])
        if public_key is None:
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KID_UNKNOWN")
        try:
            signature = self._base64url_decode(encoded_signature)
            public_key.verify(
                signature,
                f"{encoded_header}.{encoded_claims}".encode("ascii"),
            )
        except (InvalidSignature, ValueError, UnicodeEncodeError):
            raise ManagerAssertionInvalid() from None

        if claims.get("iss") != self._issuer or claims.get("aud") != audience:
            raise ManagerAssertionInvalid()
        issued_at = self._claim_epoch(claims, "iat")
        expires_at = self._claim_epoch(claims, "exp")
        now = int(self._clock().astimezone(timezone.utc).timestamp())
        if (
            issued_at > now + 5
            or expires_at <= now
            or expires_at <= issued_at
            or expires_at - issued_at > maximum_ttl_seconds
        ):
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_EXPIRED")

        jti = self._claim_text(claims, "jti")
        self._discard_expired_jtis(now)
        if jti in self._consumed_jtis:
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_REPLAYED")
        self._consumed_jtis[jti] = expires_at
        return claims

    def _require_common_claims(self, claims: Mapping[str, Any], *, action: str) -> None:
        if claims.get("action") != action:
            raise ManagerAssertionInvalid()
        if self._claim_text(claims, "workspaceId") != self._workspace_id:
            raise ManagerAssertionConflict("WORKSPACE_RUNTIME_WORKSPACE_MISMATCH")

    def _discard_expired_jtis(self, now: int) -> None:
        for jti, expires_at in list(self._consumed_jtis.items()):
            if expires_at <= now:
                self._consumed_jtis.pop(jti, None)

    @classmethod
    def _load_public_keys(cls, path: Path) -> dict[str, Ed25519PublicKey]:
        try:
            with path.open("rb") as key_file:
                raw_document = key_file.read(_MAX_JWKS_BYTES + 1)
        except OSError:
            raise ManagerAssertionInvalid(
                "RUNTIME_ASSERTION_KEYS_UNAVAILABLE"
            ) from None
        if not raw_document or len(raw_document) > _MAX_JWKS_BYTES:
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KEYS_INVALID")
        try:
            document = cls._decode_json_bytes(raw_document)
        except ManagerAssertionInvalid:
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KEYS_INVALID") from None
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KEYS_INVALID")

        public_keys: dict[str, Ed25519PublicKey] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, Mapping) or "d" in raw_key:
                raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KEYS_INVALID")
            kid = raw_key.get("kid")
            if (
                not isinstance(kid, str)
                or not kid
                or kid in public_keys
                or raw_key.get("kty") != "OKP"
                or raw_key.get("crv") != "Ed25519"
                or raw_key.get("alg", "EdDSA") != "EdDSA"
                or raw_key.get("use", "sig") != "sig"
                or not isinstance(raw_key.get("x"), str)
            ):
                raise ManagerAssertionInvalid("RUNTIME_ASSERTION_KEYS_INVALID")
            try:
                encoded_public_key = cls._base64url_decode(raw_key["x"])
                if len(encoded_public_key) != 32:
                    raise ValueError
                public_keys[kid] = Ed25519PublicKey.from_public_bytes(
                    encoded_public_key
                )
            except ValueError:
                raise ManagerAssertionInvalid(
                    "RUNTIME_ASSERTION_KEYS_INVALID"
                ) from None
        return public_keys

    @classmethod
    def _decode_json(cls, value: str) -> dict[str, Any]:
        try:
            return cls._decode_json_bytes(cls._base64url_decode(value))
        except (UnicodeDecodeError, ValueError):
            raise ManagerAssertionInvalid() from None

    @staticmethod
    def _decode_json_bytes(value: bytes) -> dict[str, Any]:
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise ManagerAssertionInvalid()
                result[key] = item
            return result

        try:
            document = json.loads(
                value.decode("utf-8"), object_pairs_hook=reject_duplicates
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ManagerAssertionInvalid() from None
        if not isinstance(document, dict):
            raise ManagerAssertionInvalid()
        return document

    @staticmethod
    def _base64url_decode(value: str) -> bytes:
        if not isinstance(value, str) or not value:
            raise ValueError
        try:
            return base64.b64decode(
                value + "=" * (-len(value) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError):
            raise ValueError from None

    @classmethod
    def _claim_text(cls, claims: Mapping[str, Any], name: str) -> str:
        try:
            return cls._required_text(claims.get(name))
        except ValueError:
            raise ManagerAssertionInvalid() from None

    @staticmethod
    def _required_text(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 256
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError
        return value

    @staticmethod
    def _claim_epoch(claims: Mapping[str, Any], name: str) -> int:
        value = claims.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ManagerAssertionInvalid()
        return value

    @staticmethod
    def _claim_revision(claims: Mapping[str, Any], name: str) -> int:
        value = claims.get(name)
        try:
            return ManagerAssertionVerifier._revision(value)
        except ValueError:
            raise ManagerAssertionInvalid() from None

    @staticmethod
    def _revision(value: Any) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError
        return value


@lru_cache(maxsize=1)
def get_manager_assertion_verifier() -> ManagerAssertionVerifier:
    return ManagerAssertionVerifier.from_settings()


__all__ = [
    "BROWSER_PAIRING_AUDIENCE",
    "BrowserPairingClaims",
    "ManagerAssertionConflict",
    "ManagerAssertionInvalid",
    "ManagerAssertionVerifier",
    "RUNTIME_COMMAND_AUDIENCE",
    "RUNTIME_DRAIN_AUDIENCE",
    "RuntimeCommandClaims",
    "RuntimeDrainClaims",
    "get_manager_assertion_verifier",
]
