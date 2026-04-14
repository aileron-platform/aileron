"""Permission Mode Mapper.

支援不同 AI 代理之間的權限模式轉換。
參考 agor 的 permission-mode-mapper.ts 實現。

當生成跨代理會話時（例如從 Claude 會話生成 Gemini 會話），
此模組負責將權限模式映射到目標代理的對應模式。
"""

from __future__ import annotations

from typing import Literal, TypedDict

from ..domain.enums import AgenticTool, CodexApprovalPolicy, CodexSandboxMode, PermissionMode


# 擴展的權限模式類型（包含所有代理的模式）
ExtendedPermissionMode = Literal[
    # Claude Code 原生模式
    "default",
    "acceptEdits",
    "bypassPermissions",
    "plan",
    "dontAsk",
    "auto",
    # Gemini 原生模式
    "autoEdit",
    "yolo",
    # Codex 原生模式
    "ask",
    "on-failure",
    "allow-all",
]


class CodexPermissionConfig(TypedDict):
    """Codex 特定的權限配置."""

    sandbox_mode: CodexSandboxMode
    approval_policy: CodexApprovalPolicy
    network_access: bool


def map_permission_mode(
    mode: str,
    target_tool: AgenticTool,
) -> PermissionMode:
    """將權限模式映射到目標代理的對應模式.

    支援不同 AI 代理之間的權限模式轉換：
    - Claude Code: default, acceptEdits, bypassPermissions, plan
    - Gemini: default, autoEdit, yolo
    - Codex: ask, auto, on-failure, allow-all

    Args:
        mode: 源權限模式
        target_tool: 目標代理工具

    Returns:
        映射後的權限模式（PermissionMode 枚舉）
    """
    if target_tool == AgenticTool.CLAUDE_CODE:
        return _map_to_claude_code(mode)
    elif target_tool == AgenticTool.GEMINI:
        return _map_to_gemini(mode)
    elif target_tool == AgenticTool.CODEX:
        return _map_to_codex(mode)
    elif target_tool == AgenticTool.OPENCODE:
        # OpenCode 使用與 Gemini 相同的模式
        return _map_to_gemini(mode)
    else:
        # 預設返回 ACCEPT_EDITS
        return PermissionMode.ACCEPT_EDITS


def _map_to_claude_code(mode: str) -> PermissionMode:
    """映射到 Claude Code 權限模式."""
    # Claude Code 原生模式直接返回
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

    # 其他代理模式映射
    mapping = {
        # Gemini 模式
        "autoEdit": PermissionMode.ACCEPT_EDITS,
        "yolo": PermissionMode.BYPASS_PERMISSIONS,
        # Codex 模式
        "ask": PermissionMode.DEFAULT,
        "on-failure": PermissionMode.ACCEPT_EDITS,
        "allow-all": PermissionMode.BYPASS_PERMISSIONS,
    }

    return mapping.get(mode, PermissionMode.ACCEPT_EDITS)


def _map_to_gemini(mode: str) -> PermissionMode:
    """映射到 Gemini 權限模式.

    Gemini 支援的模式：default, autoEdit, yolo
    返回最接近的 Claude Code 對應模式。
    """
    # Gemini/OpenCode 原生模式
    if mode == "autoEdit":
        return PermissionMode.ACCEPT_EDITS
    elif mode == "yolo":
        return PermissionMode.BYPASS_PERMISSIONS
    elif mode == "default":
        return PermissionMode.DEFAULT

    # 其他模式映射
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
    """映射到 Codex 權限模式.

    Codex 支援的模式：ask, auto, on-failure, allow-all
    返回最接近的 Claude Code 對應模式。
    """
    # Codex 原生模式
    codex_modes = {
        "ask": PermissionMode.DEFAULT,
        "auto": PermissionMode.ACCEPT_EDITS,
        "on-failure": PermissionMode.ACCEPT_EDITS,
        "allow-all": PermissionMode.BYPASS_PERMISSIONS,
    }

    if mode in codex_modes:
        return codex_modes[mode]

    # 其他模式映射
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
    """將統一的 PermissionMode 轉換為 Codex 特定配置.

    Codex 使用不同的配置結構：
    - sandboxMode: strict, relaxed, off
    - approvalPolicy: auto, manual, suggest

    Args:
        mode: 權限模式字符串

    Returns:
        Codex 專用的權限配置字典
    """
    # 先映射到 Codex 內部模式
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
    """獲取對應的 Codex 內部模式名稱."""
    # Codex 原生模式
    if mode in ("ask", "auto", "on-failure", "allow-all"):
        return mode

    # 其他模式映射到 Codex 模式
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
