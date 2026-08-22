from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .package_format_resources import package_format_resource_name_contract
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

CodexPluginResourceOwner = PluginResourceOwner
CodexPluginFileResourceType = Literal["skill", "app"]


@dataclass(frozen=True)
class CodexPluginFileResource:
    """One file-backed resource resolved relative to an installed plugin root."""

    resource_type: CodexPluginFileResourceType
    resource_id: str
    source_locator: str
    resource_root_locator: str


@dataclass(frozen=True)
class CodexPluginResources:
    file_resources: tuple[CodexPluginFileResource, ...] = ()
    mcp_servers: dict[str, CodexPluginResourceOwner] = field(default_factory=dict)
    hooks: CodexPluginResourceOwner | None = None
    hook_sources: tuple[CodexPluginResourceOwner, ...] = ()
    hook_entries: tuple[CodexPluginResourceOwner, ...] = ()
    default_prompts: tuple[str, ...] = ()
    diagnostics: tuple[ResourceResolutionDiagnostic, ...] = ()


def _manifest_path(package_root: Path) -> Path:
    contract = package_format_resource_name_contract("codex-native")
    return package_root / contract.plugin_manifest_path


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


def _diagnostic(error: PackageSourceError) -> ResourceResolutionDiagnostic:
    return ResourceResolutionDiagnostic(
        code=error.code,
        source_locator=error.source_locator,
    )


def _merge_mcp_owners(
    target: dict[str, CodexPluginResourceOwner],
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
    expected_names: tuple[str, ...] = (),
    expected_suffixes: tuple[str, ...] = (),
) -> Path:
    locator = package_relative_locator(package_root, path)
    source = resolve_package_source(
        package_root,
        locator,
        expected_suffixes=expected_suffixes,
    )
    if expected_names and source.name not in expected_names:
        raise PackageSourceError("source-not-allowed", locator)
    return source


def _component_references(
    manifest: dict[str, Any],
    *,
    manifest_locator: str,
    field_name: str,
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[str, ...]:
    try:
        return manifest_reference_values(
            manifest.get(field_name),
            source_locator=f"{manifest_locator}#/{field_name}",
        )
    except PackageSourceError as exc:
        diagnostics.append(_diagnostic(exc))
        return ()


def _resolve_skill_resources(
    package_root: Path,
    manifest: dict[str, Any],
    manifest_locator: str,
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[CodexPluginFileResource, ...]:
    raw_value = manifest.get("skills")
    references = _component_references(
        manifest,
        manifest_locator=manifest_locator,
        field_name="skills",
        diagnostics=diagnostics,
    )
    sources: list[Path] = []
    if raw_value is None:
        default = package_root / "skills"
        if default.is_dir():
            sources.append(default)
    for reference in references:
        try:
            sources.append(
                resolve_package_source(
                    package_root,
                    reference,
                    require_file=False,
                )
                if (package_root / reference).is_dir()
                else resolve_package_source(
                    package_root,
                    reference,
                    expected_suffixes=(".md",),
                )
            )
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))

    resources: dict[str, CodexPluginFileResource] = {}
    for source in sources:
        candidates = (
            (source,)
            if source.is_file()
            else tuple(sorted(source.rglob("SKILL.md")))
        )
        for candidate in candidates:
            try:
                skill_file = _safe_package_file(
                    package_root,
                    candidate,
                    expected_names=("SKILL.md",),
                )
                skill_root = skill_file.parent
                root_locator = package_relative_locator(package_root, skill_root)
                resource = CodexPluginFileResource(
                    resource_type="skill",
                    resource_id=root_locator,
                    source_locator=package_relative_locator(
                        package_root,
                        skill_file,
                    ),
                    resource_root_locator=root_locator,
                )
                if resource.resource_id in resources:
                    diagnostics.append(
                        ResourceResolutionDiagnostic(
                            code="duplicate-resource-id",
                            source_locator=resource.source_locator,
                        )
                    )
                    continue
                resources[resource.resource_id] = resource
            except PackageSourceError as exc:
                diagnostics.append(_diagnostic(exc))
    return tuple(resources[key] for key in sorted(resources))


