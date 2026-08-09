"""Claude Code Marketplace user-copy target adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapter import (
    CoreProfileResource,
    ResolvedUserCopyTarget,
    StructuredDocumentKind,
    StructuredEntryMode,
    UserCopyAdapterError,
    UserCopyOperation,
    UserCopyTargetKind,
    canonical_value_digest,
    decode_json_pointer,
    logical_child,
    normalized_config_identity,
    normalized_file_identity,
    resolve_below,
    safe_relative_target,
    validate_sha256_digest,
)
from .models import UserScopeAgent, UserScopeResource
from .paths import UserScopePathResolver, get_user_scope_path_resolver


@dataclass(frozen=True)
class ClaudeUserCopyAdapter:
    """Map canonical Claude profile resources to typed user targets."""

    paths: UserScopePathResolver
    provider: str = "claude-code"
    agent: UserScopeAgent = UserScopeAgent.CLAUDE_CODE
    placeholder_tokens: tuple[str, ...] = ("${CLAUDE_PLUGIN_ROOT}",)

    def resolve_target(
        self,
        resource: CoreProfileResource,
        *,
        source_value: Any | None,
        source_digest: str | None = None,
    ) -> ResolvedUserCopyTarget:
        if resource.resource_type == "instructions":
            return self._instructions(resource)
        if resource.resource_type == "skill":
            return self._directory(resource)
        file_resources = {
            "subagent": (
                "subagents",
                "agents",
                UserScopeResource.SUBAGENTS,
            ),
            "command": (
                "commands",
                "commands",
                UserScopeResource.COMMANDS,
            ),
            "output-style": (
                "output_styles",
                "output-styles",
                UserScopeResource.OUTPUT_STYLES,
            ),
        }
        if resource.resource_type in file_resources:
            expected_target, source_prefix, target_resource = file_resources[
                resource.resource_type
            ]
            return self._file(
                resource,
                expected_target=expected_target,
                source_prefix=source_prefix,
                target_resource=target_resource,
            )
        if resource.resource_type == "mcp":
            return self._mapping_entry(resource, source_value)
        if resource.resource_type == "hook":
            return self._hook_entry(
                resource,
                source_value,
                source_digest=source_digest,
            )
        raise UserCopyAdapterError(
            "unsupported-resource",
            resource.resource_type,
        )

    def _instructions(
        self,
        resource: CoreProfileResource,
    ) -> ResolvedUserCopyTarget:
        if (
            resource.source_locator != "CLAUDE.md"
            or resource.resource_id != "root-instructions"
            or resource.source_kind != "copy-convention"
            or resource.target_resource != "claude_md"
            or resource.copy_semantics != "create-file"
            or resource.relative_target is not None
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        location = self.paths.resolve(
            self.agent,
            UserScopeResource.INSTRUCTIONS,
        )
        return ResolvedUserCopyTarget(
            agent=self.agent,
            target_kind=UserCopyTargetKind.FILE,
            operation=UserCopyOperation.CREATE,
            runtime_path=location.runtime_path,
            logical_locator=location.logical_locator,
            normalized_identity=normalized_file_identity(location.logical_locator),
        )

    def _directory(
        self,
        resource: CoreProfileResource,
    ) -> ResolvedUserCopyTarget:
        if (
            resource.target_resource != "skills"
            or resource.copy_semantics != "create-directory"
            or resource.source_kind not in {"copy-convention", "plugin-component"}
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        relative = safe_relative_target(resource.relative_target)
        if len(relative.parts) != 1 or resource.resource_id != relative.name:
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        if resource.source_kind == "copy-convention":
            if resource.source_locator != f"skills/{relative.as_posix()}":
                raise UserCopyAdapterError(
                    "source-not-allowed",
                    resource.source_locator,
                )
        else:
            source = safe_relative_target(resource.source_locator)
            if source.name != resource.resource_id:
                raise UserCopyAdapterError(
                    "source-not-allowed",
                    resource.source_locator,
                )
        root = self.paths.resolve(self.agent, UserScopeResource.SKILLS)
        logical_locator = logical_child(root.logical_locator, relative)
        return ResolvedUserCopyTarget(
            agent=self.agent,
            target_kind=UserCopyTargetKind.DIRECTORY,
            operation=UserCopyOperation.CREATE,
            runtime_path=resolve_below(root.runtime_path, relative),
            logical_locator=logical_locator,
            normalized_identity=normalized_file_identity(logical_locator),
        )

    def _file(
        self,
        resource: CoreProfileResource,
        *,
        expected_target: str,
        source_prefix: str,
        target_resource: UserScopeResource,
    ) -> ResolvedUserCopyTarget:
        if (
            resource.target_resource != expected_target
            or resource.source_kind != "copy-convention"
            or resource.copy_semantics != "create-file"
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        relative = safe_relative_target(
            resource.relative_target,
            expected_suffix=".md",
        )
        if (
            resource.source_locator != f"{source_prefix}/{relative.as_posix()}"
            or resource.resource_id != relative.as_posix().removesuffix(".md")
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        root = self.paths.resolve(self.agent, target_resource)
        logical_locator = logical_child(root.logical_locator, relative)
        return ResolvedUserCopyTarget(
            agent=self.agent,
            target_kind=UserCopyTargetKind.FILE,
            operation=UserCopyOperation.CREATE,
            runtime_path=resolve_below(root.runtime_path, relative),
            logical_locator=logical_locator,
            normalized_identity=normalized_file_identity(logical_locator),
        )

    def _mapping_entry(
        self,
        resource: CoreProfileResource,
        source_value: Any | None,
    ) -> ResolvedUserCopyTarget:
        if (
            resource.target_resource != "mcp"
            or resource.source_kind != "plugin-component"
            or resource.copy_semantics != "merge-config-entry"
            or not resource.resource_id
            or not isinstance(source_value, dict)
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        pointer = decode_json_pointer(resource.json_pointer)
        if (
            len(pointer) not in {1, 2}
            or (len(pointer) == 2 and pointer[0] not in {"mcpServers", "mcp_servers"})
            or pointer[-1] != resource.resource_id
        ):
            raise UserCopyAdapterError(
                "source-reference-invalid",
                resource.json_pointer or "",
            )
        parent = ("mcpServers",)
        location = self.paths.resolve(self.agent, UserScopeResource.MCP)
        return ResolvedUserCopyTarget(
            agent=self.agent,
            target_kind=UserCopyTargetKind.CONFIG_ENTRY,
            operation=UserCopyOperation.MERGE,
            runtime_path=location.runtime_path,
            logical_locator=(
                f"{location.logical_locator}#"
                f"{'/'.join((*parent, resource.resource_id))}"
            ),
            normalized_identity=normalized_config_identity(
                location.logical_locator,
                parent,
                resource.resource_id,
            ),
            structured_document=StructuredDocumentKind.JSON,
            structured_entry_mode=StructuredEntryMode.MAPPING_ENTRY,
            structured_parent=parent,
            structured_entry_id=resource.resource_id,
        )

    def _hook_entry(
        self,
        resource: CoreProfileResource,
        source_value: Any | None,
        *,
        source_digest: str | None,
    ) -> ResolvedUserCopyTarget:
        if (
            resource.target_resource != "hooks"
            or resource.source_kind != "plugin-component"
            or resource.copy_semantics != "merge-config-entry"
            or source_value is None
            or resource.resource_id
            != f"{resource.source_locator}#{resource.json_pointer or '/'}"
        ):
            raise UserCopyAdapterError(
                "source-not-allowed",
                resource.source_locator,
            )
        pointer = decode_json_pointer(resource.json_pointer)
        if (
            len(pointer) not in {2, 3}
            or (len(pointer) == 3 and pointer[0] != "hooks")
            or not pointer[-1].isdigit()
        ):
            raise UserCopyAdapterError(
                "source-reference-invalid",
                resource.json_pointer or "",
            )
        offset = 1 if len(pointer) == 3 else 0
        event_name = pointer[offset]
        if not event_name:
            raise UserCopyAdapterError(
                "source-reference-invalid",
                resource.json_pointer or "",
            )
        digest = (
            validate_sha256_digest(source_digest)
            if source_digest is not None
            else canonical_value_digest(source_value)
        )
        entry_id = f"{event_name}:{digest}"
        location = self.paths.resolve(self.agent, UserScopeResource.HOOKS)
        parent = ("hooks", event_name)
        return ResolvedUserCopyTarget(
            agent=self.agent,
            target_kind=UserCopyTargetKind.CONFIG_ENTRY,
            operation=UserCopyOperation.MERGE,
            runtime_path=location.runtime_path,
            logical_locator=f"{location.logical_locator}#hooks/{entry_id}",
            normalized_identity=normalized_config_identity(
                location.logical_locator,
                parent,
                digest,
            ),
            structured_document=StructuredDocumentKind.JSON,
            structured_entry_mode=StructuredEntryMode.LIST_ENTRY,
            structured_parent=parent,
            structured_entry_id=digest,
        )


def get_claude_user_copy_adapter(
    paths: UserScopePathResolver | None = None,
) -> ClaudeUserCopyAdapter:
    """Return the canonical Claude Code user-copy target adapter."""

    return ClaudeUserCopyAdapter(paths=paths or get_user_scope_path_resolver())
