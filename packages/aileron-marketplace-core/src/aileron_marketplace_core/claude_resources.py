from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .provider_resources import provider_resource_name_contract
from .resource_resolution import (
    PackageSourceError,
    PluginResourceOwner,
    ResourceResolutionDiagnostic,
    hook_owners_from_document,
    json_pointer_escape,
    manifest_reference_values,
    mcp_owners_from_document,
    package_relative_locator,
    read_package_json_object,
    resolve_package_source,
    validate_inline_hooks,
    validate_inline_mcp_servers,
)

ClaudePluginResourceOwner = PluginResourceOwner
ClaudePluginFileResourceType = Literal[
    "skill",
    "command",
    "agent",
    "output-style",
]


@dataclass(frozen=True)
class ClaudePluginFileResource:
    resource_type: ClaudePluginFileResourceType
    resource_id: str
    source_locator: str
    resource_root_locator: str


@dataclass(frozen=True)
class ClaudePluginResources:
    file_resources: tuple[ClaudePluginFileResource, ...] = ()
    mcp_servers: dict[str, ClaudePluginResourceOwner] = field(default_factory=dict)
    hooks: ClaudePluginResourceOwner | None = None
    hook_sources: tuple[ClaudePluginResourceOwner, ...] = ()
    hook_entries: tuple[ClaudePluginResourceOwner, ...] = ()
    lsp_servers: dict[str, ClaudePluginResourceOwner] = field(default_factory=dict)
    diagnostics: tuple[ResourceResolutionDiagnostic, ...] = ()


def _manifest_path(package_root: Path) -> Path:
    contract = provider_resource_name_contract("claude-code")
    return package_root / contract.plugin_manifest_path


def _diagnostic(error: PackageSourceError) -> ResourceResolutionDiagnostic:
    return ResourceResolutionDiagnostic(
        code=error.code,
        source_locator=error.source_locator,
    )


def _read_manifest(
    package_root: Path,
    path: Path,
) -> tuple[dict[str, Any], list[ResourceResolutionDiagnostic]]:
    if not path.exists():
        return {}, []
    try:
        return read_package_json_object(package_root, path), []
    except PackageSourceError as exc:
        return {}, [
            ResourceResolutionDiagnostic(
                code=exc.code,
                source_locator=exc.source_locator,
            )
        ]


