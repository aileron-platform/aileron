"""Canonical runtime paths for Agent user-scope resources."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from hashlib import sha256
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
    codex_home: Path | None = None
    claude_config_dir: Path | None = None

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
        runtime_path = self.user_home / relative_path
        logical_locator = f"~/{relative_path.as_posix()}"
        if (
            agent is UserScopeAgent.CODEX
            and self.codex_home is not None
            and relative_path.parts
            and relative_path.parts[0] == ".codex"
        ):
            runtime_path = self.codex_home.joinpath(*relative_path.parts[1:])
            logical_locator = f"$CODEX_HOME/{Path(*relative_path.parts[1:]).as_posix()}"
        elif agent is UserScopeAgent.CLAUDE_CODE and self.claude_config_dir is not None:
            if relative_path == Path(".claude"):
                runtime_path = self.claude_config_dir
                logical_locator = "$CLAUDE_CONFIG_DIR"
            elif relative_path.parts and relative_path.parts[0] == ".claude":
                suffix = Path(*relative_path.parts[1:])
                runtime_path = self.claude_config_dir / suffix
                logical_locator = f"$CLAUDE_CONFIG_DIR/{suffix.as_posix()}"
            elif relative_path == Path(".claude.json"):
                runtime_path = self.claude_config_dir / ".claude.json"
                logical_locator = "$CLAUDE_CONFIG_DIR/.claude.json"
        return UserScopeLocation(
            agent=agent,
            resource=resource,
            runtime_path=runtime_path,
            logical_locator=logical_locator,
        )


def target_client_state_root_id(
    target_client: str,
    *,
    paths: UserScopePathResolver,
) -> str:
    """Return an opaque proof for one client's effective user-scope root."""

    agent = UserScopeAgent(target_client)
    root = paths.resolve_root(agent).runtime_path.resolve(strict=False)
    identity = f"{target_client}\0{root.as_posix()}".encode("utf-8")
    return f"tcsr_{sha256(identity).hexdigest()}"


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
    codex_home_override: Path | None = None

    @property
    def codex_home(self) -> Path:
        return (
            UserScopePathResolver(
                self.user_home,
                codex_home=self.codex_home_override,
            )
            .resolve_root(UserScopeAgent.CODEX)
            .runtime_path
        )

    def resolve(self, layer: CodexLayer | str, resource: CodexResource | str) -> Path:
        codex_layer = CodexLayer(layer)
        codex_resource = CodexResource(resource)
        if codex_layer == CodexLayer.USER:
            return (
                UserScopePathResolver(
                    self.user_home,
                    codex_home=self.codex_home_override,
                )
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

    configured_codex_home = os.environ.get("CODEX_HOME")
    configured_claude_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    return UserScopePathResolver(
        user_home=runtime_user_home(),
        codex_home=(Path(configured_codex_home) if configured_codex_home else None),
        claude_config_dir=(
            Path(configured_claude_dir) if configured_claude_dir else None
        ),
    )


def get_codex_path_resolver() -> CodexPathResolver:
    """Return the runtime Codex path resolver."""

    user_paths = get_user_scope_path_resolver()
    return CodexPathResolver(
        user_home=user_paths.user_home,
        workspace_root=Path(get_workspace_path()),
        codex_home_override=user_paths.codex_home,
    )


def get_agent_resource_path_resolver() -> AgentResourcePathResolver:
    """Return the canonical provider path resolver for this runtime."""

    return AgentResourcePathResolver(
        user_home=runtime_user_home(),
        workspace_root=Path(get_workspace_path()),
    )
