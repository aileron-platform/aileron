"""Typed models for runtime user-scope resources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class UserScopeAgent(str, Enum):
    """Agents with canonical user-scope filesystem locations."""

    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    OPENCODE = "opencode"


class UserScopeResource(str, Enum):
    """User-scope resource identities understood by the runtime."""

    INSTRUCTIONS = "instructions"
    SETTINGS = "settings"
    MCP = "mcp"
    HOOKS = "hooks"
    COMMANDS = "commands"
    SKILLS = "skills"
    SUBAGENTS = "subagents"
    OUTPUT_STYLES = "output_styles"
    PROMPTS = "prompts"
    RULES = "rules"
    MANAGED_REQUIREMENTS = "managed_requirements"
    PLUGINS = "plugins"


class AgentResourceScope(str, Enum):
    """Canonical provider resource layers."""

    USER = "user"
    PROJECT = "project"
    LOCAL = "local"


@dataclass(frozen=True)
class UserScopeLocation:
    """A logical user locator paired with its runtime filesystem path."""

    agent: UserScopeAgent
    runtime_path: Path
    logical_locator: str
    resource: UserScopeResource | None = None


class CodexLayer(str, Enum):
    """Editable Codex settings layers."""

    USER = "user"
    PROJECT = "project"


class CodexResource(str, Enum):
    """Codex settings resources with known filesystem locations."""

    AGENTS_MD = "agents_md"
    CONFIG = "config"
    RULES = "rules"
    HOOKS = "hooks"
    SKILLS = "skills"
    SUBAGENTS = "subagents"
    PROMPTS = "prompts"
    MANAGED_REQUIREMENTS = "managed_requirements"
