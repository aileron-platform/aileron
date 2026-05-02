from __future__ import annotations

import itertools

from codex_app_server.generated.v2_all import SandboxMode, ThreadStartParams, TurnStartParams

from app.modules.agent_session.domain.enums import CodexApprovalPolicy, CodexSandboxMode
from app.modules.agent_session.domain.value_objects import CodexPermissionConfig
from app.modules.agent_session.services.tools.codex.permission_mapper import (
    to_thread_start_kwargs,
    to_turn_kwargs,
)


def test_permission_mapper_outputs_valid_sdk_params() -> None:
    for sandbox_mode, approval_policy, network_access in itertools.product(
        CodexSandboxMode,
        CodexApprovalPolicy,
        [False, True],
    ):
        cfg = CodexPermissionConfig(
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
            network_access=network_access,
        )

        thread_kwargs = to_thread_start_kwargs(cfg, "/workspace")
        ThreadStartParams(**thread_kwargs)
        assert "sandbox" in thread_kwargs
        assert thread_kwargs["sandbox"] in {
            SandboxMode.read_only,
            SandboxMode.workspace_write,
            SandboxMode.danger_full_access,
        }

        turn_kwargs = to_turn_kwargs(cfg, "/workspace")
        TurnStartParams(thread_id="thread-1", input=[], **turn_kwargs)
        assert "sandbox" not in turn_kwargs
        assert "sandbox_policy" in turn_kwargs


def test_turn_kwargs_omits_overrides_without_config() -> None:
    assert to_turn_kwargs(None, "/workspace") == {}
