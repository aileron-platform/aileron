"""User Copy projection registry keyed by package format and target client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aileron_marketplace_core import (
    PluginPackageFormat,
    TargetClient,
    UserCopyResourceType,
    UserCopySourceResource,
)


@dataclass(frozen=True)
class ProjectedUserCopyResource:
    """A neutral source resource plus target-owned mutation semantics."""

    source: UserCopySourceResource
    target_resource: str
    copy_semantics: str
    relative_target: str | None = None
    structured_value: Any | None = None


@dataclass(frozen=True)
class SkippedUserCopyResource:
    """A source resource that cannot be represented by this projection."""

    source: UserCopySourceResource
    code: str


@dataclass(frozen=True)
class UserCopyProjectionResult:
    """Exactly one projected or skipped source resource."""

    projected: ProjectedUserCopyResource | None = None
    skipped: SkippedUserCopyResource | None = None

    def __post_init__(self) -> None:
        if (self.projected is None) == (self.skipped is None):
            raise ValueError("projection-result-invalid")


@dataclass(frozen=True)
class UserCopyProjection:
    """One exact package-format to target-client projection contract."""

    package_format: PluginPackageFormat
    target_client: TargetClient

    def project(
        self,
        resource: UserCopySourceResource,
    ) -> UserCopyProjectionResult:
        if self.package_format is PluginPackageFormat.AGENT_PLUGIN_V1:
            return self._project_agent_plugin(resource)
        return self._project_native(resource)

    def _project_agent_plugin(
        self,
        resource: UserCopySourceResource,
    ) -> UserCopyProjectionResult:
        if self.target_client is not TargetClient.CODEX:
            return _skipped(resource, "projection-not-supported")
        if resource.resource_type is UserCopyResourceType.SKILL:
            prefix = "skills/"
            if not resource.source_locator.startswith(prefix):
                return _skipped(resource, "source-not-allowed")
            relative = resource.source_locator.removeprefix(prefix)
            if not relative or "/" in relative or relative != resource.resource_id:
                return _skipped(resource, "source-not-allowed")
            return _projected(
                resource,
                target_resource="skills",
                copy_semantics="create-directory",
                relative_target=relative,
            )
        if resource.resource_type is UserCopyResourceType.MCP:
            return self._project_agent_plugin_mcp(resource)
        return _skipped(resource, "portable-resource-unsupported")

    def _project_agent_plugin_mcp(
        self,
        resource: UserCopySourceResource,
    ) -> UserCopyProjectionResult:
        value = resource.structured_value
        if not isinstance(value, Mapping):
            return _skipped(resource, "mcp-entry-invalid")
        if _contains_string(value, "${PLUGIN_DATA}"):
            return _skipped(resource, "plugin-data-lifecycle-unsupported")
        transport = value.get("type")
        converted: dict[str, Any]
        if transport == "stdio":
            command = value.get("command")
            if not isinstance(command, str) or not command:
                return _skipped(resource, "mcp-entry-invalid")
            converted = {"command": command}
            for field in ("args", "env", "cwd"):
                if field in value:
                    converted[field] = value[field]
        elif transport == "streamable-http":
            url = value.get("url")
            if not isinstance(url, str) or not url:
                return _skipped(resource, "mcp-entry-invalid")
            converted = {"url": url}
            if "headers" in value:
                converted["http_headers"] = value["headers"]
        elif transport == "sse":
            return _skipped(resource, "mcp-transport-unsupported")
        else:
            return _skipped(resource, "mcp-entry-invalid")
        return _projected(
            resource,
            target_resource="mcp",
            copy_semantics="merge-config-entry",
            structured_value=converted,
        )

    def _project_native(
        self,
        resource: UserCopySourceResource,
    ) -> UserCopyProjectionResult:
        expected_client = (
            TargetClient.CODEX
            if self.package_format is PluginPackageFormat.CODEX_NATIVE
            else TargetClient.CLAUDE_CODE
        )
        if self.target_client is not expected_client:
            return _skipped(resource, "projection-not-supported")
        mappings = (
            _CODEX_NATIVE_TARGETS
            if self.target_client is TargetClient.CODEX
            else _CLAUDE_NATIVE_TARGETS
        )
        target = mappings.get(resource.resource_type)
        if target is None:
            return _skipped(resource, "unsupported-resource")
        target_resource, semantics, source_prefix = target
        relative_target = None
        if source_prefix is not None:
            prefix = f"{source_prefix}/"
            if not resource.source_locator.startswith(prefix):
                return _skipped(resource, "source-not-allowed")
            relative_target = resource.source_locator.removeprefix(prefix)
        return _projected(
            resource,
            target_resource=target_resource,
            copy_semantics=semantics,
            relative_target=relative_target,
            structured_value=resource.structured_value,
        )


class UserCopyProjectionRegistry:
    """Resolve only explicitly implemented User Copy projection pairs."""

    _SUPPORTED = frozenset(
        {
            (PluginPackageFormat.CODEX_NATIVE, TargetClient.CODEX),
            (PluginPackageFormat.CLAUDE_NATIVE, TargetClient.CLAUDE_CODE),
            (PluginPackageFormat.AGENT_PLUGIN_V1, TargetClient.CODEX),
        }
    )

    def resolve(
        self,
        package_format: PluginPackageFormat | str,
        target_client: TargetClient | str,
    ) -> UserCopyProjection:
        resolved_format = PluginPackageFormat(package_format)
        resolved_client = TargetClient(target_client)
        if (resolved_format, resolved_client) not in self._SUPPORTED:
            raise ValueError(
                f"projection-not-supported: "
                f"{resolved_format.value}/{resolved_client.value}"
            )
        return UserCopyProjection(resolved_format, resolved_client)


_CODEX_NATIVE_TARGETS = {
    UserCopyResourceType.INSTRUCTIONS: ("agents_md", "create-file", None),
    UserCopyResourceType.SKILL: ("skills", "create-directory", "skills"),
    UserCopyResourceType.SUBAGENT: ("subagents", "create-file", "agents"),
    UserCopyResourceType.PROMPT: ("prompts", "create-file", "prompts"),
    UserCopyResourceType.RULE: ("rules", "create-file", "rules"),
    UserCopyResourceType.MCP: ("mcp", "merge-config-entry", None),
    UserCopyResourceType.HOOK: ("hooks", "merge-config-entry", None),
}

_CLAUDE_NATIVE_TARGETS = {
    UserCopyResourceType.INSTRUCTIONS: ("claude_md", "create-file", None),
    UserCopyResourceType.SKILL: ("skills", "create-directory", "skills"),
    UserCopyResourceType.SUBAGENT: ("subagents", "create-file", "agents"),
    UserCopyResourceType.COMMAND: ("commands", "create-file", "commands"),
    UserCopyResourceType.OUTPUT_STYLE: (
        "output_styles",
        "create-file",
        "output-styles",
    ),
    UserCopyResourceType.MCP: ("mcp", "merge-config-entry", None),
    UserCopyResourceType.HOOK: ("hooks", "merge-config-entry", None),
}


def _projected(
    source: UserCopySourceResource,
    *,
    target_resource: str,
    copy_semantics: str,
    relative_target: str | None = None,
    structured_value: Any | None = None,
) -> UserCopyProjectionResult:
    return UserCopyProjectionResult(
        projected=ProjectedUserCopyResource(
            source=source,
            target_resource=target_resource,
            copy_semantics=copy_semantics,
            relative_target=relative_target,
            structured_value=structured_value,
        )
    )


def _skipped(
    source: UserCopySourceResource,
    code: str,
) -> UserCopyProjectionResult:
    return UserCopyProjectionResult(
        skipped=SkippedUserCopyResource(source=source, code=code)
    )


def _contains_string(value: Any, token: str) -> bool:
    if isinstance(value, str):
        return token in value
    if isinstance(value, Mapping):
        return any(_contains_string(child, token) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_string(child, token) for child in value)
    return False
