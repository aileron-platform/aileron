"""
Query Builder.

比照 agor-main 的 query-builder.ts
建構 Claude Agent SDK 的 Query 物件。
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import (
    CanUseTool,
    PermissionMode as SDKPermissionMode,
    SystemPromptPreset,
)

from app.database import async_session_scope
from app.modules.agent_session.domain.enums import PermissionMode as BackendPermissionMode
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository

# 預設 max_turns 限制，防止 agent 無限循環消耗 token
DEFAULT_MAX_TURNS = 200


def to_sdk_permission_mode(mode: BackendPermissionMode | None) -> SDKPermissionMode | None:
    """
    Convert backend permission mode to SDK permission mode.

    Backend 現在直接使用 Claude SDK 原生模式：
    - default: 每個工具都提示（最嚴格）
    - acceptEdits: 自動接受編輯，其他工具提示
    - bypassPermissions: 允許所有操作（不提示）
    - plan: 計劃模式（生成計劃但不執行）
    - dontAsk: 允許所有操作（不提示、不詢問）
    - auto: 自動決定權限模式

    由於後端已使用原生模式，直接返回對應的 SDK 值即可。
    """
    if mode is None:
        return None

    # 後端 enum 值已經是 Claude SDK 原生模式，直接返回
    return mode.value


@dataclass
class QueryOptions:
    """Query 選項."""

    task_id: Optional[str] = None
    resume: bool = True
    can_use_tool: Optional[CanUseTool] = None
    permission_mode: Optional[BackendPermissionMode] = None


class QueryBuilder:
    """
    Query Builder.

    建構 Claude Agent SDK 的 Query 物件。

    無狀態：每次呼叫 setup_query 都建立一個短期 DB session 讀取會話設定。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        初始化 Query Builder.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key

    async def setup_query(
        self,
        session_id: str,
        prompt: str,
        options: QueryOptions,
    ) -> ClaudeAgentOptions:
        """
        設定 Query.

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            options: Query 選項

        Returns:
            ClaudeAgentOptions: Claude Agent 選項
        """
        # 取得 session（短期 session，避免長時間持有連線）
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            session_model = await session_repo.find_by_id(session_id)
            if not session_model:
                raise ValueError(f"Session {session_id} not found")

            session = session_repo.to_entity(session_model)

        # 取得 workspace path
        workspace_path = session.custom_context.get("workspace_path", "/workspace")
        custom_ctx = session.custom_context or {}

        # 轉換權限模式：runtime 傳入的優先，否則讀 session 儲存的設定
        sdk_permission_mode = None
        if options.permission_mode:
            sdk_permission_mode = to_sdk_permission_mode(options.permission_mode)
        elif session.permission_config:
            sdk_permission_mode = to_sdk_permission_mode(session.permission_config.mode)

        # 工具白/黑名單（從 custom_context 讀取）
        # 使用 dict.get(key, fallback) 而非 or，保留空列表 []（表示禁止所有工具）
        allowed_tools = custom_ctx.get("allowed_tools", custom_ctx.get("allowedTools"))
        disallowed_tools = custom_ctx.get("disallowed_tools", custom_ctx.get("disallowedTools"))

        # max_turns：從 custom_context 讀取，預設 DEFAULT_MAX_TURNS
        max_turns = custom_ctx.get("max_turns") or custom_ctx.get("maxTurns") or DEFAULT_MAX_TURNS

        # Thinking 模式處理：
        # SDK 文件警告：當 max_thinking_tokens 明確設定時，StreamEvent 不會被發送。
        # 因此需要在設定 thinking tokens 時停用 include_partial_messages。
        max_thinking_tokens = None
        include_partial = True
        if session.model_settings and session.model_settings.thinking_mode:
            thinking_mode = session.model_settings.thinking_mode
            if thinking_mode == "manual" and session.model_settings.manual_thinking_tokens:
                max_thinking_tokens = session.model_settings.manual_thinking_tokens
                # 明確設定 max_thinking_tokens 會導致 StreamEvent 不發送
                include_partial = False
                logger.info(
                    "Extended thinking enabled with %d tokens; "
                    "disabling include_partial_messages (StreamEvent not emitted with explicit thinking tokens)",
                    max_thinking_tokens,
                )

        # 建立選項參數，優先取用已存在的 session / context 設定
        option_kwargs: Dict[str, Any] = {
            "cwd": workspace_path,
            "resume": session.sdk_session_id if options.resume else None,
            "model": session.model_settings.model if session.model_settings else None,
            "mcp_servers": custom_ctx.get("mcp_servers") or custom_ctx.get("mcpServers"),
            # 使用 preset 類型避免 SDK 帶入 --system-prompt ""
            "system_prompt": SystemPromptPreset(type="preset", preset="claude_code"),
            # 串流控制：當 extended thinking 明確設定時停用（SDK 限制）
            "include_partial_messages": include_partial,
            # 設定來源優先順序：user > project > local
            "setting_sources": ["user", "project", "local"],
            # 權限模式
            "permission_mode": sdk_permission_mode,
            # 權限回調（當 permission_mode 為 default 時會呼叫）
            "can_use_tool": options.can_use_tool,
            # 增加 JSON 緩衝區大小至 10MB，避免大型回應導致 session 中斷
            "max_buffer_size": 10 * 1024 * 1024,
            # 工具限制
            "allowed_tools": allowed_tools,
            "disallowed_tools": disallowed_tools,
            # 對話輪數限制，防止 agent 無限循環
            "max_turns": max_turns,
            # Extended thinking
            "max_thinking_tokens": max_thinking_tokens,
            # TODO: 添加其他選項（hooks, commands, subagents, output_styles, env）
        }

        # 過濾 None，避免覆寫 SDK 預設值
        filtered_kwargs = {key: value for key, value in option_kwargs.items() if value is not None}

        agent_options = ClaudeAgentOptions(**filtered_kwargs)

        return agent_options
