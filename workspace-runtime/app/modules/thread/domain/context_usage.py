from __future__ import annotations

from typing import Any

from app.modules.thread.domain.enums import AgenticTool


def _token_count(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _codex_context_usage(raw_response: dict[str, Any]) -> int | None:
    token_usage = raw_response.get("token_usage")
    if isinstance(token_usage, dict):
        last = token_usage.get("last")
        if isinstance(last, dict) and "total_tokens" in last:
            return _token_count(last.get("total_tokens"))

        total = token_usage.get("total")
        if isinstance(total, dict) and "total_tokens" in total:
            return _token_count(total.get("total_tokens"))

        if "total_tokens" in token_usage:
            return _token_count(token_usage.get("total_tokens"))

    response = raw_response.get("response", {})
    if not isinstance(response, dict):
        return None
    turn = response.get("turn", {})
    if not isinstance(turn, dict):
        return None
    usage = turn.get("usage", {})
    if not isinstance(usage, dict):
        return None
    if "total_tokens" in usage:
        return _token_count(usage["total_tokens"])
    input_tokens = _token_count(usage.get("input_tokens")) or 0
    output_tokens = _token_count(usage.get("output_tokens")) or 0
    return input_tokens + output_tokens


def context_tokens_from_usage(
    tool: AgenticTool | str, usage: dict[str, Any] | None
) -> int | None:
    """Return context occupancy tokens from a canonical agent usage payload."""
    if not isinstance(usage, dict) or not usage:
        return None

    tool_value = tool.value if isinstance(tool, AgenticTool) else tool
    if tool_value == AgenticTool.CLAUDE.value:
        keys = (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
        if not any(key in usage for key in keys):
            return None
        return sum(int(usage.get(key) or 0) for key in keys)

    if tool_value == AgenticTool.CODEX.value:
        return _codex_context_usage(usage)

    if tool_value == AgenticTool.OPENCODE.value:
        if "total_tokens" in usage:
            return int(usage.get("total_tokens") or 0)
        if "prompt_tokens" in usage or "completion_tokens" in usage:
            return int(usage.get("prompt_tokens") or 0) + int(
                usage.get("completion_tokens") or 0
            )
        return None

    return None
