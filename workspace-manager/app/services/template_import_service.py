"""Multi-source template import and canonical normalization service."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import tomllib
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.template_canonical import (
    CanonicalFrontmatterDocument,
    CanonicalHook,
    CanonicalMcpServer,
    CanonicalOutputStyle,
    CanonicalSkill,
    CanonicalTarget,
    ImportedTemplate,
    ImportedTemplateAsset,
    ImportedTemplateMetadata,
    ImportSourceType,
)
from app.services.template_base_service import TemplateBaseService


class TemplateImportError(ValueError):
    """Template import error."""


class BaseTemplateImportAdapter(ABC):
    source_type: ImportSourceType

    def find_root(self, extract_dir: Path) -> Optional[Path]:
        for candidate in _candidate_roots(extract_dir):
            if self.matches(candidate):
                return candidate
        return None

    @abstractmethod
    def matches(self, root: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, root: Path) -> ImportedTemplate:
        raise NotImplementedError


class ClaudeImportAdapter(BaseTemplateImportAdapter):
    source_type = ImportSourceType.CLAUDE

    def matches(self, root: Path) -> bool:
        return (root / ".claude-plugin" / "manifest.json").exists()

    def load(self, root: Path) -> ImportedTemplate:
        manifest_path = root / ".claude-plugin" / "manifest.json"
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TemplateImportError("invalid_template_package_manifest_json") from exc

        template_id = str(manifest_data.get("id") or "").strip()
        if not template_id:
            raise TemplateImportError("missing_template_package_manifest_id")
        if not _is_valid_template_id(template_id):
            raise TemplateImportError("invalid_template_id")

        metadata = ImportedTemplateMetadata(
            id=template_id,
            name=manifest_data.get("name") or template_id,
            description=manifest_data.get("description"),
            version=str(manifest_data.get("version") or "1.0.0"),
            sourceType=self.source_type,
            authorName=(manifest_data.get("author") or {}).get("name") or "Unknown",
            authorEmail=(manifest_data.get("author") or {}).get("email"),
            authorUrl=(manifest_data.get("author") or {}).get("url"),
            status=manifest_data.get("status"),
            keywords=list(manifest_data.get("keywords") or []),
            initCommands=manifest_data.get("init_commands"),
        )

        mcp_servers = _parse_claude_mcp(root / "mcp.json")
        hooks, hook_assets = _parse_claude_hooks(root / "hooks" / "hooks.json", root)

        return ImportedTemplate(
            rootPath=str(root),
            metadata=metadata,
            agentsMdContent=_read_text_if_exists(root / "CLAUDE.md"),
            commands=_load_markdown_documents(root / "commands", root),
            agents=_load_markdown_documents(root / "agents", root),
            skills=_load_skills(root / "skills", root),
            hooks=hooks,
            mcpServers=mcp_servers,
            outputStyle=_load_legacy_output_style(root / "output-styles", root),
            resources=hook_assets + _collect_extra_resources(
                root,
                excluded={
                    ".claude-plugin/manifest.json",
                    ".claude-plugin/marketplace.json",
                    "CLAUDE.md",
                    "mcp.json",
                    "hooks/hooks.json",
                },
                excluded_prefixes=("commands/", "agents/", "skills/", "hooks/", "output-styles/"),
            ),
        )


class CodexImportAdapter(BaseTemplateImportAdapter):
    source_type = ImportSourceType.CODEX

    def matches(self, root: Path) -> bool:
        return (root / "AGENTS.md").exists() or (root / ".codex").exists()

    def load(self, root: Path) -> ImportedTemplate:
        template_id = _coerce_template_id(root.name)
        warnings: List[str] = []
        unresolved: List[str] = []
        mcp_servers: List[CanonicalMcpServer] = []
        hooks: List[CanonicalHook] = []

        config_path = root / ".codex" / "config.toml"
        if config_path.exists():
            config_payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
            mcp_servers.extend(_parse_codex_mcp(config_payload, config_path, root))
            if config_payload.get("hooks"):
                unresolved.append("codex_hooks_config_requires_manual_review")
                warnings.append("codex_hooks_config_detected")

        hooks_path = root / ".codex" / "hooks.json"
        if hooks_path.exists():
            parsed_hooks, _ = _parse_hooks_json_file(hooks_path, root)
            hooks.extend(parsed_hooks)

        return ImportedTemplate(
            rootPath=str(root),
            metadata=ImportedTemplateMetadata(
                id=template_id,
                name=template_id,
                sourceType=self.source_type,
            ),
            agentsMdContent=_read_text_if_exists(root / "AGENTS.md"),
            commands=_load_markdown_documents(root / ".codex" / "commands", root),
            agents=_load_markdown_documents(root / ".codex" / "agents", root),
            skills=_load_skills(root / ".codex" / "skills", root),
            hooks=hooks,
            mcpServers=mcp_servers,
            warnings=warnings,
            unresolvedItems=unresolved,
            resources=_collect_extra_resources(
                root,
                excluded={"AGENTS.md", ".codex/config.toml", ".codex/hooks.json"},
                excluded_prefixes=(".codex/commands/", ".codex/agents/", ".codex/skills/"),
            ),
        )


class GeminiImportAdapter(BaseTemplateImportAdapter):
    source_type = ImportSourceType.GEMINI

    def matches(self, root: Path) -> bool:
        return (root / "GEMINI.md").exists() or (root / ".gemini").exists()

    def load(self, root: Path) -> ImportedTemplate:
        template_id = _coerce_template_id(root.name)
        warnings: List[str] = []

        settings_path = root / ".gemini" / "settings.json"
        mcp_servers: List[CanonicalMcpServer] = []
        hooks: List[CanonicalHook] = []
        if settings_path.exists():
            settings_payload = json.loads(settings_path.read_text(encoding="utf-8"))
            mcp_servers.extend(_parse_gemini_mcp(settings_payload, settings_path, root))
            hooks.extend(_parse_gemini_hooks(settings_payload, settings_path, root))
            if settings_payload.get("output"):
                warnings.append("gemini_output_settings_mapped_to_output_style")

        commands = _load_gemini_command_documents(root / ".gemini" / "commands", root)

        return ImportedTemplate(
            rootPath=str(root),
            metadata=ImportedTemplateMetadata(
                id=template_id,
                name=template_id,
                sourceType=self.source_type,
            ),
            agentsMdContent=_read_text_if_exists(root / "GEMINI.md") or _read_text_if_exists(root / "AGENTS.md"),
            commands=commands,
            agents=_load_markdown_documents(root / ".gemini" / "agents", root),
            skills=_load_skills(root / ".gemini" / "skills", root),
            hooks=hooks,
            mcpServers=mcp_servers,
            warnings=warnings,
            resources=_collect_extra_resources(
                root,
                excluded={"GEMINI.md", "AGENTS.md", ".gemini/settings.json"},
                excluded_prefixes=(".gemini/commands/", ".gemini/agents/", ".gemini/skills/"),
            ),
        )


class OpenCodeImportAdapter(BaseTemplateImportAdapter):
    source_type = ImportSourceType.OPENCODE

    def matches(self, root: Path) -> bool:
        return (root / "opencode.json").exists() or (root / ".opencode").exists()

    def load(self, root: Path) -> ImportedTemplate:
        template_id = _coerce_template_id(root.name)
        warnings: List[str] = []
        unresolved: List[str] = []
        mcp_servers: List[CanonicalMcpServer] = []

        config_path = root / "opencode.json"
        if config_path.exists():
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            mcp_servers.extend(_parse_opencode_mcp(payload, config_path, root))
            if payload.get("commands"):
                warnings.append("opencode_inline_commands_not_imported")
                unresolved.append("opencode_inline_commands_require_manual_review")
            if payload.get("agents"):
                warnings.append("opencode_inline_agents_not_imported")
                unresolved.append("opencode_inline_agents_require_manual_review")

        return ImportedTemplate(
            rootPath=str(root),
            metadata=ImportedTemplateMetadata(
                id=template_id,
                name=template_id,
                sourceType=self.source_type,
            ),
            agentsMdContent=_read_text_if_exists(root / "AGENTS.md") or _read_text_if_exists(root / "CLAUDE.md"),
            commands=_load_markdown_documents(root / ".opencode" / "commands", root),
            agents=_load_markdown_documents(root / ".opencode" / "agents", root),
            skills=_load_skills(root / ".opencode" / "skills", root),
            mcpServers=mcp_servers,
            warnings=warnings,
            unresolvedItems=unresolved,
            resources=_collect_extra_resources(
                root,
                excluded={"AGENTS.md", "CLAUDE.md", "opencode.json"},
                excluded_prefixes=(".opencode/commands/", ".opencode/agents/", ".opencode/skills/"),
            ),
        )


class CanonicalNormalizer:
    """Convert import result to canonical template tree."""

    def write_template(self, imported: ImportedTemplate, destination_root: Path) -> Path:
        template_root = destination_root
        template_root.mkdir(parents=True, exist_ok=True)

        if imported.agents_md_content:
            (template_root / "agents.md").write_text(imported.agents_md_content, encoding="utf-8")

        if imported.output_style:
            output_payload = dict(imported.output_style.data)
            if imported.output_style.fallback_instruction:
                output_payload["fallbackInstruction"] = imported.output_style.fallback_instruction
            (template_root / "output-style.yaml").write_text(
                yaml.safe_dump(output_payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        self._write_skills(imported.skills, template_root)
        self._write_documents(imported.commands, template_root / "commands")
        self._write_documents(imported.agents, template_root / "agents")
        self._write_hooks(imported.hooks, template_root / "hooks")
        self._write_mcp_servers(imported.mcp_servers, template_root / "mcp")
        self._write_resources(imported.resources, template_root / "resources" / "imported")
        self._write_template_yaml(imported, template_root)
        return template_root

    def _write_template_yaml(self, imported: ImportedTemplate, template_root: Path) -> None:
        supported_targets = [target.value for target in CanonicalTarget]
        payload: Dict[str, Any] = {
            "id": imported.metadata.id,
            "name": imported.metadata.name,
            "version": imported.metadata.version,
            "description": imported.metadata.description,
            "schemaVersion": "v0",
            "supportedTargets": supported_targets,
            "features": {
                "agentsMd": {"path": "agents.md"},
                "outputStyle": {"path": "output-style.yaml"},
                "skills": {"path": "skills"},
                "commands": {"path": "commands"},
                "agents": {"path": "agents"},
                "hooks": {"path": "hooks"},
                "mcpServers": {"path": "mcp"},
                "resources": {"path": "resources"},
            },
            "metadata": {
                "import": {
                    "sourceType": str(imported.metadata.source_type),
                    "warnings": imported.warnings,
                    "unresolvedItems": imported.unresolved_items,
                },
                "author": {
                    "name": imported.metadata.author_name,
                    "email": imported.metadata.author_email,
                    "url": imported.metadata.author_url,
                },
                "keywords": imported.metadata.keywords,
                "status": imported.metadata.status,
                "initCommands": imported.metadata.init_commands,
            },
        }
        (template_root / "template.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _write_skills(self, skills: List[CanonicalSkill], template_root: Path) -> None:
        if not skills:
            return
        skills_root = template_root / "skills"
        for skill in skills:
            skill_dir = skills_root / skill.id
            skill_dir.mkdir(parents=True, exist_ok=True)
            content = _render_frontmatter_markdown(skill.frontmatter, skill.content)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def _write_documents(self, docs: List[CanonicalFrontmatterDocument], directory: Path) -> None:
        if not docs:
            return
        directory.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            file_name = Path(doc.path).name
            content = _render_frontmatter_markdown(doc.frontmatter, doc.content)
            (directory / file_name).write_text(content, encoding="utf-8")

    def _write_hooks(self, hooks: List[CanonicalHook], hooks_root: Path) -> None:
        if not hooks:
            return
        hooks_root.mkdir(parents=True, exist_ok=True)
        for hook in hooks:
            payload = dict(hook.raw or {})
            payload.setdefault("id", hook.id)
            payload.setdefault("event", hook.event)
            payload.setdefault("matcher", hook.matcher)
            payload.setdefault("action", hook.action)
            if hook.timeout is not None:
                payload.setdefault("timeout", hook.timeout)
            if hook.failure_policy:
                payload.setdefault("failurePolicy", hook.failure_policy)
            (hooks_root / Path(hook.path).name).write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def _write_mcp_servers(self, servers: List[CanonicalMcpServer], mcp_root: Path) -> None:
        if not servers:
            return
        mcp_root.mkdir(parents=True, exist_ok=True)
        for server in servers:
            payload = dict(server.raw or {})
            payload.setdefault("id", server.id)
            payload.setdefault("transport", server.transport)
            if server.command:
                payload.setdefault("command", server.command)
            if server.args:
                payload.setdefault("args", server.args)
            if server.url:
                payload.setdefault("url", server.url)
            if server.env:
                payload.setdefault("env", server.env)
            if server.headers:
                payload.setdefault("headers", server.headers)
            (mcp_root / Path(server.path).name).write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def _write_resources(self, resources: List[ImportedTemplateAsset], resources_root: Path) -> None:
        for asset in resources:
            asset_path = resources_root / asset.path
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(asset.content)


class TemplateImportService(TemplateBaseService):
    """Multi-source template import entry point."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.adapters: List[BaseTemplateImportAdapter] = [
            ClaudeImportAdapter(),
            OpenCodeImportAdapter(),
            GeminiImportAdapter(),
            CodexImportAdapter(),
        ]
        self.normalizer = CanonicalNormalizer()

    async def import_archive(self, file: UploadFile) -> ImportedTemplate:
        temp_dir = Path(tempfile.mkdtemp())
        try:
            zip_path = temp_dir / (file.filename or "template.zip")
            zip_path.write_bytes(await file.read())
            extract_dir = temp_dir / "extracted"
            try:
                with zipfile.ZipFile(zip_path, "r") as zipf:
                    zipf.extractall(extract_dir)
            except zipfile.BadZipFile as exc:
                raise TemplateImportError("invalid_archive") from exc
            return self.import_from_root(extract_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def import_from_root(self, source_root: Path) -> ImportedTemplate:
        for adapter in self.adapters:
            matched_root = adapter.find_root(source_root)
            if matched_root is not None:
                return adapter.load(matched_root)
        if _has_legacy_marketplace_manifest(source_root):
            raise TemplateImportError("missing_template_package_manifest")
        raise TemplateImportError("unsupported_template_source")


class TemplateMigrationService(TemplateBaseService):
    """Batch convert existing template sources to canonical template tree."""

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.import_service = TemplateImportService(db)

    def migrate_directory(self, source_root: Path, destination_root: Path, overwrite: bool = False) -> List[Path]:
        migrated: List[Path] = []
        for candidate in sorted(p for p in source_root.iterdir() if p.is_dir()):
            imported = self.import_service.import_from_root(candidate)
            target_root = destination_root / imported.metadata.id
            if target_root.exists():
                if not overwrite:
                    raise TemplateImportError(f"destination_exists:{imported.metadata.id}")
                shutil.rmtree(target_root)
            self.import_service.normalizer.write_template(imported, target_root)
            migrated.append(target_root)
        return migrated


def _candidate_roots(extract_dir: Path) -> Iterable[Path]:
    yield extract_dir
    for child in sorted(extract_dir.iterdir()):
        if child.is_dir():
            yield child


def _has_legacy_marketplace_manifest(source_root: Path) -> bool:
    for candidate in _candidate_roots(source_root):
        if (candidate / ".claude-plugin" / "marketplace.json").exists():
            return True
    return False


def _is_valid_template_id(value: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", value))


def _coerce_template_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        return "imported-template"
    if normalized[0].isdigit():
        normalized = f"template-{normalized}"
    return normalized


def _read_text_if_exists(path: Path) -> Optional[str]:
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _parse_frontmatter_markdown(path: Path, root: Path) -> CanonicalFrontmatterDocument:
    raw = path.read_text(encoding="utf-8")
    frontmatter: Dict[str, Any] = {}
    content = raw
    if raw.startswith("---\n"):
        _, remainder = raw.split("---\n", 1)
        frontmatter_text, separator, body = remainder.partition("\n---\n")
        if separator:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
            content = body
    name = str(frontmatter.get("name") or path.stem)
    return CanonicalFrontmatterDocument(
        name=name,
        path=path.relative_to(root).as_posix(),
        content=content,
        frontmatter=frontmatter,
    )


def _load_markdown_documents(directory: Path, root: Path) -> List[CanonicalFrontmatterDocument]:
    if not directory.exists():
        return []
    docs: List[CanonicalFrontmatterDocument] = []
    for path in sorted(directory.rglob("*.md")):
        docs.append(_parse_frontmatter_markdown(path, root))
    return docs


def _load_skills(directory: Path, root: Path) -> List[CanonicalSkill]:
    if not directory.exists():
        return []
    skills: List[CanonicalSkill] = []
    for skill_path in sorted(directory.rglob("SKILL.md")):
        doc = _parse_frontmatter_markdown(skill_path, root)
        skills.append(
            CanonicalSkill(
                id=str(doc.frontmatter.get("name") or skill_path.parent.name),
                path=skill_path.parent.relative_to(root).as_posix(),
                skillMdPath=skill_path.relative_to(root).as_posix(),
                content=doc.content,
                frontmatter=doc.frontmatter,
            )
        )
    return skills


def _load_legacy_output_style(directory: Path, root: Path) -> Optional[CanonicalOutputStyle]:
    if not directory.exists():
        return None
    for style_file in sorted(directory.glob("*.md")):
        return CanonicalOutputStyle(
            path=style_file.relative_to(root).as_posix(),
            data={"legacySource": style_file.name},
            fallbackInstruction=style_file.read_text(encoding="utf-8"),
        )
    return None


def _parse_claude_mcp(path: Path) -> List[CanonicalMcpServer]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    servers: List[CanonicalMcpServer] = []
    for server_id, config in (payload.get("mcpServers") or {}).items():
        servers.append(
            CanonicalMcpServer(
                id=server_id,
                path=f"mcp/{server_id}.yaml",
                transport=str(config.get("type") or "stdio"),
                command=config.get("command"),
                args=list(config.get("args") or []),
                url=config.get("url"),
                env=dict(config.get("env") or {}),
                headers=dict(config.get("headers") or {}),
                raw={
                    "id": server_id,
                    "transport": str(config.get("type") or "stdio"),
                    "command": config.get("command"),
                    "args": list(config.get("args") or []),
                    "url": config.get("url"),
                    "env": dict(config.get("env") or {}),
                    "headers": dict(config.get("headers") or {}),
                },
            )
        )
    return servers


def _parse_claude_hooks(path: Path, root: Path) -> tuple[List[CanonicalHook], List[ImportedTemplateAsset]]:
    hooks, script_assets = _parse_hooks_json_file(path, root)
    assets = _collect_hook_script_assets(hooks, root)
    return hooks, script_assets + assets


def _parse_hooks_json_file(path: Path, root: Path) -> tuple[List[CanonicalHook], List[ImportedTemplateAsset]]:
    if not path.exists():
        return [], []
    payload = json.loads(path.read_text(encoding="utf-8"))
    hooks: List[CanonicalHook] = []
    script_assets: List[ImportedTemplateAsset] = []
    for event_name, rules in (payload.get("hooks") or {}).items():
        for rule_index, rule in enumerate(rules):
            for hook_index, hook_exec in enumerate(rule.get("hooks") or []):
                hook_id = f"{event_name}-{rule_index}-{hook_index}"
                action: Dict[str, Any] = {"type": hook_exec.get("type", "command")}
                if hook_exec.get("command"):
                    action["command"] = hook_exec["command"]
                if hook_exec.get("path"):
                    action["path"] = hook_exec["path"]
                if action.get("path"):
                    script_path = (path.parent / action["path"]).resolve()
                    if script_path.exists() and script_path.is_file():
                        rel_path = script_path.relative_to(root).as_posix()
                        script_assets.append(
                            ImportedTemplateAsset(path=rel_path, content=script_path.read_bytes())
                        )
                hooks.append(
                    CanonicalHook(
                        id=hook_id,
                        path=f"{hook_id}.yaml",
                        event=event_name,
                        matcher=dict(rule.get("matcher") or {}),
                        action=action,
                        timeout=hook_exec.get("timeout"),
                        failurePolicy=None,
                        raw={
                            "id": hook_id,
                            "event": event_name,
                            "matcher": dict(rule.get("matcher") or {}),
                            "action": action,
                            "timeout": hook_exec.get("timeout"),
                        },
                    )
                )
    return hooks, script_assets


def _collect_hook_script_assets(hooks: List[CanonicalHook], root: Path) -> List[ImportedTemplateAsset]:
    assets: List[ImportedTemplateAsset] = []
    for hook in hooks:
        script_path = hook.action.get("path")
        if not script_path:
            continue
        resolved = (root / script_path).resolve()
        if resolved.exists() and resolved.is_file():
            assets.append(
                ImportedTemplateAsset(path=resolved.relative_to(root).as_posix(), content=resolved.read_bytes())
            )
    return assets


def _parse_codex_mcp(payload: Dict[str, Any], config_path: Path, root: Path) -> List[CanonicalMcpServer]:
    servers: List[CanonicalMcpServer] = []
    for server_id, config in (payload.get("mcp_servers") or {}).items():
        servers.append(
            CanonicalMcpServer(
                id=server_id,
                path=f"mcp/{server_id}.yaml",
                transport="stdio",
                command=config.get("command"),
                args=list(config.get("args") or []),
                env={k: str(v) for k, v in dict(config.get("env") or {}).items()},
                raw={
                    "id": server_id,
                    "transport": "stdio",
                    "command": config.get("command"),
                    "args": list(config.get("args") or []),
                    "env": {k: str(v) for k, v in dict(config.get("env") or {}).items()},
                    "sourcePath": config_path.relative_to(root).as_posix(),
                },
            )
        )
    return servers


def _parse_gemini_mcp(payload: Dict[str, Any], settings_path: Path, root: Path) -> List[CanonicalMcpServer]:
    servers: List[CanonicalMcpServer] = []
    for server_id, config in (payload.get("mcpServers") or {}).items():
        servers.append(
            CanonicalMcpServer(
                id=server_id,
                path=f"mcp/{server_id}.yaml",
                transport="stdio" if config.get("command") else str(config.get("transport") or "http"),
                command=config.get("command"),
                args=list(config.get("args") or []),
                url=config.get("url"),
                env={k: str(v) for k, v in dict(config.get("env") or {}).items()},
                raw={
                    "id": server_id,
                    "transport": "stdio" if config.get("command") else str(config.get("transport") or "http"),
                    "command": config.get("command"),
                    "args": list(config.get("args") or []),
                    "url": config.get("url"),
                    "env": {k: str(v) for k, v in dict(config.get("env") or {}).items()},
                    "sourcePath": settings_path.relative_to(root).as_posix(),
                },
            )
        )
    return servers


def _parse_gemini_hooks(payload: Dict[str, Any], settings_path: Path, root: Path) -> List[CanonicalHook]:
    hooks: List[CanonicalHook] = []
    raw_hooks = payload.get("hooks") or []
    if isinstance(raw_hooks, dict):
        iterable = raw_hooks.items()
    else:
        iterable = enumerate(raw_hooks)

    for key, item in iterable:
        if not isinstance(item, dict):
            continue
        event_name = str(item.get("event") or key)
        action: Dict[str, Any] = {"type": "command"}
        if item.get("command"):
            action["command"] = item["command"]
        hooks.append(
            CanonicalHook(
                id=f"{event_name}-{len(hooks)}",
                path=f"{event_name}-{len(hooks)}.yaml",
                event=event_name,
                matcher=dict(item.get("matcher") or {}),
                action=action,
                raw={
                    "event": event_name,
                    "matcher": dict(item.get("matcher") or {}),
                    "action": action,
                    "sourcePath": settings_path.relative_to(root).as_posix(),
                },
            )
        )
    return hooks


def _parse_opencode_mcp(payload: Dict[str, Any], config_path: Path, root: Path) -> List[CanonicalMcpServer]:
    mcp_section = (payload.get("mcp") or {}).get("servers") or {}
    servers: List[CanonicalMcpServer] = []
    for server_id, config in mcp_section.items():
        servers.append(
            CanonicalMcpServer(
                id=server_id,
                path=f"mcp/{server_id}.yaml",
                transport="stdio" if config.get("command") else str(config.get("transport") or "http"),
                command=config.get("command"),
                args=list(config.get("args") or []),
                url=config.get("url"),
                env={k: str(v) for k, v in dict(config.get("env") or {}).items()},
                raw={
                    "id": server_id,
                    "transport": "stdio" if config.get("command") else str(config.get("transport") or "http"),
                    "command": config.get("command"),
                    "args": list(config.get("args") or []),
                    "url": config.get("url"),
                    "env": {k: str(v) for k, v in dict(config.get("env") or {}).items()},
                    "sourcePath": config_path.relative_to(root).as_posix(),
                },
            )
        )
    return servers


def _load_gemini_command_documents(directory: Path, root: Path) -> List[CanonicalFrontmatterDocument]:
    if not directory.exists():
        return []
    docs: List[CanonicalFrontmatterDocument] = []
    for path in sorted(directory.glob("*.toml")):
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        prompt = payload.get("prompt") or {}
        content = str(prompt.get("template") or "")
        frontmatter = {
            "name": payload.get("name") or path.stem,
            "description": payload.get("description") or "",
        }
        docs.append(
            CanonicalFrontmatterDocument(
                name=str(frontmatter["name"]),
                path=f"commands/{path.stem}.md",
                content=content,
                frontmatter=frontmatter,
            )
        )
    return docs


def _collect_extra_resources(
    root: Path,
    *,
    excluded: set[str],
    excluded_prefixes: tuple[str, ...],
) -> List[ImportedTemplateAsset]:
    resources: List[ImportedTemplateAsset] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(root).as_posix()
        if rel_path in excluded:
            continue
        if any(rel_path.startswith(prefix) for prefix in excluded_prefixes):
            continue
        resources.append(ImportedTemplateAsset(path=rel_path, content=path.read_bytes()))
    return resources


def _render_frontmatter_markdown(frontmatter: Dict[str, Any], content: str) -> str:
    if not frontmatter:
        return content
    return "---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip() + "\n---\n" + content


__all__ = [
    "CanonicalNormalizer",
    "ClaudeImportAdapter",
    "CodexImportAdapter",
    "GeminiImportAdapter",
    "OpenCodeImportAdapter",
    "TemplateImportError",
    "TemplateImportService",
    "TemplateMigrationService",
]
