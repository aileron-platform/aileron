"""
Query Builder.

References agor-main's query-builder.ts
Builds Claude Agent SDK Query objects.
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

# Default max_turns limit to prevent agent infinite loop consuming tokens
DEFAULT_MAX_TURNS = 200
DEFAULT_ADDITIONAL_DIRS = ["/knowledge"]


def to_sdk_permission_mode(mode: BackendPermissionMode | None) -> SDKPermissionMode | None:
    """
    Convert backend permission mode to SDK permission mode.

    Backend now directly uses Claude SDK native modes:
    - default: prompt for every tool (strictest)
    - acceptEdits: auto-accept edits, prompt for other tools
    - bypassPermissions: allow all operations (no prompt)
    - plan: plan mode (generate plan but don't execute)
    - dontAsk: allow all operations (no prompt, no ask)
    - auto: automatically determine permission mode

    Since backend uses native modes, directly return corresponding SDK value.
    """
    if mode is None:
        return None

    # Backend enum values are already Claude SDK native modes, return directly
    return mode.value


@dataclass
class QueryOptions:
    """Query options."""

    task_id: Optional[str] = None
    resume: bool = True
    can_use_tool: Optional[CanUseTool] = None
    permission_mode: Optional[BackendPermissionMode] = None


class QueryBuilder:
    """
    Query Builder.

    Builds Claude Agent SDK Query objects.

    Stateless: each setup_query call creates a short-lived DB session to read session settings.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Query Builder.

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
        Setup Query.

        Args:
            session_id: Session ID
            prompt: User prompt
            options: Query options

        Returns:
            ClaudeAgentOptions: Claude Agent options
        """
        # Get session (short-lived session, avoid holding connection for long)
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            session_model = await session_repo.find_by_id(session_id)
            if not session_model:
                raise ValueError(f"Session {session_id} not found")

            session = session_repo.to_entity(session_model)

        # Get workspace path
        workspace_path = session.custom_context.get("workspace_path", "/workspace")
        custom_ctx = session.custom_context or {}

        # Convert permission mode: prioritize runtime-passed, otherwise read session-saved settings
        sdk_permission_mode = None
        if options.permission_mode:
            sdk_permission_mode = to_sdk_permission_mode(options.permission_mode)
        elif session.permission_config:
            sdk_permission_mode = to_sdk_permission_mode(session.permission_config.mode)

        # Tool whitelist/blacklist (read from custom_context)
        # Use dict.get(key, fallback) instead of or, preserve empty list [] (means forbid all tools)
        allowed_tools = custom_ctx.get("allowed_tools", custom_ctx.get("allowedTools"))
        disallowed_tools = custom_ctx.get("disallowed_tools", custom_ctx.get("disallowedTools"))

        # max_turns: read from custom_context, default DEFAULT_MAX_TURNS
        max_turns = custom_ctx.get("max_turns") or custom_ctx.get("maxTurns") or DEFAULT_MAX_TURNS

        # Thinking mode handling:
        # SDK docs warn: when max_thinking_tokens is explicitly set, StreamEvent will not be sent.
        # Therefore need to disable include_partial_messages when setting thinking tokens.
        max_thinking_tokens = None
        include_partial = True
        if session.model_settings and session.model_settings.thinking_mode:
            thinking_mode = session.model_settings.thinking_mode
            if thinking_mode == "manual" and session.model_settings.manual_thinking_tokens:
                max_thinking_tokens = session.model_settings.manual_thinking_tokens
                # Explicitly setting max_thinking_tokens causes StreamEvent not to be sent
                include_partial = False
                logger.info(
                    "Extended thinking enabled with %d tokens; "
                    "disabling include_partial_messages (StreamEvent not emitted with explicit thinking tokens)",
                    max_thinking_tokens,
                )

        # Build option parameters, prioritize existing session/context settings
        option_kwargs: Dict[str, Any] = {
            "cwd": workspace_path,
            "resume": session.sdk_session_id if options.resume else None,
            "model": session.model_settings.model if session.model_settings else None,
            "mcp_servers": custom_ctx.get("mcp_servers") or custom_ctx.get("mcpServers"),
            # Use preset type to avoid SDK injecting --system-prompt ""
            "system_prompt": SystemPromptPreset(type="preset", preset="claude_code"),
            # Streaming control: disable when extended thinking explicitly set (SDK limitation)
            "include_partial_messages": include_partial,
            # Setting source priority: user > project > local
            "setting_sources": ["user", "project", "local"],
            # Permission mode
            "permission_mode": sdk_permission_mode,
            # Permission callback (called when permission_mode is default)
            "can_use_tool": options.can_use_tool,
            # Increase JSON buffer size to 10MB, avoid large responses causing session disconnect
            "max_buffer_size": 10 * 1024 * 1024,
            # Tool restrictions
            "allowed_tools": allowed_tools,
            "disallowed_tools": disallowed_tools,
            # Conversation turn limit, prevent agent infinite loop
            "max_turns": max_turns,
            # Additional directories Claude Code may access besides cwd
            "add_dirs": DEFAULT_ADDITIONAL_DIRS,
            # Extended thinking
            "max_thinking_tokens": max_thinking_tokens,
            # TODO: add other options (hooks, commands, subagents, output_styles, env)
        }

        # Filter None to avoid overriding SDK defaults
        filtered_kwargs = {key: value for key, value in option_kwargs.items() if value is not None}

        agent_options = ClaudeAgentOptions(**filtered_kwargs)

        return agent_options
