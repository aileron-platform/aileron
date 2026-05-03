"""Codex settings path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.config.settings import get_workspace_path


DEFAULT_AILERON_USER_HOME = Path("/home/developer")


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


@dataclass(frozen=True)
class CodexPathResolver:
    """Resolve Codex user/project settings paths.

    Aileron manages CODEX_HOME for Codex sessions. User-editable environment
    variables must not change these paths.
    """

    user_home: Path = DEFAULT_AILERON_USER_HOME
    workspace_root: Path = Path("/workspace")

    @property
    def codex_home(self) -> Path:
        return self.user_home / ".codex"

    def resolve(self, layer: CodexLayer | str, resource: CodexResource | str) -> Path:
        codex_layer = CodexLayer(layer)
        codex_resource = CodexResource(resource)
        if codex_layer == CodexLayer.USER:
            return self._resolve_user(codex_resource)
        return self._resolve_project(codex_resource)

    def _resolve_user(self, resource: CodexResource) -> Path:
        return {
            CodexResource.AGENTS_MD: self.codex_home / "AGENTS.md",
            CodexResource.CONFIG: self.codex_home / "config.toml",
            CodexResource.RULES: self.codex_home / "rules",
            CodexResource.HOOKS: self.codex_home / "hooks.json",
            CodexResource.SKILLS: self.user_home / ".agents" / "skills",
            CodexResource.SUBAGENTS: self.codex_home / "agents",
            CodexResource.PROMPTS: self.codex_home / "prompts",
            CodexResource.MANAGED_REQUIREMENTS: self.codex_home / "requirements.toml",
        }[resource]

    def _resolve_project(self, resource: CodexResource) -> Path:
        return {
            CodexResource.AGENTS_MD: self.workspace_root / "AGENTS.md",
            CodexResource.CONFIG: self.workspace_root / ".codex" / "config.toml",
            CodexResource.RULES: self.workspace_root / ".codex" / "rules",
            CodexResource.HOOKS: self.workspace_root / ".codex" / "hooks.json",
            CodexResource.SKILLS: self.workspace_root / ".agents" / "skills",
            CodexResource.SUBAGENTS: self.workspace_root / ".codex" / "agents",
            CodexResource.PROMPTS: self.workspace_root / ".codex" / "prompts",
            CodexResource.MANAGED_REQUIREMENTS: self.workspace_root / ".codex" / "requirements.toml",
        }[resource]


def get_codex_path_resolver() -> CodexPathResolver:
    """Return the runtime Codex path resolver."""

    return CodexPathResolver(
        user_home=DEFAULT_AILERON_USER_HOME,
        workspace_root=Path(get_workspace_path()),
    )
