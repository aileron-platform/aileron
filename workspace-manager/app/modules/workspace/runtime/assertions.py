"""Manager-owned Ed25519 assertions for runtime control-plane operations."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from app.config.settings import Settings, get_settings

RUNTIME_DRAIN_AUDIENCE = "workspace-runtime-drain"
TERMINAL_DRAIN_AUDIENCE = "workspace-terminal-drain"
BROWSER_EXTENSION_PAIRING_AUDIENCE = "workspace-browser-extension"
RUNTIME_COMMAND_AUDIENCE = "workspace-runtime-command"
WORKSPACE_RUNTIME_AUDIENCE = "workspace-runtime"
WORKSPACE_TERMINAL_AUDIENCE = "workspace-terminal"
EXECUTION_GRANT_KIND = "workspace-execution-access-grant"
MAX_ASSERTION_TTL_SECONDS = 60
_MAX_PRIVATE_KEY_FILE_BYTES = 64 * 1024
_MAX_PUBLIC_KEY_SET_FILE_BYTES = 256 * 1024
_EXECUTION_GRANT_ACTIONS = frozenset(
    {
        "runtime_read",
        "runtime_write",
        "workspace_settings",
        "terminal",
        "agent",
        "automation",
        "browser_automation",
    }
)


class RuntimeAssertionConfigurationError(ValueError):
    """Raised when assertion key material or metadata is not usable."""


class RuntimeAssertionContextError(ValueError):
    """Raised when a required assertion context value is invalid."""


@dataclass(frozen=True)
class DrainAssertionContext:
    """Identity and revision fence shared by Runtime and Terminal drain calls."""

    workspace_id: str
    expected_runtime_instance_id: str
    expected_mounted_revision: int
    target_revision: int
    drain_attempt_id: str
    deadline: datetime
    job_id: str


@dataclass(frozen=True)
class BrowserExtensionPairingAssertionContext:
    """Actor and workload fence for one browser extension pairing attempt."""

    actor_user_id: str
    workspace_id: str
    runtime_instance_id: str
    browser_workload_identity: str
    pairing_session_id: str


@dataclass(frozen=True)
class RuntimeCommandAssertionContext:
    """One Manager command bound to one Runtime generation."""

    workspace_id: str
    runtime_instance_id: str
    action: str


@dataclass(frozen=True)
class ExecutionGrantContext:
    """Actor, generation, revision, audience, and action fences for execution."""

    actor_user_id: str
    workspace_id: str
    runtime_instance_id: str
    runtime_access_revision: int
    audience: str
    actions: tuple[str, ...]


class RuntimeAssertionService:
    """Load one Manager private key and issue audience-bound drain assertions."""

    def __init__(
        self,
        *,
        private_key_file: Union[str, Path],
        key_id: str,
        issuer: str,
        ttl_seconds: int = MAX_ASSERTION_TTL_SECONDS,
        public_key_set_file: Optional[Union[str, Path]] = None,
        clock: Optional[Callable[[], datetime]] = None,
        jti_factory: Optional[Callable[[], str]] = None,
    ) -> None:
        self._key_id = self._validate_key_id(key_id)
        self._issuer = self._validate_issuer(issuer)
        self._ttl_seconds = self._validate_ttl(ttl_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._jti_factory = jti_factory or (lambda: str(uuid4()))
        self._private_key = self._load_private_key(Path(private_key_file))
        if public_key_set_file is not None:
            self._validate_active_public_key(Path(public_key_set_file))

    @classmethod
    def from_settings(
        cls, settings: Optional[Settings] = None
    ) -> "RuntimeAssertionService":
        """Create the service from file-path-only application settings."""

        resolved = settings or get_settings()
        public_key_set_file = resolved.RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE
        if not isinstance(public_key_set_file, str) or not public_key_set_file:
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key set file is not configured"
            )
        return cls(
            private_key_file=resolved.RUNTIME_ASSERTION_PRIVATE_KEY_FILE,
            public_key_set_file=public_key_set_file,
            key_id=resolved.RUNTIME_ASSERTION_KID,
            issuer=resolved.RUNTIME_ASSERTION_ISSUER,
            ttl_seconds=resolved.RUNTIME_ASSERTION_TTL_SECONDS,
        )

    def sign_runtime_drain(self, context: DrainAssertionContext) -> str:
        """Sign a one-time drain assertion accepted only by Runtime."""

        return self._sign_drain(context, audience=RUNTIME_DRAIN_AUDIENCE)

    def sign_terminal_drain(self, context: DrainAssertionContext) -> str:
        """Sign a one-time drain assertion accepted only by Terminal."""

        return self._sign_drain(context, audience=TERMINAL_DRAIN_AUDIENCE)

    def sign_browser_extension_pairing(
        self,
        context: BrowserExtensionPairingAssertionContext,
    ) -> str:
        """Sign a one-time assertion accepted only by the browser relay."""

        self._validate_browser_pairing_context(context)
        issued_at = self._as_epoch(self._clock(), field_name="clock")
        expires_at = issued_at + self._ttl_seconds
        jti = self._validate_required_text("jti", self._jti_factory())
        claims: Dict[str, object] = {
            "iss": self._issuer,
            "aud": BROWSER_EXTENSION_PAIRING_AUDIENCE,
            "action": "browser_automation",
            "actorUserId": context.actor_user_id,
            "workspaceId": context.workspace_id,
            "runtimeInstanceId": context.runtime_instance_id,
            "browserWorkloadIdentity": context.browser_workload_identity,
            "pairingSessionId": context.pairing_session_id,
            "iat": issued_at,
            "exp": expires_at,
            "jti": jti,
        }
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="EdDSA",
            headers={"kid": self._key_id, "typ": "JWT"},
        )

    def sign_runtime_command(self, context: RuntimeCommandAssertionContext) -> str:
        """Sign one Runtime command without sharing Manager credentials."""

        if not isinstance(context, RuntimeCommandAssertionContext):
            raise RuntimeAssertionContextError(
                "context must be a RuntimeCommandAssertionContext"
            )
        workspace_id = self._validate_required_text(
            "workspace_id", context.workspace_id
        )
        runtime_instance_id = self._validate_required_text(
            "runtime_instance_id", context.runtime_instance_id
        )
        action = self._validate_required_text("action", context.action)
        return self._sign_scoped(
            audience=RUNTIME_COMMAND_AUDIENCE,
            action=action,
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            ttl_seconds=self._ttl_seconds,
        )

    def sign_execution_grant(self, context: ExecutionGrantContext) -> str:
        """Sign a reusable-for-60-seconds Workspace Execution Access Grant."""

        if not isinstance(context, ExecutionGrantContext):
            raise RuntimeAssertionContextError(
                "context must be an ExecutionGrantContext"
            )
        actor_user_id = self._validate_required_text(
            "actor_user_id", context.actor_user_id
        )
        workspace_id = self._validate_required_text("workspace_id", context.workspace_id)
        runtime_instance_id = self._validate_required_text(
            "runtime_instance_id", context.runtime_instance_id
        )
        runtime_access_revision = self._validate_revision(
            "runtime_access_revision", context.runtime_access_revision
        )
        audience = context.audience
        if audience not in {WORKSPACE_RUNTIME_AUDIENCE, WORKSPACE_TERMINAL_AUDIENCE}:
            raise RuntimeAssertionContextError("audience is invalid")
        if (
            not isinstance(context.actions, tuple)
            or not context.actions
            or any(action not in _EXECUTION_GRANT_ACTIONS for action in context.actions)
            or len(set(context.actions)) != len(context.actions)
        ):
            raise RuntimeAssertionContextError("actions are invalid")
        actions = tuple(sorted(context.actions))
        if audience == WORKSPACE_RUNTIME_AUDIENCE and "terminal" in actions:
            raise RuntimeAssertionContextError("runtime audience cannot include terminal")
        if audience == WORKSPACE_TERMINAL_AUDIENCE and actions != ("terminal",):
            raise RuntimeAssertionContextError("terminal audience only accepts terminal")
        issued_at = self._as_epoch(self._clock(), field_name="clock")
        claims: Dict[str, object] = {
            "iss": self._issuer,
            "sub": actor_user_id,
            "aud": audience,
            "kind": EXECUTION_GRANT_KIND,
            "workspaceId": workspace_id,
            "runtimeInstanceId": runtime_instance_id,
            "runtimeAccessRevision": runtime_access_revision,
            "actions": list(actions),
            "iat": issued_at,
            "exp": issued_at + MAX_ASSERTION_TTL_SECONDS,
            "jti": self._validate_required_text("jti", self._jti_factory()),
        }
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="EdDSA",
            headers={"kid": self._key_id, "typ": "JWT"},
        )

    def _sign_scoped(
        self,
        *,
        audience: str,
        action: str,
        workspace_id: str,
        runtime_instance_id: str,
        ttl_seconds: int,
    ) -> str:
        issued_at = self._as_epoch(self._clock(), field_name="clock")
        claims: Dict[str, object] = {
            "iss": self._issuer,
            "aud": audience,
            "action": action,
            "workspaceId": workspace_id,
            "runtimeInstanceId": runtime_instance_id,
            "iat": issued_at,
            "exp": issued_at + ttl_seconds,
            "jti": self._validate_required_text("jti", self._jti_factory()),
        }
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="EdDSA",
            headers={"kid": self._key_id, "typ": "JWT"},
        )

    def _sign_drain(self, context: DrainAssertionContext, *, audience: str) -> str:
        issued_at = self._as_epoch(self._clock(), field_name="clock")
        deadline = self._validate_context(context)
        expires_at = min(issued_at + self._ttl_seconds, deadline)
        if expires_at <= issued_at:
            raise RuntimeAssertionContextError(
                "deadline must be later than assertion issue time"
            )

        jti = self._validate_required_text("jti", self._jti_factory())
        claims: Dict[str, object] = {
            "iss": self._issuer,
            "aud": audience,
            "action": "drain",
            "workspaceId": context.workspace_id,
            "expectedRuntimeInstanceId": context.expected_runtime_instance_id,
            "expectedMountedRevision": context.expected_mounted_revision,
            "targetRevision": context.target_revision,
            "drainAttemptId": context.drain_attempt_id,
            "deadline": deadline,
            "jobId": context.job_id,
            "iat": issued_at,
            "exp": expires_at,
            "jti": jti,
        }
        return jwt.encode(
            claims,
            self._private_key,
            algorithm="EdDSA",
            headers={"kid": self._key_id, "typ": "JWT"},
        )

    def _validate_context(self, context: DrainAssertionContext) -> int:
        if not isinstance(context, DrainAssertionContext):
            raise RuntimeAssertionContextError(
                "context must be a DrainAssertionContext"
            )
        self._validate_required_text("workspace_id", context.workspace_id)
        self._validate_required_text(
            "expected_runtime_instance_id", context.expected_runtime_instance_id
        )
        self._validate_required_text("drain_attempt_id", context.drain_attempt_id)
        self._validate_required_text("job_id", context.job_id)
        self._validate_revision(
            "expected_mounted_revision", context.expected_mounted_revision
        )
        self._validate_revision("target_revision", context.target_revision)
        return self._as_epoch(context.deadline, field_name="deadline")

    def _validate_browser_pairing_context(
        self,
        context: BrowserExtensionPairingAssertionContext,
    ) -> None:
        if not isinstance(context, BrowserExtensionPairingAssertionContext):
            raise RuntimeAssertionContextError(
                "context must be a BrowserExtensionPairingAssertionContext"
            )
        self._validate_required_text("actor_user_id", context.actor_user_id)
        self._validate_required_text("workspace_id", context.workspace_id)
        self._validate_required_text("runtime_instance_id", context.runtime_instance_id)
        self._validate_required_text(
            "browser_workload_identity",
            context.browser_workload_identity,
        )
        self._validate_required_text("pairing_session_id", context.pairing_session_id)

    def _validate_active_public_key(self, public_key_set_file: Path) -> None:
        configured_keys = self._load_public_key_set(public_key_set_file)
        current_key = self._public_jwk(self._private_key, self._key_id)
        configured_by_kid = {key["kid"]: key for key in configured_keys}
        configured_current = configured_by_kid.get(self._key_id)
        if configured_current is None:
            raise RuntimeAssertionConfigurationError(
                "Active public key is missing from the configured public key set"
            )
        if configured_current != current_key:
            raise RuntimeAssertionConfigurationError(
                "Active public key does not match the Manager private key"
            )

    @classmethod
    def _load_private_key(cls, private_key_file: Path) -> Ed25519PrivateKey:
        key_data = cls._read_file(
            private_key_file,
            maximum_bytes=_MAX_PRIVATE_KEY_FILE_BYTES,
            file_kind="private key",
        )
        private_key: Any
        try:
            private_key = serialization.load_pem_private_key(key_data, password=None)
        except (TypeError, ValueError):
            try:
                private_key = serialization.load_ssh_private_key(
                    key_data, password=None
                )
            except (TypeError, ValueError):
                raise RuntimeAssertionConfigurationError(
                    "Runtime assertion private key file is invalid"
                ) from None
        if not isinstance(private_key, Ed25519PrivateKey):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion private key must use Ed25519"
            )
        return private_key

    @classmethod
    def _load_public_key_set(cls, public_key_set_file: Path) -> List[Dict[str, str]]:
        encoded = cls._read_file(
            public_key_set_file,
            maximum_bytes=_MAX_PUBLIC_KEY_SET_FILE_BYTES,
            file_kind="public key set",
        )
        try:
            document = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key set file is invalid"
            ) from None
        if not isinstance(document, Mapping):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key set must be a JWKS object"
            )
        keys = document.get("keys")
        if not isinstance(keys, list):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key set must contain a keys array"
            )

        normalized: List[Dict[str, str]] = []
        seen_key_ids = set()
        for raw_key in keys:
            key = cls._normalize_public_jwk(raw_key)
            if key["kid"] in seen_key_ids:
                raise RuntimeAssertionConfigurationError(
                    "Runtime assertion public key IDs must be unique"
                )
            seen_key_ids.add(key["kid"])
            normalized.append(key)
        return normalized

    @classmethod
    def _normalize_public_jwk(cls, raw_key: object) -> Dict[str, str]:
        if not isinstance(raw_key, Mapping):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key is invalid"
            )
        if "d" in raw_key:
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key set must not contain private keys"
            )
        key_id = cls._validate_key_id(raw_key.get("kid"))
        key_type = raw_key.get("kty")
        curve = raw_key.get("crv")
        algorithm = raw_key.get("alg", "EdDSA")
        usage = raw_key.get("use", "sig")
        encoded_key = raw_key.get("x")
        if (
            key_type != "OKP"
            or curve != "Ed25519"
            or algorithm != "EdDSA"
            or usage != "sig"
            or not isinstance(encoded_key, str)
        ):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key must be an Ed25519 signing key"
            )
        try:
            padding = "=" * (-len(encoded_key) % 4)
            raw_public_key = base64.b64decode(
                encoded_key + padding,
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key is invalid"
            ) from None
        if len(raw_public_key) != 32:
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion public key is invalid"
            )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "use": "sig",
            "alg": "EdDSA",
            "kid": key_id,
            "x": cls._base64url(raw_public_key),
        }

    @classmethod
    def _public_jwk(cls, private_key: Ed25519PrivateKey, key_id: str) -> Dict[str, str]:
        raw_public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "use": "sig",
            "alg": "EdDSA",
            "kid": key_id,
            "x": cls._base64url(raw_public_key),
        }

    @staticmethod
    def _base64url(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _read_file(path: Path, *, maximum_bytes: int, file_kind: str) -> bytes:
        try:
            with path.open("rb") as key_file:
                content = key_file.read(maximum_bytes + 1)
        except (OSError, TypeError, ValueError):
            raise RuntimeAssertionConfigurationError(
                f"Runtime assertion {file_kind} file could not be read"
            ) from None
        if not content or len(content) > maximum_bytes:
            raise RuntimeAssertionConfigurationError(
                f"Runtime assertion {file_kind} file is invalid"
            )
        return content

    @staticmethod
    def _validate_key_id(value: object) -> str:
        if not isinstance(value, str):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion key ID is invalid"
            )
        if not value or len(value) > 128:
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion key ID is invalid"
            )
        if not value[0].isalnum() or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for character in value
        ):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion key ID is invalid"
            )
        return value

    @staticmethod
    def _validate_issuer(value: object) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 128
            or any(ord(character) < 32 for character in value)
        ):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion issuer is invalid"
            )
        return value

    @staticmethod
    def _validate_required_text(field_name: str, value: object) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 256
            or any(ord(character) < 32 for character in value)
        ):
            raise RuntimeAssertionContextError(f"{field_name} is invalid")
        return value

    @staticmethod
    def _validate_revision(field_name: str, value: object) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeAssertionContextError(f"{field_name} is invalid")
        return value

    @staticmethod
    def _validate_ttl(value: int) -> int:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
            or value > MAX_ASSERTION_TTL_SECONDS
        ):
            raise RuntimeAssertionConfigurationError(
                "Runtime assertion TTL must be between 1 and 60 seconds"
            )
        return value

    @staticmethod
    def _as_epoch(value: datetime, *, field_name: str) -> int:
        if not isinstance(value, datetime):
            raise RuntimeAssertionContextError(f"{field_name} is invalid")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.astimezone(timezone.utc).timestamp())


@lru_cache(maxsize=1)
def get_runtime_assertion_service() -> RuntimeAssertionService:
    """Return the process-wide assertion signer/verifier."""

    return RuntimeAssertionService.from_settings()


__all__ = [
    "BROWSER_EXTENSION_PAIRING_AUDIENCE",
    "BrowserExtensionPairingAssertionContext",
    "DrainAssertionContext",
    "EXECUTION_GRANT_KIND",
    "ExecutionGrantContext",
    "get_runtime_assertion_service",
    "MAX_ASSERTION_TTL_SECONDS",
    "RUNTIME_COMMAND_AUDIENCE",
    "RUNTIME_DRAIN_AUDIENCE",
    "RuntimeAssertionConfigurationError",
    "RuntimeAssertionContextError",
    "RuntimeAssertionService",
    "RuntimeCommandAssertionContext",
    "TERMINAL_DRAIN_AUDIENCE",
    "WORKSPACE_RUNTIME_AUDIENCE",
    "WORKSPACE_TERMINAL_AUDIENCE",
]
