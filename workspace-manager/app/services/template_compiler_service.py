"""Canonical template compiler and target adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.template_canonical import (
    CanonicalTarget,
    CompileIssue,
    CompiledTemplateFile,
    InstallPlan,
)
from app.services.template_artifact_cache_service import TemplateArtifactCacheService
from app.services.template_canonical_service import TemplateCanonicalService


class BaseTemplateTargetAdapter(ABC):
    def __init__(self, target: CanonicalTarget) -> None:
        self.target = target

    @abstractmethod
    def compile(self, template) -> InstallPlan:
        raise NotImplementedError

    def _compile_agents_md(self, template, file_name: str) -> List[CompiledTemplateFile]:
        if not template.agents_md_content:
            return []
        return [
            CompiledTemplateFile(
                path=file_name,
                source=template.agents_md_path or "agents.md",
                content=template.agents_md_content,
            )
        ]

    def _compile_markdown_collection(
        self,
        template,
        docs,
        directory: str,
        extension: str = ".md",
        source_root: str = "commands",
    ) -> List[CompiledTemplateFile]:
        files: List[CompiledTemplateFile] = []
        for doc in docs:
            target_name = self._target_relative_path(doc.path, source_root, extension)
            files.append(
                CompiledTemplateFile(
                    path=f"{directory}/{target_name}",
                    source=doc.path,
                    content=doc.content,
                )
            )
        return files

    @staticmethod
    def _target_relative_path(doc_path: str, source_root: str, extension: str = ".md") -> str:
        path = Path(doc_path)
        try:
            relative = path.relative_to(source_root)
        except ValueError:
            relative = Path(path.name)
        return relative.with_suffix(extension).as_posix()

    @staticmethod
    def _is_namespaced_command(doc_path: str) -> bool:
        try:
            relative = Path(doc_path).relative_to("commands")
        except ValueError:
            relative = Path(doc_path)
        return len(relative.parts) > 1

    def _compile_output_style_fallback(self, template) -> List[CompileIssue]:
        if not template.output_style:
            return []
        fallback = template.output_style.fallback_instruction or "Output style compiled as instruction fallback"
        return [
            CompileIssue(
                feature="outputStyle",
                target=self.target,
                message=fallback,
            )
        ]


class ClaudeCodeAdapter(BaseTemplateTargetAdapter):
    def __init__(self) -> None:
        super().__init__(CanonicalTarget.CLAUDE_CODE)

    def compile(self, template) -> InstallPlan:
        return InstallPlan(
            target=self.target,
            files=[
                *self._compile_agents_md(template, "CLAUDE.md"),
                *self._compile_markdown_collection(template, template.commands, ".claude/commands"),
                *self._compile_markdown_collection(template, template.agents, ".claude/agents/user", source_root="agents"),
            ],
            warnings=[],
            unsupported=[],
            degradationNotes=[],
            installHints=_build_runtime_install_hints(template),
        )


class CodexAdapter(BaseTemplateTargetAdapter):
    def __init__(self) -> None:
        super().__init__(CanonicalTarget.CODEX)

    def compile(self, template) -> InstallPlan:
        unsupported = [
            CompileIssue(
                feature="commands",
                target=self.target,
                message=f"Codex prompts do not support namespaced command path: {doc.path}",
            )
            for doc in template.commands
            if self._is_namespaced_command(doc.path)
        ]
        prompt_docs = [doc for doc in template.commands if not self._is_namespaced_command(doc.path)]
        fallback_issues = self._compile_output_style_fallback(template)
        return InstallPlan(
            target=self.target,
            files=[
                *self._compile_agents_md(template, "AGENTS.md"),
                *self._compile_markdown_collection(template, prompt_docs, ".codex/prompts"),
                *self._compile_markdown_collection(template, template.agents, ".codex/agents", source_root="agents"),
            ],
            warnings=[*fallback_issues, *unsupported],
            unsupported=unsupported,
            degradationNotes=fallback_issues,
            installHints=_build_runtime_install_hints(template),
        )


class GeminiAdapter(BaseTemplateTargetAdapter):
    def __init__(self) -> None:
        super().__init__(CanonicalTarget.GEMINI)

    def compile(self, template) -> InstallPlan:
        files = self._compile_agents_md(template, "GEMINI.md")
        for doc in template.commands:
            description = str(doc.frontmatter.get("description") or "")
            target_name = self._target_relative_path(doc.path, "commands", ".toml")
            toml_content = "\n".join(
                [
                    f'name = "{doc.name}"',
                    f'description = "{description}"',
                    "",
                    "[prompt]",
                    'template = """',
                    doc.content.rstrip("\n"),
                    '"""',
                    "",
                ]
            )
            files.append(
                CompiledTemplateFile(
                    path=f".gemini/commands/{target_name}",
                    source=doc.path,
                    content=toml_content,
                )
            )
        files.extend(self._compile_markdown_collection(template, template.agents, ".gemini/agents", source_root="agents"))
        return InstallPlan(
            target=self.target,
            files=files,
            warnings=self._compile_output_style_fallback(template),
            unsupported=[],
            degradationNotes=self._compile_output_style_fallback(template),
            installHints=_build_runtime_install_hints(template),
        )


