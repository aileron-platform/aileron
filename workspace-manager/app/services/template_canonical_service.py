"""Canonical template filesystem loader and validator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

from app.models.template_canonical import (
    CanonicalFeaturePath,
    CanonicalFrontmatterDocument,
    CanonicalHook,
    CanonicalMcpServer,
    CanonicalOutputStyle,
    CanonicalResourceNode,
    CanonicalSkill,
    CanonicalTemplate,
    CanonicalTemplateIndex,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)

DEFAULT_FEATURE_PATHS: Dict[str, str] = {
    "agentsMd": "agents.md",
    "outputStyle": "output-style.yaml",
    "skills": "skills",
    "commands": "commands",
    "agents": "agents",
    "hooks": "hooks",
    "mcpServers": "mcp",
    "resources": "resources",
}


class CanonicalTemplateValidationError(ValueError):
    """Raised when canonical template filesystem validation fails."""


class TemplateCanonicalService(TemplateBaseService):
    """Load and validate canonical template filesystem trees."""

    def load_from_template_id(self, template_id: str) -> CanonicalTemplate:
        return self.load_from_root(self._resolve_template_dir(template_id))

    def load_from_root(self, template_root: Path) -> CanonicalTemplate:
        template_root = template_root.resolve()
        index = self._load_index(template_root)
        self.validate_root(template_root, index)

        agents_md_path = self._resolve_feature_path(template_root, index, "agentsMd")
        output_style_path = self._resolve_feature_path(template_root, index, "outputStyle")
        skills_path = self._resolve_feature_path(template_root, index, "skills")
        commands_path = self._resolve_feature_path(template_root, index, "commands")
        agents_path = self._resolve_feature_path(template_root, index, "agents")
        hooks_path = self._resolve_feature_path(template_root, index, "hooks")
        mcp_path = self._resolve_feature_path(template_root, index, "mcpServers")
        resources_path = self._resolve_feature_path(template_root, index, "resources")

        return CanonicalTemplate(
            rootPath=str(template_root),
            index=index,
            agentsMdPath=self._to_relative_str(agents_md_path, template_root) if agents_md_path.exists() else None,
            agentsMdContent=agents_md_path.read_text(encoding="utf-8") if agents_md_path.exists() else None,
            outputStyle=self._load_output_style(output_style_path, template_root),
            skills=self._load_skills(skills_path, template_root),
            commands=self._load_markdown_documents(commands_path, template_root),
            agents=self._load_markdown_documents(agents_path, template_root),
            hooks=self._load_hooks(hooks_path, template_root),
            mcpServers=self._load_mcp_servers(mcp_path, template_root),
            resources=self._load_resources(resources_path, template_root),
        )

    def validate_root(self, template_root: Path, index: CanonicalTemplateIndex | None = None) -> None:
        if not template_root.exists() or not template_root.is_dir():
            raise CanonicalTemplateValidationError(f"Template root not found: {template_root}")

        index = index or self._load_index(template_root)
        expected_dir_name = template_root.name
        if index.id != expected_dir_name:
            raise CanonicalTemplateValidationError(
                f"template.yaml id '{index.id}' does not match root directory '{expected_dir_name}'"
            )

        for feature_name in DEFAULT_FEATURE_PATHS:
            feature_path = self._resolve_feature_path(template_root, index, feature_name)
            if not self._is_safe_path(feature_path, template_root):
                raise CanonicalTemplateValidationError(
                    f"Feature path for '{feature_name}' escapes template root: {feature_path}"
                )

    def _load_index(self, template_root: Path) -> CanonicalTemplateIndex:
        index_path = template_root / "template.yaml"
        if not index_path.exists():
            raise CanonicalTemplateValidationError(f"Missing template.yaml in {template_root}")

        payload = self._read_yaml(index_path)
        if not isinstance(payload, dict):
            raise CanonicalTemplateValidationError("template.yaml must contain a YAML object")

        payload.setdefault("features", {})
        features = dict(payload["features"])
        for feature_name, default_path in DEFAULT_FEATURE_PATHS.items():
            features.setdefault(feature_name, CanonicalFeaturePath(path=default_path).model_dump())
        payload["features"] = features
        return CanonicalTemplateIndex(**payload)

    def _resolve_feature_path(
        self, template_root: Path, index: CanonicalTemplateIndex, feature_name: str
    ) -> Path:
        feature = index.features.get(feature_name)
        path = feature.path if feature else DEFAULT_FEATURE_PATHS[feature_name]
        if Path(path).is_absolute():
            raise CanonicalTemplateValidationError(f"Absolute feature path is not allowed: {path}")
        return (template_root / path).resolve()

    def _load_output_style(self, path: Path, template_root: Path) -> CanonicalOutputStyle | None:
        if not path.exists():
            return None
        payload = self._read_yaml(path)
        if not isinstance(payload, dict):
            raise CanonicalTemplateValidationError("output-style.yaml must contain a YAML object")
        return CanonicalOutputStyle(
            path=self._to_relative_str(path, template_root),
            data=payload,
            fallbackInstruction=payload.get("fallbackInstruction"),
        )

    def _load_skills(self, skills_dir: Path, template_root: Path) -> List[CanonicalSkill]:
        if not skills_dir.exists():
            return []
        if not skills_dir.is_dir():
            raise CanonicalTemplateValidationError("skills path must be a directory")

        skills: List[CanonicalSkill] = []
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                raise CanonicalTemplateValidationError(f"Skill directory missing SKILL.md: {child.name}")
            frontmatter, content = self._parse_frontmatter_document(skill_md.read_text(encoding="utf-8"))
            skill_id = str(frontmatter.get("name") or child.name)
            skills.append(
                CanonicalSkill(
                    id=skill_id,
                    path=self._to_relative_str(child, template_root),
                    skillMdPath=self._to_relative_str(skill_md, template_root),
                    content=content,
                    frontmatter=frontmatter,
                )
            )
        return skills

    def _load_markdown_documents(
        self, directory: Path, template_root: Path
    ) -> List[CanonicalFrontmatterDocument]:
        if not directory.exists():
            return []
        if not directory.is_dir():
            raise CanonicalTemplateValidationError(f"Expected directory for markdown documents: {directory}")

        documents: List[CanonicalFrontmatterDocument] = []
        for file_path in sorted(directory.rglob("*.md")):
            frontmatter, content = self._parse_frontmatter_document(file_path.read_text(encoding="utf-8"))
            logical_name = str(frontmatter.get("name") or file_path.stem)
            documents.append(
                CanonicalFrontmatterDocument(
                    name=logical_name,
                    path=self._to_relative_str(file_path, template_root),
                    content=content,
                    frontmatter=frontmatter,
                )
            )
        return documents

    def _load_hooks(self, hooks_dir: Path, template_root: Path) -> List[CanonicalHook]:
        if not hooks_dir.exists():
            return []
        if not hooks_dir.is_dir():
            raise CanonicalTemplateValidationError("hooks path must be a directory")

        hooks: List[CanonicalHook] = []
        for file_path in sorted(self._iter_yaml_files(hooks_dir)):
            if "scripts" in file_path.parts:
                continue
            payload = self._read_yaml(file_path)
            if not isinstance(payload, dict):
                raise CanonicalTemplateValidationError(f"Hook file must contain a YAML object: {file_path.name}")
            hook_id = str(payload.get("id") or file_path.stem)
            event = payload.get("event")
            if not event:
                raise CanonicalTemplateValidationError(f"Hook file missing event: {file_path.name}")
            hooks.append(
                CanonicalHook(
                    id=hook_id,
                    path=self._to_relative_str(file_path, template_root),
                    event=str(event),
                    matcher=dict(payload.get("matcher") or {}),
                    action=dict(payload.get("action") or {}),
                    timeout=payload.get("timeout"),
                    failurePolicy=payload.get("failurePolicy"),
                    raw=payload,
                )
            )
        return hooks

    def _load_mcp_servers(self, mcp_dir: Path, template_root: Path) -> List[CanonicalMcpServer]:
        if not mcp_dir.exists():
            return []
        if not mcp_dir.is_dir():
            raise CanonicalTemplateValidationError("mcp path must be a directory")

        servers: List[CanonicalMcpServer] = []
        for file_path in sorted(self._iter_yaml_files(mcp_dir)):
            payload = self._read_yaml(file_path)
            if not isinstance(payload, dict):
                raise CanonicalTemplateValidationError(f"MCP file must contain a YAML object: {file_path.name}")
            server_id = str(payload.get("id") or file_path.stem)
            transport = payload.get("transport")
            if not transport:
                raise CanonicalTemplateValidationError(f"MCP file missing transport: {file_path.name}")
            servers.append(
                CanonicalMcpServer(
                    id=server_id,
                    path=self._to_relative_str(file_path, template_root),
                    transport=str(transport),
                    command=payload.get("command"),
                    args=list(payload.get("args") or []),
                    url=payload.get("url"),
                    env=dict(payload.get("env") or {}),
                    headers=dict(payload.get("headers") or {}),
                    raw=payload,
                )
            )
        return servers

    def _load_resources(self, resources_dir: Path, template_root: Path) -> List[CanonicalResourceNode]:
        if not resources_dir.exists():
            return []
        if not resources_dir.is_dir():
            raise CanonicalTemplateValidationError("resources path must be a directory")

        return [self._build_resource_node(child, template_root) for child in sorted(resources_dir.iterdir())]

    def _build_resource_node(self, path: Path, template_root: Path) -> CanonicalResourceNode:
        if path.is_dir():
            return CanonicalResourceNode(
                path=self._to_relative_str(path, template_root),
                type="directory",
                children=[self._build_resource_node(child, template_root) for child in sorted(path.iterdir())],
            )
        return CanonicalResourceNode(path=self._to_relative_str(path, template_root), type="file")

    @staticmethod
    def _parse_frontmatter_document(raw: str) -> Tuple[Dict[str, Any], str]:
        if not raw.startswith("---\n"):
            return {}, raw
        parts = raw.split("\n---\n", 1)
        if len(parts) != 2:
            return {}, raw
        frontmatter_raw = parts[0][4:]
        content = parts[1]
        frontmatter = yaml.safe_load(frontmatter_raw) or {}
        if not isinstance(frontmatter, dict):
            raise CanonicalTemplateValidationError("Document frontmatter must be a YAML object")
        return frontmatter, content

    @staticmethod
    def _iter_yaml_files(directory: Path) -> Iterable[Path]:
        for pattern in ("*.yaml", "*.yml"):
            yield from directory.rglob(pattern)

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CanonicalTemplateValidationError(f"Invalid YAML in {path.name}: {exc}") from exc

    @staticmethod
    def _to_relative_str(path: Path, root: Path) -> str:
        return path.relative_to(root).as_posix()
