"""Canonical runtime paths for Agent user-scope resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config.settings import get_workspace_path

from .models import (
    AgentResourceScope,
    CodexLayer,
    CodexResource,
    UserScopeAgent,
    UserScopeLocation,
    UserScopeResource,
)


_AGENT_ROOTS: dict[UserScopeAgent, Path] = {
    UserScopeAgent.CLAUDE_CODE: Path(".claude"),
    UserScopeAgent.CODEX: Path(".codex"),
    UserScopeAgent.OPENCODE: Path(".config") / "opencode",
}

_RESOURCE_PATHS: dict[tuple[UserScopeAgent, UserScopeResource], Path] = {
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.INSTRUCTIONS): Path(
        ".claude/CLAUDE.md"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SETTINGS): Path(
        ".claude/settings.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.MCP): Path(".claude.json"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.HOOKS): Path(
        ".claude/settings.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.COMMANDS): Path(".claude/commands"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SKILLS): Path(".claude/skills"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SUBAGENTS): Path(".claude/agents"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.OUTPUT_STYLES): Path(
        ".claude/output-styles"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.PLUGINS): Path(".claude/plugins"),
    (UserScopeAgent.CODEX, UserScopeResource.INSTRUCTIONS): Path(".codex/AGENTS.md"),
    (UserScopeAgent.CODEX, UserScopeResource.SETTINGS): Path(".codex/config.toml"),
    (UserScopeAgent.CODEX, UserScopeResource.MCP): Path(".codex/config.toml"),
    (UserScopeAgent.CODEX, UserScopeResource.HOOKS): Path(".codex/hooks.json"),
    (UserScopeAgent.CODEX, UserScopeResource.SKILLS): Path(".codex/skills"),
    (UserScopeAgent.CODEX, UserScopeResource.SUBAGENTS): Path(".codex/agents"),
    (UserScopeAgent.CODEX, UserScopeResource.PROMPTS): Path(".codex/prompts"),
    (UserScopeAgent.CODEX, UserScopeResource.RULES): Path(".codex/rules"),
    (UserScopeAgent.CODEX, UserScopeResource.MANAGED_REQUIREMENTS): Path(
        ".codex/requirements.toml"
    ),
    (UserScopeAgent.CODEX, UserScopeResource.PLUGINS): Path(".codex/plugins"),
    (UserScopeAgent.OPENCODE, UserScopeResource.INSTRUCTIONS): Path(
        ".config/opencode/AGENTS.md"
    ),
    (UserScopeAgent.OPENCODE, UserScopeResource.SETTINGS): Path(
        ".config/opencode/opencode.json"
    ),
    (UserScopeAgent.OPENCODE, UserScopeResource.MCP): Path(
        ".config/opencode/opencode.json"
    ),
    (UserScopeAgent.OPENCODE, UserScopeResource.COMMANDS): Path(
        ".config/opencode/commands"
    ),
    (UserScopeAgent.OPENCODE, UserScopeResource.SKILLS): Path(
        ".config/opencode/skills"
    ),
    (UserScopeAgent.OPENCODE, UserScopeResource.SUBAGENTS): Path(
        ".config/opencode/agents"
    ),
}

_PROJECT_ROOTS: dict[UserScopeAgent, Path] = {
    UserScopeAgent.CLAUDE_CODE: Path(".claude"),
    UserScopeAgent.CODEX: Path(".codex"),
}

_PROJECT_RESOURCE_PATHS: dict[
    tuple[UserScopeAgent, UserScopeResource],
    Path,
] = {
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.INSTRUCTIONS): Path("CLAUDE.md"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SETTINGS): Path(
        ".claude/settings.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.MCP): Path(".mcp.json"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.HOOKS): Path(
        ".claude/settings.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.COMMANDS): Path(".claude/commands"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SKILLS): Path(".claude/skills"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SUBAGENTS): Path(".claude/agents"),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.OUTPUT_STYLES): Path(
        ".claude/output-styles"
    ),
    (UserScopeAgent.CODEX, UserScopeResource.INSTRUCTIONS): Path("AGENTS.md"),
    (UserScopeAgent.CODEX, UserScopeResource.SETTINGS): Path(".codex/config.toml"),
    (UserScopeAgent.CODEX, UserScopeResource.MCP): Path(".codex/config.toml"),
    (UserScopeAgent.CODEX, UserScopeResource.HOOKS): Path(".codex/hooks.json"),
    (UserScopeAgent.CODEX, UserScopeResource.SKILLS): Path(".codex/skills"),
    (UserScopeAgent.CODEX, UserScopeResource.SUBAGENTS): Path(".codex/agents"),
    (UserScopeAgent.CODEX, UserScopeResource.PROMPTS): Path(".codex/prompts"),
    (UserScopeAgent.CODEX, UserScopeResource.RULES): Path(".codex/rules"),
    (UserScopeAgent.CODEX, UserScopeResource.MANAGED_REQUIREMENTS): Path(
        ".codex/requirements.toml"
    ),
}

_LOCAL_RESOURCE_PATHS: dict[
    tuple[UserScopeAgent, UserScopeResource],
    Path,
] = {
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.SETTINGS): Path(
        ".claude/settings.local.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.HOOKS): Path(
        ".claude/settings.local.json"
    ),
    (UserScopeAgent.CLAUDE_CODE, UserScopeResource.MCP): Path(".claude.json"),
}

_CODEX_USER_RESOURCES: dict[CodexResource, UserScopeResource] = {
    CodexResource.AGENTS_MD: UserScopeResource.INSTRUCTIONS,
    CodexResource.CONFIG: UserScopeResource.SETTINGS,
    CodexResource.RULES: UserScopeResource.RULES,
    CodexResource.HOOKS: UserScopeResource.HOOKS,
    CodexResource.SKILLS: UserScopeResource.SKILLS,
    CodexResource.SUBAGENTS: UserScopeResource.SUBAGENTS,
    CodexResource.PROMPTS: UserScopeResource.PROMPTS,
    CodexResource.MANAGED_REQUIREMENTS: UserScopeResource.MANAGED_REQUIREMENTS,
}


def runtime_user_home() -> Path:
    """Resolve the runtime user's standard home directory."""

    return Path.home()


