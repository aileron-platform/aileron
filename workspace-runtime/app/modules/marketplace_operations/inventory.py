"""Target client-wide effective resource inventory for user-copy planning."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Mapping

from aileron_marketplace_core import UserCopySourceProfile

from app.config.settings import Settings
from app.modules.claude_code.plugins.catalog import ClaudePluginsService
from app.modules.cli_settings.codex.plugin_resources import (
    CodexPluginResourceResolver,
)
from app.modules.cli_settings.user_scope.models import (
    AgentResourceScope,
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import (
    AgentResourcePathResolver,
    get_codex_path_resolver,
    get_user_scope_path_resolver,
)
from app.modules.cli_settings.user_scope.planner import (
    EffectiveUserCopyIdentity,
    UserCopyInventory,
)


class FilesystemUserCopyInventoryReader:
    """Enumerate every documented effective identity outside the user target."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def inventory(
        self,
        target_client: str,
        *,
        profile: UserCopySourceProfile | None = None,
    ) -> UserCopyInventory:
        if profile is None or target_client not in {"codex", "claude-code"}:
            return UserCopyInventory(complete=False)
        try:
            toml_documents: dict[Path, dict[str, Any]] = {}
            identities = self._project_and_local_identities(
                profile,
                target_client=target_client,
                toml_documents=toml_documents,
            )
            identities.extend(
                self._plugin_identities(
                    profile,
                    target_client=target_client,
                    toml_documents=toml_documents,
                )
            )
        except Exception:
            return UserCopyInventory(complete=False)
        unique = {
            (
                item.target_client,
                item.resource_type,
                item.resource_id,
                item.scope,
            ): item
            for item in identities
        }
        return UserCopyInventory(
            complete=True,
            effective_identities=tuple(
                unique[key]
                for key in sorted(
                    unique,
                    key=lambda item: tuple(
                        "" if part is None else part for part in item
                    ),
                )
            ),
        )

    def _project_and_local_identities(
        self,
        profile: UserCopySourceProfile,
        *,
        target_client: str,
        toml_documents: dict[Path, dict[str, Any]],
    ) -> list[EffectiveUserCopyIdentity]:
        workspace_root = Path(self._settings.AILERON_WORKSPACE_PATH)
        paths = AgentResourcePathResolver(
            user_home=get_user_scope_path_resolver().user_home,
            workspace_root=workspace_root,
        )
        agent = UserScopeAgent(target_client)
        identities: list[EffectiveUserCopyIdentity] = []
        for resource in profile.resources:
            project_path = _project_resource_path(
                paths,
                agent,
                resource.resource_type.value,
                resource.resource_id,
                _source_relative_target(resource.source_locator),
            )
            if project_path is not None and (
                project_path.exists() or project_path.is_symlink()
            ):
                identities.append(
                    _identity(
                        target_client,
                        resource.resource_type.value,
                        resource.resource_id,
                        "project",
                    )
                )

        desired_mcp = {
            resource.resource_id
            for resource in profile.resources
            if resource.resource_type.value == "mcp"
        }
        desired_hooks = [
            resource.resource_id
            for resource in profile.resources
            if resource.resource_type.value == "hook"
        ]
        if target_client == "claude-code":
            project_mcp = _json_mapping(
                paths.resolve(
                    agent,
                    AgentResourceScope.PROJECT,
                    UserScopeResource.MCP,
                ),
                "mcpServers",
            )
            identities.extend(
                _identity(target_client, "mcp", name, "project")
                for name in sorted(desired_mcp & set(project_mcp))
            )
            local_mcp = _claude_local_mcp(
                paths.resolve(
                    agent,
                    AgentResourceScope.LOCAL,
                    UserScopeResource.MCP,
                ),
                workspace_root,
            )
            identities.extend(
                _identity(target_client, "mcp", name, "local")
                for name in sorted(desired_mcp & set(local_mcp))
            )
            project_hooks = _json_hooks(
                paths.resolve(
                    agent,
                    AgentResourceScope.PROJECT,
                    UserScopeResource.HOOKS,
                )
            )
            local_hooks = _json_hooks(
                paths.resolve(
                    agent,
                    AgentResourceScope.LOCAL,
                    UserScopeResource.HOOKS,
                )
            )
            if project_hooks:
                identities.extend(
                    _identity(target_client, "hook", resource_id, "project")
                    for resource_id in desired_hooks
                )
            if local_hooks:
                identities.extend(
                    _identity(target_client, "hook", resource_id, "local")
                    for resource_id in desired_hooks
                )
        else:
            project_config = _cached_toml_document(
                paths.resolve(
                    agent,
                    AgentResourceScope.PROJECT,
                    UserScopeResource.SETTINGS,
                ),
                toml_documents,
            )
            project_mcp = _mapping(project_config.get("mcp_servers"))
            identities.extend(
                _identity(target_client, "mcp", name, "project")
                for name in sorted(desired_mcp & set(project_mcp))
            )
            if _json_hooks(
                paths.resolve(
                    agent,
                    AgentResourceScope.PROJECT,
                    UserScopeResource.HOOKS,
                )
            ):
                identities.extend(
                    _identity(target_client, "hook", resource_id, "project")
                    for resource_id in desired_hooks
                )
        return identities

    def _plugin_identities(
        self,
        profile: UserCopySourceProfile,
        *,
        target_client: str,
        toml_documents: dict[Path, dict[str, Any]],
    ) -> list[EffectiveUserCopyIdentity]:
        if target_client == "claude-code":
            roots = self._enabled_claude_plugin_roots()
        else:
            roots = self._enabled_codex_plugin_roots(toml_documents)
        identities: list[EffectiveUserCopyIdentity] = []
        desired_hooks = [
            resource.resource_id
            for resource in profile.resources
            if resource.resource_type.value == "hook"
        ]
        for root in roots:
            identities.extend(_native_plugin_file_identities(target_client, root))
            desired_mcp = {
                resource.resource_id
                for resource in profile.resources
                if resource.resource_type.value == "mcp"
            }
            mcp_servers = _json_mapping(root / ".mcp.json", "mcpServers")
            if target_client == "codex":
                manifest = _json_document(root / ".codex-plugin" / "plugin.json")
                declared = manifest.get("mcpServers")
                if isinstance(declared, str):
                    mcp_servers.update(_json_mapping(root / declared, "mcpServers"))
                elif isinstance(declared, Mapping):
                    mcp_servers.update(
                        {str(key): value for key, value in declared.items()}
                    )
            identities.extend(
                _identity(target_client, "mcp", name, "plugin")
                for name in sorted(desired_mcp & set(mcp_servers))
            )
            if _plugin_has_hooks(target_client, root):
                identities.extend(
                    _identity(target_client, "hook", resource_id, "plugin")
                    for resource_id in desired_hooks
                )
        return identities

    def _enabled_claude_plugin_roots(self) -> tuple[Path, ...]:
        plugin_state = (
            get_user_scope_path_resolver()
            .resolve(
                UserScopeAgent.CLAUDE_CODE,
                UserScopeResource.PLUGINS,
            )
            .runtime_path
            / "installed_plugins.json"
        )
        if plugin_state.exists():
            _json_document(plugin_state)
        snapshot = ClaudePluginsService().read_plugin_inventory(
            self._settings.AILERON_WORKSPACE_ID
        )
        return snapshot.enabled_roots()

    def _enabled_codex_plugin_roots(
        self,
        toml_documents: dict[Path, dict[str, Any]],
    ) -> tuple[Path, ...]:
        resolver = get_codex_path_resolver()
        configured: dict[str, Any] = {}
        for path in (
            resolver.resolve("user", "config"),
            resolver.resolve("project", "config"),
        ):
            configured.update(
                _mapping(_cached_toml_document(path, toml_documents).get("plugins"))
            )
        enabled_ids = {
            plugin_id
            for plugin_id, value in configured.items()
            if _mapping(value).get("enabled") is True
        }
        packages = CodexPluginResourceResolver(resolver).packages(enabled_ids)
        by_id = {package.plugin_id: package for package in packages}
        if set(by_id) != enabled_ids:
            raise ValueError("Enabled Codex plugin root is missing")
        return tuple(
            sorted(
                (package.package_root for package in by_id.values()),
                key=str,
            )
        )


