"""Prompt Invocation source adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

import yaml

from app.modules.claude_code.slash_commands.catalog import SlashCommandService
from app.modules.claude_code.documents import DocumentScope
from app.modules.cli_settings.slash_commands.config import SlashCommandScope
from app.modules.cli_settings.skills.catalog import CliSkillService
from app.modules.cli_settings.skills.config import (
    SkillTool,
    get_skill_config,
)
from app.modules.cli_settings.slash_commands.catalog import CliSlashCommandService
from app.modules.cli_settings.slash_commands.config import (
    SlashCommandTool,
    get_slash_command_config,
)

from .config import PromptInvocationTool
from .models import (
    PromptInvocationItem,
    PromptInvocationKind,
    PromptInvocationScope,
)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _scope(value: Any) -> PromptInvocationScope:
    raw_scope = value.value if hasattr(value, "value") else str(value)
    return PromptInvocationScope(raw_scope)


def _strip_document_extension(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    return path[: -len(suffix)] if suffix in {".md", ".toml"} else path


def _parse_skill_metadata(content: str) -> dict[str, str]:
    if not content.startswith("---\n"):
        return {}
    end_marker = content.find("\n---\n", 4)
    if end_marker == -1:
        return {}
    try:
        parsed = yaml.safe_load(content[4:end_marker])
    except yaml.YAMLError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        key: str(value).strip()
        for key, value in parsed.items()
        if key in {"name", "description"} and value is not None
    }


def _default_slash_command_service(tool: PromptInvocationTool) -> Any:
    if tool is PromptInvocationTool.CLAUDE:
        return SlashCommandService()
    slash_tool = SlashCommandTool(tool.value)
    return CliSlashCommandService(get_slash_command_config(slash_tool))


def _refresh_claude_plugin_cache(workspace_id: str) -> None:
    from app.modules.claude_code.plugins.loader import get_plugin_loader
    from app.modules.claude_code.plugins.plugin_inventory import (
        clear_claude_plugin_inventory_cache,
    )
    from app.modules.claude_code.settings.dependencies import get_settings_service

    clear_claude_plugin_inventory_cache()
    get_plugin_loader(get_settings_service()).clear_cache(workspace_id)


class SlashCommandPromptInvocationSource:
    """Load one Slash Command scope through the existing Runtime service."""

    def __init__(
        self,
        tool: PromptInvocationTool,
        scope: PromptInvocationScope,
        service_factory: Callable[[], Any] | None = None,
        refresh_plugin_cache: Callable[[str], None] | None = None,
    ) -> None:
        self._tool = tool
        self._scope = scope
        self.source_id = f"{scope.value}-slash-commands"
        self._service_factory = service_factory or (
            lambda: _default_slash_command_service(tool)
        )
        self._refresh_plugin_cache = (
            refresh_plugin_cache or _refresh_claude_plugin_cache
        )
        self.scopes = (scope,)

    def load(self, workspace_id: str) -> list[PromptInvocationItem]:
        service = self._service_factory()
        if self._tool is PromptInvocationTool.CLAUDE:
            if self._scope is PromptInvocationScope.PLUGIN:
                self._refresh_plugin_cache(workspace_id)
            response = service.list_scopes(
                workspace_id,
                DocumentScope(self._scope.value),
                strict_plugin_errors=True,
            )
        else:
            response = service.list_scopes(
                workspace_id,
                SlashCommandScope(self._scope.value),
            )
        items: list[PromptInvocationItem] = []
        for summary in _field(response, "items", []):
            path = str(_field(summary, "path", "")).lstrip("/")
            if not path:
                continue
            scope = _scope(_field(summary, "scope"))
            plugin_name = _field(summary, "plugin_name") or _field(
                summary, "pluginName"
            )
            plugin_name = str(plugin_name).strip() if plugin_name else None
            command_name = _strip_document_extension(path)
            display_name = (
                f"{plugin_name}:{command_name}" if plugin_name else command_name
            )
            source_key = f"{plugin_name}:{path}" if plugin_name else path
            items.append(
                PromptInvocationItem(
                    id=(
                        f"{self._tool.value}:slash-command:"
                        f"{scope.value}:{source_key}"
                    ),
                    sourceKey=source_key,
                    fileName=path,
                    kind=PromptInvocationKind.SLASH_COMMAND,
                    scope=scope,
                    pluginName=plugin_name,
                    displayName=display_name,
                    category=plugin_name or scope.value,
                    description=str(_field(summary, "description") or ""),
                    invocation=f"/{display_name}",
                )
            )
        return items


class SkillPromptInvocationSource:
    """Load one local Skill scope without making Runtime HTTP calls."""

    def __init__(
        self,
        tool: PromptInvocationTool,
        scope: PromptInvocationScope,
        service_factory: Callable[[str], Any] | None = None,
        refresh_plugin_cache: Callable[[str], None] | None = None,
    ) -> None:
        self._tool = tool
        self._scope = scope
        self.source_id = f"{scope.value}-skills"
        self.scopes = (scope,)
        self._service_factory = service_factory or self._build_service
        self._refresh_plugin_cache = (
            refresh_plugin_cache or _refresh_claude_plugin_cache
        )

    def _build_service(self, workspace_id: str) -> CliSkillService:
        skill_tool = SkillTool(self._tool.value)
        return CliSkillService(get_skill_config(skill_tool), workspace_id)

    def load(self, workspace_id: str) -> list[PromptInvocationItem]:
        service = self._service_factory(workspace_id)
        if (
            self._tool is PromptInvocationTool.CLAUDE
            and self._scope is PromptInvocationScope.PLUGIN
        ):
            self._refresh_plugin_cache(workspace_id)
        service.clear_tree_cache(self._scope.value)
        tree = service.get_tree(
            "/",
            self._scope.value,
            max_depth=8,
        )
        items: list[PromptInvocationItem] = []
        for node in self._skill_documents(_field(tree, "nodes", [])):
            path = str(_field(node, "path", "")).lstrip("/")
            if not path:
                continue
            segments = [segment for segment in path.split("/") if segment]
            fallback_name = segments[-2] if len(segments) >= 2 else "skill"
            skill_name = str(_field(node, "skillName") or "").strip()
            description = str(_field(node, "skillDescription") or "").strip()
            if not skill_name or not description:
                metadata = self._load_metadata(service, path)
                skill_name = skill_name or metadata.get("name", "")
                description = description or metadata.get("description", "")
            skill_name = skill_name or fallback_name
            plugin_name = self._plugin_name(segments)
            display_name = f"{plugin_name}:{skill_name}" if plugin_name else skill_name
            invocation_prefix = "$" if self._tool is PromptInvocationTool.CODEX else "/"
            items.append(
                PromptInvocationItem(
                    id=(f"{self._tool.value}:skill:" f"{self._scope.value}:{path}"),
                    sourceKey=path,
                    fileName="SKILL.md",
                    kind=PromptInvocationKind.SKILL,
                    scope=self._scope,
                    pluginName=plugin_name,
                    displayName=display_name,
                    category=plugin_name or self._scope.value,
                    description=description,
                    invocation=f"{invocation_prefix}{display_name}",
                )
            )
        return items

    def _load_metadata(self, service: Any, path: str) -> dict[str, str]:
        response = service.read_file(path, self._scope.value)
        return _parse_skill_metadata(str(_field(response, "content", "")))

    def _plugin_name(self, segments: list[str]) -> str | None:
        if self._scope is not PromptInvocationScope.PLUGIN or not segments:
            return None
        return segments[0].split("@", 1)[0]

    @classmethod
    def _skill_documents(cls, nodes: list[Any]) -> list[Any]:
        documents: list[Any] = []
        for node in nodes:
            if _field(node, "type") == "file" and _field(node, "name") == "SKILL.md":
                documents.append(node)
                continue
            documents.extend(cls._skill_documents(_field(node, "children", []) or []))
        return documents


class CodexPluginSkillPromptInvocationSource:
    """Load Codex plugin Skills from the Codex plugin inventory."""

    source_id = "plugin-skills"
    scopes = (PromptInvocationScope.PLUGIN,)

    def load(self, workspace_id: str) -> list[PromptInvocationItem]:
        from app.modules.cli_settings.codex.plugin_resources import (
            clear_codex_plugin_inventory_cache,
        )
        from app.modules.cli_settings.codex.settings import (
            CodexSettingsIntent,
            get_codex_agent_settings,
        )

        service = get_codex_agent_settings()
        clear_codex_plugin_inventory_cache()
        service.execute(
            CodexSettingsIntent.REFRESH_CACHE,
            workspace_id=workspace_id,
            capability="skills",
            scope="plugin",
        )
        response = service.execute(
            CodexSettingsIntent.LIST_FILES,
            workspace_id,
            "plugin",
            "skills",
        )
        items: list[PromptInvocationItem] = []
        for summary in response.files:
            plugin_id = str(summary.metadata.get("pluginId") or "").strip()
            plugin_name = str(
                summary.metadata.get("pluginName") or plugin_id or "plugin"
            ).strip()
            content_response = service.execute(
                CodexSettingsIntent.GET_FILE,
                workspace_id,
                "plugin",
                "skills",
                summary.path,
                plugin_id=plugin_id or None,
            )
            metadata = _parse_skill_metadata(content_response.content)
            fallback_name = PurePosixPath(summary.path).parent.name or summary.name
            skill_name = metadata.get("name") or fallback_name
            display_name = f"{plugin_name}:{skill_name}"
            source_key = f"{plugin_id}:{summary.path}"
            items.append(
                PromptInvocationItem(
                    id=f"codex:skill:plugin:{source_key}",
                    sourceKey=source_key,
                    fileName="SKILL.md",
                    kind=PromptInvocationKind.SKILL,
                    scope=PromptInvocationScope.PLUGIN,
                    pluginName=plugin_name,
                    displayName=display_name,
                    category=plugin_name,
                    description=metadata.get("description", ""),
                    invocation=f"${display_name}",
                )
            )
        return items


def build_prompt_invocation_sources(tool: PromptInvocationTool) -> tuple[Any, ...]:
    """Build independently loadable sources for one Agentic Tool."""

    sources: list[Any] = [
        SlashCommandPromptInvocationSource(tool, PromptInvocationScope.PROJECT),
        SlashCommandPromptInvocationSource(tool, PromptInvocationScope.USER),
        SkillPromptInvocationSource(tool, PromptInvocationScope.PROJECT),
        SkillPromptInvocationSource(tool, PromptInvocationScope.USER),
    ]
    if tool is PromptInvocationTool.CLAUDE:
        sources.append(
            SlashCommandPromptInvocationSource(tool, PromptInvocationScope.PLUGIN)
        )
        sources.append(SkillPromptInvocationSource(tool, PromptInvocationScope.PLUGIN))
    if tool is PromptInvocationTool.CODEX:
        sources.append(CodexPluginSkillPromptInvocationSource())
    return tuple(sources)