def _merge_mcp_owners(
    target: dict[str, ClaudePluginResourceOwner],
    owners: dict[str, PluginResourceOwner],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> None:
    for name, owner in sorted(owners.items()):
        if name in target:
            diagnostics.append(
                ResourceResolutionDiagnostic(
                    code="duplicate-resource-id",
                    source_locator=owner.file_path,
                )
            )
            continue
        target[name] = owner


def _safe_package_file(
    package_root: Path,
    path: Path,
    *,
    expected_suffix: str,
) -> Path:
    locator = package_relative_locator(package_root, path)
    return resolve_package_source(
        package_root,
        locator,
        expected_suffixes=(expected_suffix,),
    )


def _files_under_directory(
    package_root: Path,
    directory: Path,
    *,
    expected_suffix: str,
) -> tuple[Path, ...]:
    files: list[Path] = []
    for candidate in sorted(directory.rglob(f"*{expected_suffix}")):
        try:
            files.append(
                _safe_package_file(
                    package_root,
                    candidate,
                    expected_suffix=expected_suffix,
                )
            )
        except PackageSourceError:
            raise
    return tuple(files)


def _component_source_paths(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    field_name: str,
    default_path: str,
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[Path, ...]:
    manifest_locator = package_relative_locator(package_root, manifest_path)
    raw_value = manifest.get(field_name)
    if raw_value is None:
        candidate = package_root / default_path
        return (candidate,) if candidate.exists() else ()
    try:
        references = manifest_reference_values(
            raw_value,
            source_locator=f"{manifest_locator}#/{field_name}",
        )
    except PackageSourceError as exc:
        diagnostics.append(_diagnostic(exc))
        return ()
    paths: list[Path] = []
    for reference in references:
        try:
            locator = reference[:-1] if reference.endswith("/") else reference
            paths.append(
                resolve_package_source(
                    package_root,
                    locator,
                    require_file=False,
                )
                if (package_root / locator).is_dir()
                else resolve_package_source(package_root, locator)
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return tuple(paths)


def _file_component(
    package_root: Path,
    *,
    resource_type: ClaudePluginFileResourceType,
    source_path: Path,
    root_path: Path,
) -> ClaudePluginFileResource:
    source_locator = package_relative_locator(package_root, source_path)
    root_locator = package_relative_locator(package_root, root_path)
    if resource_type == "skill":
        resource_id = root_locator
    else:
        resource_id = source_locator
    return ClaudePluginFileResource(
        resource_type=resource_type,
        resource_id=resource_id,
        source_locator=source_locator,
        resource_root_locator=root_locator,
    )


def _merge_file_components(
    target: dict[tuple[str, str], ClaudePluginFileResource],
    resources: tuple[ClaudePluginFileResource, ...],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> None:
    for resource in resources:
        key = (resource.resource_type, resource.resource_id)
        if key in target:
            if target[key] == resource:
                continue
            diagnostics.append(
                ResourceResolutionDiagnostic(
                    code="duplicate-resource-id",
                    source_locator=resource.source_locator,
                )
            )
            continue
        target[key] = resource


def _markdown_file_components(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    field_name: str,
    default_path: str,
    resource_type: Literal["command", "agent", "output-style"],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[ClaudePluginFileResource, ...]:
    resources: list[ClaudePluginFileResource] = []
    for source in _component_source_paths(
        package_root,
        manifest_path,
        manifest,
        field_name,
        default_path,
        diagnostics,
    ):
        try:
            files = (
                _files_under_directory(
                    package_root,
                    source,
                    expected_suffix=".md",
                )
                if source.is_dir()
                else (
                    _safe_package_file(
                        package_root,
                        source,
                        expected_suffix=".md",
                    ),
                )
            )
            resources.extend(
                _file_component(
                    package_root,
                    resource_type=resource_type,
                    source_path=path,
                    root_path=path,
                )
                for path in files
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return tuple(resources)


def _skill_file_components(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[ClaudePluginFileResource, ...]:
    sources = list(
        _component_source_paths(
            package_root,
            manifest_path,
            manifest,
            "skills",
            "skills",
            diagnostics,
        )
    )
    resources: list[ClaudePluginFileResource] = []
    for source in sources:
        try:
            skill_files: tuple[Path, ...]
            if source.is_file():
                skill_files = (
                    _safe_package_file(
                        package_root,
                        source,
                        expected_suffix=".md",
                    ),
                )
            elif (source / "SKILL.md").is_file():
                skill_files = (
                    _safe_package_file(
                        package_root,
                        source / "SKILL.md",
                        expected_suffix=".md",
                    ),
                )
            else:
                skill_files = tuple(
                    path
                    for path in _files_under_directory(
                        package_root,
                        source,
                        expected_suffix=".md",
                    )
                    if path.name == "SKILL.md"
                )
            resources.extend(
                _file_component(
                    package_root,
                    resource_type="skill",
                    source_path=path,
                    root_path=path.parent,
                )
                for path in skill_files
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return tuple(resources)


def _resolve_file_resources(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[ClaudePluginFileResource, ...]:
    resources: dict[tuple[str, str], ClaudePluginFileResource] = {}
    for resolved in (
        _skill_file_components(
            package_root,
            manifest_path,
            manifest,
            diagnostics,
        ),
        _markdown_file_components(
            package_root,
            manifest_path,
            manifest,
            field_name="commands",
            default_path="commands",
            resource_type="command",
            diagnostics=diagnostics,
        ),
        _markdown_file_components(
            package_root,
            manifest_path,
            manifest,
            field_name="agents",
            default_path="agents",
            resource_type="agent",
            diagnostics=diagnostics,
        ),
        _markdown_file_components(
            package_root,
            manifest_path,
            manifest,
            field_name="outputStyles",
            default_path="output-styles",
            resource_type="output-style",
            diagnostics=diagnostics,
        ),
    ):
        _merge_file_components(resources, resolved, diagnostics)
    return tuple(
        sorted(
            resources.values(),
            key=lambda item: (
                item.resource_type,
                item.resource_id,
                item.source_locator,
            ),
        )
    )


def _resolve_mcp_resources(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> dict[str, ClaudePluginResourceOwner]:
    owners: dict[str, ClaudePluginResourceOwner] = {}
    manifest_locator = package_relative_locator(package_root, manifest_path)
    if "mcpServers" in manifest and "mcp_servers" in manifest:
        diagnostics.append(
            ResourceResolutionDiagnostic(
                code="source-document-invalid",
                source_locator=manifest_locator,
            )
        )
        return owners
    raw_value = manifest.get("mcpServers")
    key = "mcpServers"
    if raw_value is None:
        raw_value = manifest.get("mcp_servers")
        key = "mcp_servers"
    if isinstance(raw_value, dict):
        try:
            validate_inline_mcp_servers(
                raw_value,
                source_locator=f"{manifest_locator}#/{key}",
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
            return owners
        _merge_mcp_owners(
            owners,
            {
                str(name): ClaudePluginResourceOwner(
                    file_path=manifest_locator,
                    json_pointer=f"/{key}/{json_pointer_escape(str(name))}",
                    standalone_file=False,
                )
                for name in sorted(raw_value)
            },
            diagnostics,
        )
        return owners

    try:
        references = manifest_reference_values(
            raw_value,
            source_locator=f"{manifest_locator}#/{key}",
        )
    except PackageSourceError as exc:
        diagnostics.append(_diagnostic(exc))
        return owners
    if raw_value is None and (package_root / ".mcp.json").exists():
        references = (".mcp.json",)
    for reference in references:
        try:
            source = resolve_package_source(
                package_root,
                reference,
                expected_suffixes=(".json",),
            )
            _merge_mcp_owners(
                owners,
                mcp_owners_from_document(package_root, source),
                diagnostics,
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return owners


def _resolve_lsp_resources(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> dict[str, ClaudePluginResourceOwner]:
    owners: dict[str, ClaudePluginResourceOwner] = {}
    manifest_locator = package_relative_locator(package_root, manifest_path)
    raw_value = manifest.get("lspServers")
    if isinstance(raw_value, dict):
        try:
            validate_inline_mcp_servers(
                raw_value,
                source_locator=f"{manifest_locator}#/lspServers",
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
            return owners
        _merge_mcp_owners(
            owners,
            {
                str(name): ClaudePluginResourceOwner(
                    file_path=manifest_locator,
                    json_pointer=(f"/lspServers/{json_pointer_escape(str(name))}"),
                    standalone_file=False,
                )
                for name in sorted(raw_value)
            },
            diagnostics,
        )
        return owners

    try:
        references = manifest_reference_values(
            raw_value,
            source_locator=f"{manifest_locator}#/lspServers",
        )
    except PackageSourceError as exc:
        diagnostics.append(_diagnostic(exc))
        return owners
    if raw_value is None and (package_root / ".lsp.json").exists():
        references = (".lsp.json",)
    for reference in references:
        try:
            source = resolve_package_source(
                package_root,
                reference,
                expected_suffixes=(".json",),
            )
            _merge_mcp_owners(
                owners,
                mcp_owners_from_document(package_root, source),
                diagnostics,
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return owners


def _inline_hook_entries(
    package_root: Path,
    manifest_path: Path,
    hooks: dict[str, Any],
) -> tuple[ClaudePluginResourceOwner, ...]:
    locator = package_relative_locator(package_root, manifest_path)
    entries: list[ClaudePluginResourceOwner] = []
    for event_name in sorted(hooks):
        event_entries = hooks[event_name]
        for index in range(len(event_entries)):
            entries.append(
                ClaudePluginResourceOwner(
                    file_path=locator,
                    json_pointer=(
                        f"/hooks/{json_pointer_escape(str(event_name))}/{index}"
                    ),
                    standalone_file=False,
                )
            )
    return tuple(entries)


def _resolve_hook_resources(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[
    ClaudePluginResourceOwner | None,
    tuple[ClaudePluginResourceOwner, ...],
    tuple[ClaudePluginResourceOwner, ...],
]:
    raw_hooks = manifest.get("hooks")
    manifest_locator = package_relative_locator(package_root, manifest_path)
    if isinstance(raw_hooks, dict):
        locator = package_relative_locator(package_root, manifest_path)
        owner = ClaudePluginResourceOwner(
            file_path=locator,
            json_pointer="/hooks",
            standalone_file=False,
        )
        try:
            validate_inline_hooks(
                raw_hooks,
                source_locator=f"{manifest_locator}#/hooks",
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
            return owner, (owner,), ()
        return (
            owner,
            (owner,),
            _inline_hook_entries(package_root, manifest_path, raw_hooks),
        )

    try:
        references = manifest_reference_values(
            raw_hooks,
            source_locator=f"{manifest_locator}#/hooks",
        )
    except PackageSourceError as exc:
        diagnostics.append(_diagnostic(exc))
        return None, (), ()
    if raw_hooks is None:
        for default in ("hooks/hooks.json", "hooks.json"):
            if (package_root / default).exists():
                references = (default,)
                break
    documents: list[ClaudePluginResourceOwner] = []
    entries: list[ClaudePluginResourceOwner] = []
    for reference in references:
        try:
            source = resolve_package_source(
                package_root,
                reference,
                expected_suffixes=(".json",),
            )
            owner = ClaudePluginResourceOwner(
                file_path=package_relative_locator(package_root, source),
                json_pointer="",
                standalone_file=True,
            )
            if owner in documents:
                diagnostics.append(
                    ResourceResolutionDiagnostic(
                        code="duplicate-resource-id",
                        source_locator=owner.file_path,
                    )
                )
                continue
            documents.append(owner)
            data = read_package_json_object(package_root, source)
            pointer = "/hooks" if isinstance(data.get("hooks"), dict) else ""
            resolved_entries = hook_owners_from_document(package_root, source)
            documents[-1] = ClaudePluginResourceOwner(
                file_path=owner.file_path,
                json_pointer=pointer,
                standalone_file=True,
            )
            entries.extend(resolved_entries)
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return (documents[0] if documents else None, tuple(documents), tuple(entries))


def resolve_claude_plugin_resources(package_root: Path) -> ClaudePluginResources:
    manifest_path = _manifest_path(package_root)
    manifest, diagnostics = _read_manifest(package_root, manifest_path)
    if diagnostics:
        return ClaudePluginResources(diagnostics=tuple(diagnostics))
    file_resources = _resolve_file_resources(
        package_root,
        manifest_path,
        manifest,
        diagnostics,
    )
    mcp_servers = _resolve_mcp_resources(
        package_root,
        manifest_path,
        manifest,
        diagnostics,
    )
    hooks, hook_sources, hook_entries = _resolve_hook_resources(
        package_root,
        manifest_path,
        manifest,
        diagnostics,
    )
    lsp_servers = _resolve_lsp_resources(
        package_root,
        manifest_path,
        manifest,
        diagnostics,
    )
    return ClaudePluginResources(
        file_resources=file_resources,
        mcp_servers=mcp_servers,
        hooks=hooks,
        hook_sources=hook_sources,
        hook_entries=hook_entries,
        lsp_servers=lsp_servers,
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (item.code, item.source_locator),
            )
        ),
    )
