"""Prompt Invocation Catalog configuration."""

from enum import StrEnum


class PromptInvocationTool(StrEnum):
    """Agentic tools that expose Prompt Invocations."""

    CLAUDE = "claude-code"
    CODEX = "codex"
    OPENCODE = "opencode"