def _identity(
    target_client: str,
    resource_type: str,
    resource_id: str,
    scope: str,
) -> EffectiveUserCopyIdentity:
    return EffectiveUserCopyIdentity(
        target_client=target_client,
        resource_type=resource_type,
        resource_id=resource_id,
        scope=scope,
    )


def _project_resource_path(
    paths: AgentResourcePathResolver,
    agent: UserScopeAgent,
    resource_type: str,
    resource_id: str,
    relative_target: str | None,
) -> Path | None:
    if resource_type == "instructions":
        return paths.resolve(
            agent,
            AgentResourceScope.PROJECT,
            UserScopeResource.INSTRUCTIONS,
        )
    roots = {
        "skill": (UserScopeResource.SKILLS, None),
        "subagent": (
            UserScopeResource.SUBAGENTS,
            ".md" if agent is UserScopeAgent.CLAUDE_CODE else ".toml",
        ),
        "command": (UserScopeResource.COMMANDS, ".md"),
        "output-style": (UserScopeResource.OUTPUT_STYLES, ".md"),
        "prompt": (UserScopeResource.PROMPTS, ".md"),
        "rule": (UserScopeResource.RULES, ".rules"),
    }
    definition = roots.get(resource_type)
    if definition is None:
        return None
    root_resource, suffix = definition
    directory = paths.resolve(
        agent,
        AgentResourceScope.PROJECT,
        root_resource,
    )
    if resource_type == "skill":
        return directory / resource_id
    relative = relative_target or f"{resource_id}{suffix or ''}"
    return directory / relative


