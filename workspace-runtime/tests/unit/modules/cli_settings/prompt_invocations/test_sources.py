from __future__ import annotations

import pytest

from app.modules.cli_settings.prompt_invocations.config import PromptInvocationTool
from app.modules.cli_settings.prompt_invocations.models import PromptInvocationScope
from app.modules.cli_settings.prompt_invocations.sources import (
    SkillPromptInvocationSource,
    SlashCommandPromptInvocationSource,
)


class FakeSlashCommandService:
    def list_scopes(self, workspace_id: str, scope=None):
        return {
            "workspaceId": workspace_id,
            "items": [
                {
                    "path": "ops/deploy.md",
                    "description": "Deploy the service",
                    "scope": "project",
                    "size": "1KB",
                    "format": "markdown",
                }
            ],
            "availableScopes": [],
        }


class FakeSkillService:
    def __init__(self) -> None:
        self.cleared_scopes: list[str] = []

    def clear_tree_cache(self, scope: str) -> None:
        self.cleared_scopes.append(scope)

    def get_tree(self, path: str, scope: str, max_depth: int):
        return {
            "path": path,
            "scope": scope,
            "nodes": [
                {
                    "id": "/review",
                    "name": "review",
                    "path": "/review",
                    "type": "directory",
                    "children": [
                        {
                            "id": "/review/SKILL.md",
                            "name": "SKILL.md",
                            "path": "/review/SKILL.md",
                            "type": "file",
                            "skillName": "review",
                            "skillDescription": "Review the current changes",
                        }
                    ],
                }
            ],
            "total": 1,
        }


class BrokenMetadataSkillService(FakeSkillService):
    def get_tree(self, path: str, scope: str, max_depth: int):
        tree = super().get_tree(path, scope, max_depth)
        skill = tree["nodes"][0]["children"][0]
        skill.pop("skillName")
        skill.pop("skillDescription")
        return tree

    def read_file(self, path: str, scope: str):
        raise OSError("skill metadata unavailable")


class BrokenClaudePluginCommandService:
    def list_scopes(
        self,
        workspace_id: str,
        scope=None,
        *,
        strict_plugin_errors: bool = False,
    ):
        assert strict_plugin_errors is True
        raise OSError("plugin commands unavailable")


def test_codex_sources_return_runtime_owned_invocation_formats() -> None:
    skill_service = FakeSkillService()
    command_source = SlashCommandPromptInvocationSource(
        PromptInvocationTool.CODEX,
        PromptInvocationScope.PROJECT,
        service_factory=FakeSlashCommandService,
    )
    skill_source = SkillPromptInvocationSource(
        PromptInvocationTool.CODEX,
        PromptInvocationScope.PROJECT,
        service_factory=lambda workspace_id: skill_service,
    )

    command = command_source.load("ws-1")[0]
    skill = skill_source.load("ws-1")[0]

    assert command.display_name == "ops/deploy"
    assert command.invocation == "/ops/deploy"
    assert skill.display_name == "review"
    assert skill.invocation == "$review"
    assert skill_service.cleared_scopes == ["project"]


def test_skill_metadata_failure_is_reported_to_the_catalog() -> None:
    source = SkillPromptInvocationSource(
        PromptInvocationTool.CODEX,
        PromptInvocationScope.PROJECT,
        service_factory=lambda workspace_id: BrokenMetadataSkillService(),
    )

    with pytest.raises(OSError, match="skill metadata unavailable"):
        source.load("ws-1")


def test_claude_plugin_command_failure_is_not_suppressed() -> None:
    source = SlashCommandPromptInvocationSource(
        PromptInvocationTool.CLAUDE,
        PromptInvocationScope.PLUGIN,
        service_factory=BrokenClaudePluginCommandService,
        refresh_plugin_cache=lambda workspace_id: None,
    )

    with pytest.raises(OSError, match="plugin commands unavailable"):
        source.load("ws-1")


def test_claude_plugin_skills_refresh_provider_and_tree_caches() -> None:
    refreshed_workspaces: list[str] = []
    skill_service = FakeSkillService()
    source = SkillPromptInvocationSource(
        PromptInvocationTool.CLAUDE,
        PromptInvocationScope.PLUGIN,
        service_factory=lambda workspace_id: skill_service,
        refresh_plugin_cache=refreshed_workspaces.append,
    )

    source.load("ws-1")

    assert refreshed_workspaces == ["ws-1"]
    assert skill_service.cleared_scopes == ["plugin"]
