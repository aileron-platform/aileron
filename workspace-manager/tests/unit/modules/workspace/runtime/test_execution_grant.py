"""Behavior tests for audience-bound Workspace Execution Access Grants."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.authorization.actor import AuthorizationActor
from app.modules.workspace.runtime.access import WorkspaceRuntimeAccessService
from app.modules.workspace.runtime.assertions import (
    ExecutionGrantContext,
    RuntimeAssertionContextError,
    RuntimeAssertionService,
)
from app.modules.workspace.router import (
    ExecutionGrantRequest,
    create_workspace_execution_grant,
)


def _signer(tmp_path: Path) -> tuple[RuntimeAssertionService, Ed25519PrivateKey]:
    private_key = Ed25519PrivateKey.generate()
    private_key_file = tmp_path / "manager-key.pem"
    private_key_file.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return (
        RuntimeAssertionService(
            private_key_file=private_key_file,
            key_id="manager-v1",
            issuer="workspace-manager",
            ttl_seconds=60,
            clock=lambda: datetime(2026, 8, 6, tzinfo=timezone.utc),
            jti_factory=lambda: "grant-jti",
        ),
        private_key,
    )


def test_runtime_grant_has_exact_fences_and_fixed_sixty_second_ttl(tmp_path: Path) -> None:
    signer, private_key = _signer(tmp_path)
    token = signer.sign_execution_grant(
        ExecutionGrantContext(
            actor_user_id="local-user-1",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            runtime_access_revision=7,
            audience="workspace-runtime",
            actions=("agent", "runtime_read"),
        )
    )

    claims = jwt.decode(
        token,
        private_key.public_key(),
        algorithms=["EdDSA"],
        audience="workspace-runtime",
        issuer="workspace-manager",
        options={"verify_exp": False},
    )
    assert claims == {
        "iss": "workspace-manager",
        "sub": "local-user-1",
        "aud": "workspace-runtime",
        "kind": "workspace-execution-access-grant",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "runtimeAccessRevision": 7,
        "actions": ["agent", "runtime_read"],
        "iat": 1785974400,
        "exp": 1785974460,
        "jti": "grant-jti",
    }


@pytest.mark.parametrize(
    ("audience", "actions"),
    [
        ("workspace-runtime", ("terminal",)),
        ("workspace-terminal", ("terminal", "runtime_read")),
        ("workspace-terminal", ()),
        ("all", ("runtime_read",)),
        ("workspace-runtime", ("all",)),
    ],
)
def test_grant_rejects_cross_audience_or_implicit_actions(
    tmp_path: Path,
    audience: str,
    actions: tuple[str, ...],
) -> None:
    signer, _ = _signer(tmp_path)
    with pytest.raises(RuntimeAssertionContextError):
        signer.sign_execution_grant(
            ExecutionGrantContext(
                actor_user_id="local-user-1",
                workspace_id="workspace-1",
                runtime_instance_id="11111111-1111-4111-8111-111111111111",
                runtime_access_revision=7,
                audience=audience,
                actions=actions,
            )
        )


def test_execution_grant_route_authorizes_each_explicit_action_and_signs_current_fences(
    monkeypatch,
) -> None:
    actor = AuthorizationActor(user_id="local-user-1", platform_role="member")
    workspace = SimpleNamespace(
        id="workspace-1",
        runtime_access_revision=7,
    )
    access_service = Mock()
    access_service.authorize.return_value = SimpleNamespace(
        actor=actor,
        workspace=workspace,
    )
    signer = Mock()
    signer.sign_execution_grant.return_value = "signed-grant"
    monkeypatch.setattr(
        RuntimeAssertionService,
        "from_settings",
        classmethod(lambda cls: signer),
    )
    payload = ExecutionGrantRequest(
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        audience="workspace-runtime",
        actions=("runtime_read", "agent"),
    )

    response = create_workspace_execution_grant(
        "workspace-1",
        SimpleNamespace(),
        payload,
        actor,
        access_service,
    )

    assert response.grant == "signed-grant"
    assert response.expires_in == 60
    assert [call.kwargs["action"] for call in access_service.authorize.call_args_list] == [
        "runtime_read",
        "agent",
    ]
    context = signer.sign_execution_grant.call_args.args[0]
    assert context == ExecutionGrantContext(
        actor_user_id="local-user-1",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        runtime_access_revision=7,
        audience="workspace-runtime",
        actions=("runtime_read", "agent"),
    )