def logical_runtime_locator(
    path: Path,
    *,
    user_home: Path | None = None,
    workspace_root: Path | None = None,
    preferred_roots: tuple[tuple[Path, str], ...] = (),
) -> str | None:
    """Map a runtime path to a stable logical locator without exposing its root."""

    if not path.is_absolute():
        if ".." in path.parts:
            return None
        return path.as_posix()

    resolved_user_home = (user_home or runtime_user_home()).resolve(strict=False)
    roots = list(preferred_roots)
    if workspace_root is not None:
        roots.append((workspace_root, "."))
    roots.append((resolved_user_home, "~"))
    candidate = path.resolve(strict=False)
    for raw_root, prefix in roots:
        root = raw_root.resolve(strict=False)
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        if not relative.parts:
            return prefix
        return f"{prefix}/{relative.as_posix()}"
    return None


@dataclass(frozen=True)
class UserScopePathResolver:
    """Resolve typed logical locators and runtime paths from one user home."""

    user_home: Path = field(default_factory=runtime_user_home)

    def resolve_root(self, agent: UserScopeAgent | str) -> UserScopeLocation:
        resolved_agent = UserScopeAgent(agent)
        relative_path = _AGENT_ROOTS[resolved_agent]
        return self._location(resolved_agent, relative_path)

    def resolve(
        self,
        agent: UserScopeAgent | str,
        resource: UserScopeResource | str,
    ) -> UserScopeLocation:
        resolved_agent = UserScopeAgent(agent)
        resolved_resource = UserScopeResource(resource)
        try:
            relative_path = _RESOURCE_PATHS[(resolved_agent, resolved_resource)]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported user-scope resource: "
                f"{resolved_agent.value}/{resolved_resource.value}"
            ) from exc
        return self._location(
            resolved_agent,
            relative_path,
            resource=resolved_resource,
        )

    def _location(
        self,
        agent: UserScopeAgent,
        relative_path: Path,
        *,
        resource: UserScopeResource | None = None,
    ) -> UserScopeLocation:
        return UserScopeLocation(
            agent=agent,
            resource=resource,
            runtime_path=self.user_home / relative_path,
            logical_locator=f"~/{relative_path.as_posix()}",
        )