def _source_relative_target(source_locator: str) -> str | None:
    prefixes = (
        "skills/",
        "agents/",
        "commands/",
        "output-styles/",
        "prompts/",
        "rules/",
    )
    for prefix in prefixes:
        if source_locator.startswith(prefix):
            return source_locator.removeprefix(prefix)
    return None


def _native_plugin_file_identities(
    target_client: str,
    root: Path,
) -> list[EffectiveUserCopyIdentity]:
    definitions = (
        (
            ("command", root / "commands", ".md"),
            ("subagent", root / "agents", ".md"),
            ("output-style", root / "output-styles", ".md"),
        )
        if target_client == "claude-code"
        else (("subagent", root / "agents", ".toml"),)
    )
    identities: list[EffectiveUserCopyIdentity] = []
    for resource_type, directory, suffix in definitions:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob(f"*{suffix}")):
            if path.is_file():
                identities.append(
                    _identity(
                        target_client,
                        resource_type,
                        path.relative_to(directory).as_posix().removesuffix(suffix),
                        "plugin",
                    )
                )
    skill_root = root / "skills"
    if skill_root.is_dir():
        identities.extend(
            _identity(target_client, "skill", path.parent.name, "plugin")
            for path in sorted(skill_root.glob("*/SKILL.md"))
            if path.is_file()
        )
    return identities


def _plugin_has_hooks(target_client: str, root: Path) -> bool:
    candidates = (
        (root / "hooks" / "hooks.json",)
        if target_client == "claude-code"
        else (
            root / "hooks.json",
            root / ".codex-plugin" / "hooks.json",
        )
    )
    return any(_json_hooks(path) for path in candidates)


def _claude_local_mcp(path: Path, workspace_root: Path) -> dict[str, Any]:
    document = _json_document(path)
    projects = _mapping(document.get("projects"))
    result: dict[str, Any] = {}
    candidates = {
        str(workspace_root),
        str(workspace_root.resolve(strict=False)),
    }
    for key in candidates:
        project = _mapping(projects.get(key))
        result.update(_mapping(project.get("mcpServers")))
    return result


def _json_hooks(path: Path) -> Any:
    document = _json_document(path)
    return document.get("hooks")


def _json_mapping(path: Path, key: str) -> dict[str, Any]:
    return _mapping(_json_document(path).get(key))


def _json_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def _toml_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("TOML document must be a table")
    return value


def _cached_toml_document(
    path: Path,
    documents: dict[Path, dict[str, Any]],
) -> dict[str, Any]:
    document = documents.get(path)
    if document is None:
        document = _toml_document(path)
        documents[path] = document
    return document


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["FilesystemUserCopyInventoryReader"]