class OpenCodeAdapter(BaseTemplateTargetAdapter):
    def __init__(self) -> None:
        super().__init__(CanonicalTarget.OPENCODE)

    def compile(self, template) -> InstallPlan:
        return InstallPlan(
            target=self.target,
            files=[
                *self._compile_agents_md(template, "AGENTS.md"),
                *self._compile_markdown_collection(template, template.commands, ".opencode/commands"),
                *self._compile_markdown_collection(template, template.agents, ".opencode/agents", source_root="agents"),
            ],
            warnings=self._compile_output_style_fallback(template),
            unsupported=[],
            degradationNotes=self._compile_output_style_fallback(template),
            installHints=_build_runtime_install_hints(template),
        )


def _build_runtime_install_hints(template) -> Dict[str, Any]:
    mcp_servers: Dict[str, Any] = {}
    for server in template.mcp_servers:
        server_config: Dict[str, Any] = {"type": server.transport}
        if server.command:
            server_config["command"] = server.command
        if server.args:
            server_config["args"] = server.args
        if server.url:
            server_config["url"] = server.url
        if server.env:
            server_config["env"] = server.env
        if server.headers:
            server_config["headers"] = server.headers
        mcp_servers[server.id] = server_config

    hooks: Dict[str, List[Dict[str, Any]]] = {}
    for hook in template.hooks:
        hook_rule: Dict[str, Any] = {"matcher": hook.matcher or {"tool": "*"}}
        action = dict(hook.action)
        if action:
            hook_rule["hooks"] = [action]
        else:
            hook_rule["hooks"] = []
        hooks.setdefault(hook.event, []).append(hook_rule)

    return {
        "agentsMdContent": template.agents_md_content,
        "commands": [{"fileName": Path(doc.path).name, "content": doc.content} for doc in template.commands],
        "agents": [{"fileName": Path(doc.path).name, "content": doc.content} for doc in template.agents],
        "hooks": hooks,
        "mcpServers": mcp_servers,
        "outputStyle": (
            [{"fileName": Path(template.output_style.path).name, "content": template.output_style.data.get("fallbackInstruction", "")}]
            if template.output_style
            else []
        ),
        "skills": [{"path": skill.skill_md_path, "content": skill.content} for skill in template.skills],
    }


class TemplateCompilerService:
    def __init__(self, db: Session):
        self.canonical_service = TemplateCanonicalService(db)
        self.cache_service = TemplateArtifactCacheService(db)
        self.adapters = {
            CanonicalTarget.CLAUDE_CODE: ClaudeCodeAdapter(),
            CanonicalTarget.CODEX: CodexAdapter(),
            CanonicalTarget.GEMINI: GeminiAdapter(),
            CanonicalTarget.OPENCODE: OpenCodeAdapter(),
        }

    def compile_template(self, template_id: str, target: str) -> InstallPlan:
        template_root = self.canonical_service._resolve_template_dir(template_id)
        source_hash = self.cache_service.compute_source_hash(template_root)
        cached_plan = self.cache_service.load_compile_cache(template_id, target, source_hash)
        if cached_plan is not None:
            return cached_plan

        canonical = self.canonical_service.load_from_template_id(template_id)
        target_enum = CanonicalTarget(target)
        plan = self.adapters[target_enum].compile(canonical)
        return self.cache_service.save_compile_cache(template_id, target, source_hash, plan)