@dataclass(frozen=True)
class AgentResourcePathResolver:
    """Resolve canonical user, project, and local provider resources."""

    user_home: Path = field(default_factory=runtime_user_home)
    workspace_root: Path = Path("/workspace")

    def resolve_root(
        self,
        agent: UserScopeAgent | str,
        scope: AgentResourceScope | str,
    ) -> Path:
        resolved_agent = UserScopeAgent(agent)
        resolved_scope = AgentResourceScope(scope)
        if resolved_scope is AgentResourceScope.USER:
            return (
                UserScopePathResolver(self.user_home)
                .resolve_root(resolved_agent)
                .runtime_path
            )
        if resolved_scope is AgentResourceScope.PROJECT:
            try:
                return self.workspace_root / _PROJECT_ROOTS[resolved_agent]
            except KeyError as exc:
                raise ValueError(
                    f"Unsupported project provider: {resolved_agent.value}"
                ) from exc
        raise ValueError(
            f"Provider has no standalone local root: {resolved_agent.value}"
        )

    def resolve(
        self,
        agent: UserScopeAgent | str,
        scope: AgentResourceScope | str,
        resource: UserScopeResource | str,
    ) -> Path:
        resolved_agent = UserScopeAgent(agent)
        resolved_scope = AgentResourceScope(scope)
        resolved_resource = UserScopeResource(resource)
        if resolved_scope is AgentResourceScope.USER:
            return (
                UserScopePathResolver(self.user_home)
                .resolve(
                    resolved_agent,
                    resolved_resource,
                )
                .runtime_path
            )
        table = (
            _PROJECT_RESOURCE_PATHS
            if resolved_scope is AgentResourceScope.PROJECT
            else _LOCAL_RESOURCE_PATHS
        )
        try:
            relative = table[(resolved_agent, resolved_resource)]
        except KeyError as exc:
            raise ValueError(
                "Unsupported provider resource: "
                f"{resolved_agent.value}/{resolved_scope.value}/"
                f"{resolved_resource.value}"
            ) from exc
        root = (
            self.workspace_root
            if resolved_scope is AgentResourceScope.PROJECT
            else self.user_home
        )
        return root / relative


@dataclass(frozen=True)
class CodexPathResolver:
    """Resolve Codex user and project settings paths."""

    user_home: Path = field(default_factory=runtime_user_home)
    workspace_root: Path = Path("/workspace")

    @property
    def codex_home(self) -> Path:
        return (
            UserScopePathResolver(self.user_home)
            .resolve_root(UserScopeAgent.CODEX)
            .runtime_path
        )

    def resolve(self, layer: CodexLayer | str, resource: CodexResource | str) -> Path:
        codex_layer = CodexLayer(layer)
        codex_resource = CodexResource(resource)
        if codex_layer == CodexLayer.USER:
            return (
                UserScopePathResolver(self.user_home)
                .resolve(
                    UserScopeAgent.CODEX,
                    _CODEX_USER_RESOURCES[codex_resource],
                )
                .runtime_path
            )
        return self._resolve_project(codex_resource)

    def _resolve_project(self, resource: CodexResource) -> Path:
        return AgentResourcePathResolver(
            user_home=self.user_home,
            workspace_root=self.workspace_root,
        ).resolve(
            UserScopeAgent.CODEX,
            AgentResourceScope.PROJECT,
            _CODEX_USER_RESOURCES[resource],
        )


def get_user_scope_path_resolver() -> UserScopePathResolver:
    """Return a resolver bound to the current runtime user home."""

    return UserScopePathResolver(user_home=runtime_user_home())


def get_codex_path_resolver() -> CodexPathResolver:
    """Return the runtime Codex path resolver."""

    return CodexPathResolver(
        user_home=runtime_user_home(),
        workspace_root=Path(get_workspace_path()),
    )


def get_agent_resource_path_resolver() -> AgentResourcePathResolver:
    """Return the canonical provider path resolver for this runtime."""

    return AgentResourcePathResolver(
        user_home=runtime_user_home(),
        workspace_root=Path(get_workspace_path()),
    )
