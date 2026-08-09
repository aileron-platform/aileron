"""Unit tests for Manager-signed Runtime and Terminal drain assertions."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from pydantic import ValidationError

import app.modules.workspace.runtime.assertions as runtime_assertion_module
from app.config.settings import Settings
from app.modules.workspace.runtime.assertions import (
    BROWSER_EXTENSION_PAIRING_AUDIENCE,
    RUNTIME_COMMAND_AUDIENCE,
    RUNTIME_DRAIN_AUDIENCE,
    TERMINAL_DRAIN_AUDIENCE,
    BrowserExtensionPairingAssertionContext,
    DrainAssertionContext,
    RuntimeAssertionConfigurationError,
    RuntimeAssertionContextError,
    RuntimeAssertionService,
    RuntimeCommandAssertionContext,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def private_key_file(tmp_path: Path) -> Path:
    private_key = Ed25519PrivateKey.generate()
    path = tmp_path / "manager-ed25519.pem"
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return path


@pytest.fixture
def context(now: datetime) -> DrainAssertionContext:
    return DrainAssertionContext(
        workspace_id="workspace-123",
        expected_runtime_instance_id="runtime-instance-123",
        expected_mounted_revision=7,
        target_revision=8,
        drain_attempt_id="drain-attempt-123",
        deadline=now + timedelta(seconds=45),
        job_id="job-123",
    )


@pytest.fixture
def browser_pairing_context() -> BrowserExtensionPairingAssertionContext:
    return BrowserExtensionPairingAssertionContext(
        actor_user_id="user-123",
        workspace_id="workspace-123",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        browser_workload_identity="browser-container-or-pod-uid",
        pairing_session_id="pairing-session-123",
    )


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    assert isinstance(key, Ed25519PrivateKey)
    return key


def _public_jwk(private_key: Ed25519PrivateKey, key_id: str) -> Dict[str, str]:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
        "kid": key_id,
        "x": encoded,
    }


def _decode(
    token: str,
    private_key_file: Path,
    *,
    audience: str,
) -> Dict[str, object]:
    private_key = _load_private_key(private_key_file)
    return jwt.decode(
        token,
        private_key.public_key(),
        algorithms=["EdDSA"],
        audience=audience,
        issuer="workspace-manager",
    )


@pytest.mark.unit
def test_runtime_drain_assertion_has_required_camel_case_claims_and_kid(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v2",
        issuer="workspace-manager",
        ttl_seconds=60,
        clock=lambda: now,
        jti_factory=lambda: "jti-runtime-1",
    )

    token = service.sign_runtime_drain(context)

    header = jwt.get_unverified_header(token)
    claims = _decode(token, private_key_file, audience=RUNTIME_DRAIN_AUDIENCE)
    assert header == {"alg": "EdDSA", "kid": "manager-key-v2", "typ": "JWT"}
    assert claims == {
        "iss": "workspace-manager",
        "aud": RUNTIME_DRAIN_AUDIENCE,
        "action": "drain",
        "workspaceId": "workspace-123",
        "expectedRuntimeInstanceId": "runtime-instance-123",
        "expectedMountedRevision": 7,
        "targetRevision": 8,
        "drainAttemptId": "drain-attempt-123",
        "deadline": int(context.deadline.timestamp()),
        "jobId": "job-123",
        "iat": int(now.timestamp()),
        "exp": int(context.deadline.timestamp()),
        "jti": "jti-runtime-1",
    }
    assert not any("_" in claim_name for claim_name in claims)


@pytest.mark.unit
def test_runtime_command_assertion_is_generation_and_action_bound(
    private_key_file: Path,
    now: datetime,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v2",
        issuer="workspace-manager",
        ttl_seconds=30,
        clock=lambda: now,
        jti_factory=lambda: "runtime-command-jti",
    )

    token = service.sign_runtime_command(
        RuntimeCommandAssertionContext(
            workspace_id="workspace-123",
            runtime_instance_id="runtime-instance-456",
            action="marketplace.execute",
        )
    )

    claims = _decode(token, private_key_file, audience=RUNTIME_COMMAND_AUDIENCE)
    assert claims == {
        "iss": "workspace-manager",
        "aud": RUNTIME_COMMAND_AUDIENCE,
        "action": "marketplace.execute",
        "workspaceId": "workspace-123",
        "runtimeInstanceId": "runtime-instance-456",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + 30,
        "jti": "runtime-command-jti",
    }


@pytest.mark.unit
def test_runtime_command_public_contract_is_exported() -> None:
    assert {
        "get_runtime_assertion_service",
        "RUNTIME_COMMAND_AUDIENCE",
        "RuntimeCommandAssertionContext",
    } <= set(runtime_assertion_module.__all__)


@pytest.mark.unit
def test_runtime_and_terminal_assertions_are_audience_separated(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    jtis = iter(["jti-runtime", "jti-terminal"])
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
        jti_factory=lambda: next(jtis),
    )

    runtime_token = service.sign_runtime_drain(context)
    terminal_token = service.sign_terminal_drain(context)

    runtime_claims = _decode(
        runtime_token,
        private_key_file,
        audience=RUNTIME_DRAIN_AUDIENCE,
    )
    terminal_claims = _decode(
        terminal_token,
        private_key_file,
        audience=TERMINAL_DRAIN_AUDIENCE,
    )
    assert runtime_claims["jti"] == "jti-runtime"
    assert terminal_claims["jti"] == "jti-terminal"
    with pytest.raises(jwt.InvalidAudienceError):
        _decode(
            runtime_token,
            private_key_file,
            audience=TERMINAL_DRAIN_AUDIENCE,
        )
    with pytest.raises(jwt.InvalidAudienceError):
        _decode(
            terminal_token,
            private_key_file,
            audience=RUNTIME_DRAIN_AUDIENCE,
        )


@pytest.mark.unit
def test_each_signing_call_uses_a_new_single_use_jti(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
    )

    first = _decode(
        service.sign_runtime_drain(context),
        private_key_file,
        audience=RUNTIME_DRAIN_AUDIENCE,
    )
    second = _decode(
        service.sign_runtime_drain(context),
        private_key_file,
        audience=RUNTIME_DRAIN_AUDIENCE,
    )

    assert first["jti"] != second["jti"]


@pytest.mark.unit
def test_browser_extension_pairing_assertion_is_actor_and_workload_bound(
    private_key_file: Path,
    browser_pairing_context: BrowserExtensionPairingAssertionContext,
    now: datetime,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        ttl_seconds=45,
        clock=lambda: now,
        jti_factory=lambda: "pairing-jti-123",
    )

    token = service.sign_browser_extension_pairing(browser_pairing_context)

    claims = _decode(
        token,
        private_key_file,
        audience=BROWSER_EXTENSION_PAIRING_AUDIENCE,
    )
    assert claims == {
        "iss": "workspace-manager",
        "aud": BROWSER_EXTENSION_PAIRING_AUDIENCE,
        "action": "browser_automation",
        "actorUserId": "user-123",
        "workspaceId": "workspace-123",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "browserWorkloadIdentity": "browser-container-or-pod-uid",
        "pairingSessionId": "pairing-session-123",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + 45,
        "jti": "pairing-jti-123",
    }
    assert claims["exp"] - claims["iat"] <= 60
    assert not any("_" in claim_name for claim_name in claims)


@pytest.mark.unit
@pytest.mark.parametrize(
    "field_name",
    (
        "actor_user_id",
        "workspace_id",
        "runtime_instance_id",
        "browser_workload_identity",
        "pairing_session_id",
    ),
)
def test_browser_extension_pairing_rejects_missing_context(
    private_key_file: Path,
    browser_pairing_context: BrowserExtensionPairingAssertionContext,
    now: datetime,
    field_name: str,
) -> None:
    values = dict(browser_pairing_context.__dict__)
    values[field_name] = ""
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
    )

    with pytest.raises(RuntimeAssertionContextError, match=field_name):
        service.sign_browser_extension_pairing(
            BrowserExtensionPairingAssertionContext(**values)
        )


@pytest.mark.unit
def test_assertion_expiry_never_exceeds_sixty_seconds(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    context = DrainAssertionContext(
        workspace_id=context.workspace_id,
        expected_runtime_instance_id=context.expected_runtime_instance_id,
        expected_mounted_revision=context.expected_mounted_revision,
        target_revision=context.target_revision,
        drain_attempt_id=context.drain_attempt_id,
        deadline=now + timedelta(minutes=5),
        job_id=context.job_id,
    )
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        ttl_seconds=60,
        clock=lambda: now,
    )

    claims = _decode(
        service.sign_runtime_drain(context),
        private_key_file,
        audience=RUNTIME_DRAIN_AUDIENCE,
    )

    assert claims["exp"] - claims["iat"] == 60
    assert claims["deadline"] == int(context.deadline.timestamp())


@pytest.mark.unit
def test_expiry_is_capped_by_drain_deadline(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        ttl_seconds=60,
        clock=lambda: now,
    )

    claims = _decode(
        service.sign_runtime_drain(context),
        private_key_file,
        audience=RUNTIME_DRAIN_AUDIENCE,
    )

    assert claims["exp"] == claims["deadline"]
    assert claims["exp"] - claims["iat"] == 45


@pytest.mark.unit
def test_past_deadline_is_rejected(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
) -> None:
    context = DrainAssertionContext(
        workspace_id=context.workspace_id,
        expected_runtime_instance_id=context.expected_runtime_instance_id,
        expected_mounted_revision=context.expected_mounted_revision,
        target_revision=context.target_revision,
        drain_attempt_id=context.drain_attempt_id,
        deadline=now,
        job_id=context.job_id,
    )
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
    )

    with pytest.raises(RuntimeAssertionContextError, match="deadline"):
        service.sign_runtime_drain(context)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("workspace_id", ""),
        ("expected_runtime_instance_id", " runtime-instance-123"),
        ("drain_attempt_id", "drain\nattempt"),
        ("job_id", ""),
        ("expected_mounted_revision", -1),
        ("target_revision", True),
    ],
)
def test_invalid_required_context_is_rejected(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
    field_name: str,
    value: object,
) -> None:
    values = dict(context.__dict__)
    values[field_name] = value
    invalid_context = DrainAssertionContext(**values)
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
    )

    with pytest.raises(RuntimeAssertionContextError, match=field_name):
        service.sign_runtime_drain(invalid_context)


@pytest.mark.unit
def test_private_key_is_loaded_only_from_a_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing-private-key.pem"

    with pytest.raises(
        RuntimeAssertionConfigurationError,
        match="private key file could not be read",
    ):
        RuntimeAssertionService(
            private_key_file=missing,
            key_id="manager-key-v1",
            issuer="workspace-manager",
        )


@pytest.mark.unit
def test_non_ed25519_private_key_is_rejected(tmp_path: Path) -> None:
    rsa_key = generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "rsa-private-key.pem"
    path.write_bytes(
        rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    with pytest.raises(RuntimeAssertionConfigurationError, match="must use Ed25519"):
        RuntimeAssertionService(
            private_key_file=path,
            key_id="manager-key-v1",
            issuer="workspace-manager",
        )


@pytest.mark.unit
def test_configured_public_key_set_requires_active_key(
    tmp_path: Path,
    private_key_file: Path,
) -> None:
    previous_key = Ed25519PrivateKey.generate()
    public_key_set_file = tmp_path / "runtime-assertion-jwks.json"
    public_key_set_file.write_text(
        json.dumps({"keys": [_public_jwk(previous_key, "manager-key-v1")]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeAssertionConfigurationError, match="is missing"):
        RuntimeAssertionService(
            private_key_file=private_key_file,
            public_key_set_file=public_key_set_file,
            key_id="manager-key-v2",
            issuer="workspace-manager",
        )


@pytest.mark.unit
def test_configured_active_public_key_must_match_private_key(
    tmp_path: Path,
    private_key_file: Path,
) -> None:
    different_key = Ed25519PrivateKey.generate()
    public_key_set_file = tmp_path / "runtime-assertion-jwks.json"
    public_key_set_file.write_text(
        json.dumps({"keys": [_public_jwk(different_key, "manager-key-v2")]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeAssertionConfigurationError, match="does not match"):
        RuntimeAssertionService(
            private_key_file=private_key_file,
            public_key_set_file=public_key_set_file,
            key_id="manager-key-v2",
            issuer="workspace-manager",
        )


@pytest.mark.unit
def test_public_key_set_rejects_private_key_material(
    tmp_path: Path,
    private_key_file: Path,
) -> None:
    private_key = _load_private_key(private_key_file)
    jwk = _public_jwk(private_key, "manager-key-v1")
    jwk["d"] = "private-material"
    public_key_set_file = tmp_path / "runtime-assertion-jwks.json"
    public_key_set_file.write_text(
        json.dumps({"keys": [jwk]}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeAssertionConfigurationError, match="must not contain"):
        RuntimeAssertionService(
            private_key_file=private_key_file,
            public_key_set_file=public_key_set_file,
            key_id="manager-key-v1",
            issuer="workspace-manager",
        )


@pytest.mark.unit
def test_signing_does_not_log_assertion_claims_or_key_material(
    private_key_file: Path,
    context: DrainAssertionContext,
    now: datetime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = RuntimeAssertionService(
        private_key_file=private_key_file,
        key_id="manager-key-v1",
        issuer="workspace-manager",
        clock=lambda: now,
        jti_factory=lambda: "sensitive-jti",
    )

    with caplog.at_level(logging.DEBUG):
        token = service.sign_runtime_drain(context)

    output = caplog.text
    assert token not in output
    assert context.workspace_id not in output
    assert "sensitive-jti" not in output
    assert private_key_file.read_text(encoding="utf-8") not in output


@pytest.mark.unit
def test_settings_restrict_assertion_ttl_to_sixty_seconds() -> None:
    with pytest.raises(ValidationError):
        Settings(RUNTIME_ASSERTION_TTL_SECONDS=61, _env_file=None)


@pytest.mark.unit
def test_settings_expose_only_a_private_key_file_field() -> None:
    assert "RUNTIME_ASSERTION_PRIVATE_KEY_FILE" in Settings.model_fields
    assert "RUNTIME_ASSERTION_PRIVATE_KEY" not in Settings.model_fields


@pytest.mark.unit
def test_service_can_be_created_from_file_path_settings(
    private_key_file: Path,
    context: DrainAssertionContext,
    tmp_path: Path,
) -> None:
    public_key_set_file = tmp_path / "runtime-assertion-jwks.json"
    public_key_set_file.write_text(
        json.dumps(
            {
                "keys": [
                    _public_jwk(_load_private_key(private_key_file), "manager-key-v3")
                ]
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        RUNTIME_ASSERTION_PRIVATE_KEY_FILE=str(private_key_file),
        RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE=str(public_key_set_file),
        RUNTIME_ASSERTION_KID="manager-key-v3",
        RUNTIME_ASSERTION_ISSUER="workspace-manager",
        RUNTIME_ASSERTION_TTL_SECONDS=30,
        _env_file=None,
    )

    service = RuntimeAssertionService.from_settings(settings)
    token = service.sign_terminal_drain(context)

    assert jwt.get_unverified_header(token)["kid"] == "manager-key-v3"
    _decode(token, private_key_file, audience=TERMINAL_DRAIN_AUDIENCE)