def _resolve_app_resources(
    package_root: Path,
    manifest: dict[str, Any],
    manifest_locator: str,
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[CodexPluginFileResource, ...]:
    declared_fields = [
        field_name
        for field_name in ("apps", "connectors")
        if manifest.get(field_name) not in (None, "", [])
    ]
    if len(declared_fields) > 1:
        diagnostics.append(
            ResourceResolutionDiagnostic(
                code="source-document-invalid",
                source_locator=manifest_locator,
            )
        )
        return ()
    if not declared_fields:
        return ()

    field_name = declared_fields[0]
    references = _component_references(
        manifest,
        manifest_locator=manifest_locator,
        field_name=field_name,
        diagnostics=diagnostics,
    )
    resources: dict[str, CodexPluginFileResource] = {}
    for reference in references:
        try:
            source = resolve_package_source(package_root, reference)
            read_package_json_object(package_root, source)
            locator = package_relative_locator(package_root, source)
            resource_id = source.stem if source.suffix else source.name
            resource = CodexPluginFileResource(
                resource_type="app",
                resource_id=resource_id,
                source_locator=locator,
                resource_root_locator=locator,
            )
            if resource_id in resources:
                diagnostics.append(
                    ResourceResolutionDiagnostic(
                        code="duplicate-resource-id",
                        source_locator=locator,
                    )
                )
                continue
            resources[resource_id] = resource
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return tuple(resources[key] for key in sorted(resources))


def _default_prompts(
    manifest: dict[str, Any],
    manifest_locator: str,
    diagnostics: list[ResourceResolutionDiagnostic],
) -> tuple[str, ...]:
    interface = manifest.get("interface")
    if interface is None:
        return ()
    if not isinstance(interface, dict):
        diagnostics.append(
            ResourceResolutionDiagnostic(
                code="source-document-invalid",
                source_locator=f"{manifest_locator}#/interface",
            )
        )
        return ()
    value = interface.get("defaultPrompt")
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    diagnostics.append(
        ResourceResolutionDiagnostic(
            code="source-document-invalid",
            source_locator=f"{manifest_locator}#/interface/defaultPrompt",
        )
    )
    return ()


def _inline_mcp_owners(
    manifest_path: Path,
    key: str,
    servers: dict[str, Any],
) -> dict[str, CodexPluginResourceOwner]:
    manifest_locator = package_relative_locator(
        manifest_path.parent.parent, manifest_path
    )
    return {
        str(name): CodexPluginResourceOwner(
            file_path=manifest_locator,
            json_pointer=f"/{key}/{json_pointer_escape(str(name))}",
            standalone_file=False,
        )
        for name in sorted(servers)
    }


def _resolve_mcp_resources(
    package_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    diagnostics: list[ResourceResolutionDiagnostic],
) -> dict[str, CodexPluginResourceOwner]:
    owners: dict[str, CodexPluginResourceOwner] = {}
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
            _inline_mcp_owners(manifest_path, key, raw_value),
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
    if raw_value is None:
        default_path = package_root / ".mcp.json"
        if not default_path.exists():
            return owners
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


def _inline_hook_entries(
    manifest_path: Path,
    hooks: dict[str, Any],
) -> tuple[CodexPluginResourceOwner, ...]:
    locator = package_relative_locator(manifest_path.parent.parent, manifest_path)
    entries: list[CodexPluginResourceOwner] = []
    for event_name in sorted(hooks):
        event_entries = hooks[event_name]
        for index in range(len(event_entries)):
            entries.append(
                CodexPluginResourceOwner(
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
    CodexPluginResourceOwner | None,
    tuple[CodexPluginResourceOwner, ...],
    tuple[CodexPluginResourceOwner, ...],
]:
    raw_hooks = manifest.get("hooks")
    manifest_locator = package_relative_locator(package_root, manifest_path)
    if isinstance(raw_hooks, dict):
        locator = package_relative_locator(package_root, manifest_path)
        owner = CodexPluginResourceOwner(
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
            _inline_hook_entries(manifest_path, raw_hooks),
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
    documents: list[CodexPluginResourceOwner] = []
    entries: list[CodexPluginResourceOwner] = []
    for reference in references:
        try:
            source = resolve_package_source(
                package_root,
                reference,
                expected_suffixes=(".json",),
            )
            owner = CodexPluginResourceOwner(
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
            documents[-1] = CodexPluginResourceOwner(
                file_path=owner.file_path,
                json_pointer=pointer,
                standalone_file=True,
            )
            entries.extend(resolved_entries)
        except PackageSourceError as exc:
            diagnostics.append(_diagnostic(exc))
    return (documents[0] if documents else None, tuple(documents), tuple(entries))


def resolve_codex_plugin_resources(package_root: Path) -> CodexPluginResources:
    manifest_path = _manifest_path(package_root)
    manifest, diagnostics = _read_manifest(package_root, manifest_path)
    if diagnostics:
        return CodexPluginResources(diagnostics=tuple(diagnostics))
    manifest_locator = package_relative_locator(package_root, manifest_path)
    file_resources = (
        *_resolve_skill_resources(
            package_root,
            manifest,
            manifest_locator,
            diagnostics,
        ),
        *_resolve_app_resources(
            package_root,
            manifest,
            manifest_locator,
            diagnostics,
        ),
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
    return CodexPluginResources(
        file_resources=tuple(
            sorted(
                file_resources,
                key=lambda item: (
                    item.resource_type,
                    item.resource_id,
                    item.source_locator,
                ),
            )
        ),
        mcp_servers=mcp_servers,
        hooks=hooks,
        hook_sources=hook_sources,
        hook_entries=hook_entries,
        default_prompts=_default_prompts(
            manifest,
            manifest_locator,
            diagnostics,
        ),
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (item.code, item.source_locator),
            )
        ),
    )
