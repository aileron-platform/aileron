"""Permission Mode Mapper.

Supports permission mode conversion between different AI agents.
References agor's permission-mode-mapper.ts implementation.

When generating cross-agent sessions (e.g., from Claude session to Gemini session)，
this module maps permission modes to corresponding modes of the target agent.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from ..domain.enums import AgenticTool, CodexApprovalPolicy, CodexSandboxMode, PermissionMode


# Extended permission mode types (includes all agent modes)
ExtendedPermissionMode = Literal[
    # Claude Code native modes
    "default",
    "acceptEdits",
    "bypassPermissions",
    "plan",
    "dontAsk",
    "auto",
    # Gemini native modes
    "autoEdit",
    "yolo",
    # Codex native modes
    "ask",
    "on-failure",
    "allow-all",
]


class CodexPermissionConfig(TypedDict):
    """Codex-specific permission configuration."""

    sandbox_mode: CodexSandboxMode
    approval_policy: CodexApprovalPolicy
    network_access: bool


def map_permission_mode(
    mode: str,
    target_tool: AgenticTool,
) -> PermissionMode:
    """Map permission mode to corresponding mode of target agent.

    Supports permission mode conversion between different AI agents:
    - Claude Code: default, acceptEdits, bypassPermissions, plan
    - Gemini: default, autoEdit, yolo
    - Codex: ask, auto, on-failure, allow-all

    Args:
        mode: Source permission mode
        target_tool: Target agent tool

    Returns:
        Mapped permission mode (PermissionMode enum)
    """
    if target_tool == AgenticTool.CLAUDE_CODE:
        return _map_to_claude_code(mode)
    elif target_tool == AgenticTool.GEMINI:
        return _map_to_gemini(mode)
    elif target_tool == AgenticTool.CODEX:
        return _map_to_codex(mode)
    elif target_tool == AgenticTool.OPENCODE:
        # OpenCode uses same modes as Gemini
        return _map_to_gemini(mode)
    else:
        # Default return ACCEPT_EDITS
        return PermissionMode.ACCEPT_EDITS


def _map_to_claude_code(mode: str) -> PermissionMode:
    """Map to Claude Code permission mode."""
    # Claude Code native modes return directly
    if mode in ("default", "acceptEdits", "bypassPermissions", "plan", "dontAsk", "auto"):
        mode_map = {
            "default": PermissionMode.DEFAULT,
            "acceptEdits": PermissionMode.ACCEPT_EDITS,
            "bypassPermissions": PermissionMode.BYPASS_PERMISSIONS,
            "plan": PermissionMode.PLAN,
            "dontAsk": PermissionMode.DONT_ASK,
            "auto": PermissionMode.AUTO,
        }
        return mode_map[mode]

    # Other agent mode mappings
    mapping = {
        # Gemini modes
        "autoEdit": PermissionMode.ACCEPT_EDITS,
        "yolo": PermissionMode.BYPASS_PERMISSIONS,
        # Codex modes
        "ask": PermissionMode.DEFAULT,
        "on-failure": PermissionMode.ACCEPT_EDITS,
        "allow-all": PermissionMode.BYPASS_PERMISSIONS,
    }

    return mapping.get(mode, PermissionMode.ACCEPT_EDITS)


def _map_to_gemini(mode: str) -> PermissionMode:
    """Map to Gemini permission mode.

    Gemini supported modes: default, autoEdit, yolo
    Return closest Claude Code equivalent mode.
    """
    # Gemini/OpenCode native modes
    if mode == "autoEdit":
        return PermissionMode.ACCEPT_EDITS
    elif mode == "yolo":
        return PermissionMode.BYPASS_PERMISSIONS
    elif mode == "default":
        return PermissionMode.DEFAULT

    # Other mode mappings
    mapping = {
        "acceptEdits": PermissionMode.ACCEPT_EDITS,
        "bypassPermissions": PermissionMode.BYPASS_PERMISSIONS,
        "plan": PermissionMode.DEFAULT,
        "dontAsk": PermissionMode.BYPASS_PERMISSIONS,
        "ask": PermissionMode.DEFAULT,
        "auto": PermissionMode.ACCEPT_EDITS,
        "on-failure": PermissionMode.ACCEPT_EDITS,
        "allow-all": PermissionMode.BYPASS_PERMISSIONS,
    }

    return mapping.get(mode, PermissionMode.ACCEPT_EDITS)


def _map_to_codex(mode: str) -> PermissionMode:
    """Map to Codex permission mode.

    Codex supported modes: ask, auto, on-failure, allow-all
    Return closest Claude Code equivalent mode.
    """
    # Codex native modes
    codex_modes = {
        "ask": PermissionMode.DEFAULT,
        "auto": PermissionMode.ACCEPT_EDITS,
        "on-failure": PermissionMode.ACCEPT_EDITS,
        "allow-all": PermissionMode.BYPASS_PERMISSIONS,
    }

    if mode in codex_modes:
        return codex_modes[mode]

    # Other mode mappings
    mapping = {
        "default": PermissionMode.DEFAULT,
        "acceptEdits": PermissionMode.ACCEPT_EDITS,
        "bypassPermissions": PermissionMode.BYPASS_PERMISSIONS,
        "plan": PermissionMode.DEFAULT,
        "dontAsk": PermissionMode.BYPASS_PERMISSIONS,
        "autoEdit": PermissionMode.ACCEPT_EDITS,
        "yolo": PermissionMode.BYPASS_PERMISSIONS,
    }

    return mapping.get(mode, PermissionMode.ACCEPT_EDITS)


def map_to_codex_permission_config(mode: str) -> CodexPermissionConfig:
    """Convert unified PermissionMode to Codex-specific configuration.

    Codex uses different configuration structure:
    - sandboxMode: strict, relaxed, off
    - approvalPolicy: auto, manual, suggest

    Args:
        mode: Permission mode string

    Returns:
        Codex-specific permission configuration dict
    """
    # First map to Codex internal mode
    codex_mode = _get_codex_mode(mode)

    configs = {
        "ask": CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.STRICT,
            approval_policy=CodexApprovalPolicy.MANUAL,
            network_access=False,
        ),
        "auto": CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.RELAXED,
            approval_policy=CodexApprovalPolicy.AUTO,
            network_access=True,
        ),
        "on-failure": CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.RELAXED,
            approval_policy=CodexApprovalPolicy.SUGGEST,
            network_access=True,
        ),
        "allow-all": CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.OFF,
            approval_policy=CodexApprovalPolicy.AUTO,
            network_access=True,
        ),
    }

    return configs.get(
        codex_mode,
        CodexPermissionConfig(
            sandbox_mode=CodexSandboxMode.STRICT,
            approval_policy=CodexApprovalPolicy.MANUAL,
            network_access=False,
        ),
    )


def _get_codex_mode(mode: str) -> str:
    """Get corresponding Codex internal mode name."""
    # Codex native modes
    if mode in ("ask", "auto", "on-failure", "allow-all"):
        return mode

    # Map other modes to Codex modes
    mapping = {
        "default": "ask",
        "acceptEdits": "auto",
        "bypassPermissions": "allow-all",
        "plan": "ask",
        "dontAsk": "allow-all",
        "autoEdit": "auto",
        "yolo": "allow-all",
    }

    return mapping.get(mode, "auto")


__all__ = [
    "map_permission_mode",
    "map_to_codex_permission_config",
    "CodexPermissionConfig",
]
