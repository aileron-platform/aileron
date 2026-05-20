"""Map Aileron Codex permission settings to Codex SDK parameters."""

from __future__ import annotations

from codex_app_server.generated.v2_all import (
    AskForApproval,
    AskForApprovalValue,
    SandboxMode,
    SandboxPolicy,
)

from app.modules.agent_session.domain.enums import CodexApprovalPolicy, CodexSandboxMode
from app.modules.agent_session.domain.value_objects import CodexPermissionConfig


SANDBOX_MAP = {
    CodexSandboxMode.STRICT: SandboxMode.read_only,
    CodexSandboxMode.RELAXED: SandboxMode.workspace_write,
    CodexSandboxMode.OFF: SandboxMode.danger_full_access,
}

APPROVAL_MAP = {
    CodexApprovalPolicy.MANUAL: AskForApprovalValue.untrusted,
    CodexApprovalPolicy.SUGGEST: AskForApprovalValue.on_request,
    CodexApprovalPolicy.AUTO: AskForApprovalValue.never,
}


def _coerce_config(cfg: CodexPermissionConfig | None) -> CodexPermissionConfig:
    return cfg or CodexPermissionConfig()


def _approval_policy(cfg: CodexPermissionConfig) -> AskForApproval:
    return AskForApproval.model_validate(APPROVAL_MAP[cfg.approval_policy])


def _sandbox_policy(
    sandbox_mode: CodexSandboxMode,
    cwd: str,
) -> SandboxPolicy:
    if sandbox_mode == CodexSandboxMode.STRICT:
        payload = {"type": "readOnly", "networkAccess": True}
    elif sandbox_mode == CodexSandboxMode.RELAXED:
        payload = {
            "type": "workspaceWrite",
            "networkAccess": True,
            "writableRoots": [cwd],
        }
    else:
        payload = {"type": "dangerFullAccess"}
    return SandboxPolicy.model_validate(payload)


def to_thread_start_kwargs(cfg: CodexPermissionConfig | None, cwd: str) -> dict:
    """Build keyword arguments for AsyncCodex.thread_start."""
    cfg = _coerce_config(cfg)
    return {
        "cwd": cwd,
        "sandbox": SANDBOX_MAP[cfg.sandbox_mode],
        "approval_policy": _approval_policy(cfg),
    }


def to_thread_resume_kwargs(cfg: CodexPermissionConfig | None, cwd: str) -> dict:
    """Build keyword arguments for AsyncCodex.thread_resume."""
    return to_thread_start_kwargs(cfg, cwd)


def to_turn_kwargs(cfg: CodexPermissionConfig | None, cwd: str) -> dict:
    """Build keyword arguments for AsyncThread.turn."""
    if cfg is None:
        return {}
    cfg = _coerce_config(cfg)
    return {
        "cwd": cwd,
        "approval_policy": _approval_policy(cfg),
        "sandbox_policy": _sandbox_policy(cfg.sandbox_mode, cwd),
    }
