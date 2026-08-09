"""Verify reusable Manager-signed Workspace Execution Access Grants locally."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config.settings import Settings, get_settings
from app.modules.auth.manager_assertion import (
    ManagerAssertionInvalid,
    ManagerAssertionVerifier,
)

EXECUTION_GRANT_AUDIENCE = "workspace-runtime"
EXECUTION_GRANT_KIND = "workspace-execution-access-grant"
MAX_EXECUTION_GRANT_TTL_SECONDS = 60
RUNTIME_ACTIONS = frozenset(
    {
        "runtime_read",
        "runtime_write",
        "workspace_settings",
        "agent",
        "automation",
        "browser_automation",
    }
)


@dataclass(frozen=True)
class ExecutionGrantInvalid(Exception):
    error_code: str = "WORKSPACE_EXECUTION_GRANT_INVALID"


@dataclass(frozen=True)
class ExecutionGrantConflict(Exception):
    error_code: str


@dataclass(frozen=True)
class ExecutionGrantClaims:
    subject: str
    workspace_id: str
    runtime_instance_id: str
    runtime_access_revision: int
    actions: tuple[str, ...]
    issued_at: int
    expires_at: int
    jti: str


class ExecutionGrantVerifier:
    """Validate local signature, route action, and current Runtime fences."""

    def __init__(
        self,
        *,
        public_key_set_file: str | Path,
        issuer: str,
        workspace_id: str,
        runtime_instance_id: str,
        runtime_access_revision: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._issuer = self._text(issuer)
        self._workspace_id = self._text(workspace_id)
        self._runtime_instance_id = self._text(runtime_instance_id)
        self._runtime_access_revision = self._revision(runtime_access_revision)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._public_key_set_file = Path(public_key_set_file)
        self._public_keys_lock = RLock()
        try:
            self._public_keys = ManagerAssertionVerifier._load_public_keys(
                self._public_key_set_file
            )
        except ManagerAssertionInvalid as exc:
            raise ExecutionGrantInvalid(exc.error_code) from exc

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None
    ) -> "ExecutionGrantVerifier":
        resolved = settings or get_settings()
        return cls(
            public_key_set_file=resolved.AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE,
            issuer=resolved.AILERON_RUNTIME_ASSERTION_ISSUER,
            workspace_id=resolved.AILERON_WORKSPACE_ID,
            runtime_instance_id=resolved.AILERON_RUNTIME_INSTANCE_ID,
            runtime_access_revision=resolved.AILERON_RUNTIME_ACCESS_REVISION,
        )

    def verify(self, grant: str, *, action: str) -> ExecutionGrantClaims:
        required_action = self._text(action)
        if required_action not in RUNTIME_ACTIONS:
            raise ExecutionGrantInvalid()
        if not isinstance(grant, str) or len(grant) > 48 * 1024:
            raise ExecutionGrantInvalid()
        parts = grant.split(".")
        if len(parts) != 3:
            raise ExecutionGrantInvalid()
        try:
            header = ManagerAssertionVerifier._decode_json(parts[0])
            claims = ManagerAssertionVerifier._decode_json(parts[1])
            signature = ManagerAssertionVerifier._base64url_decode(parts[2])
        except (ManagerAssertionInvalid, ValueError) as exc:
            raise ExecutionGrantInvalid() from exc
        if (
            header.get("alg") != "EdDSA"
            or header.get("typ") != "JWT"
            or not isinstance(header.get("kid"), str)
            or not header["kid"]
        ):
            raise ExecutionGrantInvalid()
        public_key = self._public_key(header["kid"])
        if public_key is None:
            raise ExecutionGrantInvalid("WORKSPACE_EXECUTION_GRANT_KID_UNKNOWN")
        try:
            public_key.verify(signature, f"{parts[0]}.{parts[1]}".encode("ascii"))
        except (InvalidSignature, ValueError, UnicodeEncodeError) as exc:
            raise ExecutionGrantInvalid() from exc

        if (
            claims.get("iss") != self._issuer
            or claims.get("aud") != EXECUTION_GRANT_AUDIENCE
            or claims.get("kind") != EXECUTION_GRANT_KIND
        ):
            raise ExecutionGrantInvalid()
        issued_at = self._epoch(claims, "iat")
        expires_at = self._epoch(claims, "exp")
        now = int(self._clock().astimezone(timezone.utc).timestamp())
        if (
            issued_at > now + 5
            or expires_at <= now
            or expires_at - issued_at != MAX_EXECUTION_GRANT_TTL_SECONDS
        ):
            raise ExecutionGrantInvalid("WORKSPACE_EXECUTION_GRANT_EXPIRED")
        actions = claims.get("actions")
        if (
            not isinstance(actions, list)
            or not actions
            or any(
                not isinstance(item, str) or item not in RUNTIME_ACTIONS
                for item in actions
            )
            or actions != sorted(set(actions))
            or required_action not in actions
        ):
            raise ExecutionGrantInvalid("WORKSPACE_EXECUTION_GRANT_ACTION_FORBIDDEN")
        workspace_id = self._claim_text(claims, "workspaceId")
        runtime_instance_id = self._claim_text(claims, "runtimeInstanceId")
        revision = self._claim_revision(claims, "runtimeAccessRevision")
        if workspace_id != self._workspace_id:
            raise ExecutionGrantConflict("WORKSPACE_RUNTIME_WORKSPACE_MISMATCH")
        if runtime_instance_id != self._runtime_instance_id:
            raise ExecutionGrantConflict("WORKSPACE_RUNTIME_INSTANCE_MISMATCH")
        if revision != self._runtime_access_revision:
            raise ExecutionGrantConflict("WORKSPACE_RUNTIME_ACCESS_REVISION_MISMATCH")
        return ExecutionGrantClaims(
            subject=self._claim_text(claims, "sub"),
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            runtime_access_revision=revision,
            actions=tuple(actions),
            issued_at=issued_at,
            expires_at=expires_at,
            jti=self._claim_text(claims, "jti"),
        )

    def _public_key(self, kid: str) -> Ed25519PublicKey | None:
        with self._public_keys_lock:
            public_key = self._public_keys.get(kid)
        if public_key is not None:
            return public_key

        with self._public_keys_lock:
            public_key = self._public_keys.get(kid)
            if public_key is not None:
                return public_key
            try:
                reloaded = ManagerAssertionVerifier._load_public_keys(
                    self._public_key_set_file
                )
            except ManagerAssertionInvalid:
                return None
            self._public_keys = reloaded
            return reloaded.get(kid)

    @staticmethod
    def _text(value: Any) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 256
        ):
            raise ExecutionGrantInvalid()
        return value

    @classmethod
    def _claim_text(cls, claims: Mapping[str, Any], name: str) -> str:
        return cls._text(claims.get(name))

    @staticmethod
    def _revision(value: Any) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ExecutionGrantInvalid()
        return value

    @classmethod
    def _claim_revision(cls, claims: Mapping[str, Any], name: str) -> int:
        return cls._revision(claims.get(name))

    @staticmethod
    def _epoch(claims: Mapping[str, Any], name: str) -> int:
        value = claims.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ExecutionGrantInvalid()
        return value


@lru_cache(maxsize=1)
def get_execution_grant_verifier() -> ExecutionGrantVerifier:
    return ExecutionGrantVerifier.from_settings()


__all__ = [
    "ExecutionGrantClaims",
    "ExecutionGrantConflict",
    "ExecutionGrantInvalid",
    "ExecutionGrantVerifier",
    "get_execution_grant_verifier",
]
