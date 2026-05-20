from __future__ import annotations

from codex_app_server.generated.v2_all import SandboxMode, ThreadStartParams, TurnStartParams

from app.modules.agent_session.domain.enums import CodexApprovalPolicy, CodexSandboxMode
from app.modules.agent_session.domain.value_objects import CodexPermissionConfig
from app.modules.agent_session.services.tools.codex.permission_mapper import (
    to_thread_resume_kwargs,
    to_thread_start_kwargs,
    to_turn_kwargs,
)


def test_permission_mapper_outputs_valid_sdk_params() -> None:
    for sandbox_mode in CodexSandboxMode:
        for approval_policy in CodexApprovalPolicy:
            cfg = CodexPermissionConfig(
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
            )

            thread_kwargs = to_thread_start_kwargs(cfg, "/workspace")
            ThreadStartParams(**thread_kwargs)
            assert "sandbox" in thread_kwargs
            assert thread_kwargs["sandbox"] in {
                SandboxMode.read_only,
                SandboxMode.workspace_write,
                SandboxMode.danger_full_access,
            }
            assert "config" not in thread_kwargs
            assert "model_reasoning_effort" not in thread_kwargs
            assert "service_tier" not in thread_kwargs
            assert "model_auto_compact_token_limit" not in thread_kwargs

            resume_kwargs = to_thread_resume_kwargs(cfg, "/workspace")
            assert "config" not in resume_kwargs

            turn_kwargs = to_turn_kwargs(cfg, "/workspace")
            params = TurnStartParams(thread_id="thread-1", input=[], **turn_kwargs)
            assert "sandbox" not in turn_kwargs
            assert "effort" not in turn_kwargs
            assert "service_tier" not in turn_kwargs
            assert "model" not in turn_kwargs
            assert "sandbox_policy" in turn_kwargs
            if sandbox_mode != CodexSandboxMode.OFF:
                assert params.sandbox_policy is not None
                assert params.sandbox_policy.root.network_access is True


def test_permission_mapper_always_enables_network_access() -> None:
    for sandbox_mode in (CodexSandboxMode.STRICT, CodexSandboxMode.RELAXED):
        cfg = CodexPermissionConfig(
            sandbox_mode=sandbox_mode,
            approval_policy=CodexApprovalPolicy.MANUAL,
        )

        turn_kwargs = to_turn_kwargs(cfg, "/workspace")
        params = TurnStartParams(thread_id="thread-1", input=[], **turn_kwargs)

        assert params.sandbox_policy is not None
        assert params.sandbox_policy.root.network_access is True


def test_turn_kwargs_omits_overrides_without_config() -> None:
    assert to_turn_kwargs(None, "/workspace") == {}
