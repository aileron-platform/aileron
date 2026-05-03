"""Internal API Template Install related tests"""

from __future__ import annotations

from typing import Any

from app.modules.internal.dependencies import (
    get_template_install_service,
    verify_internal_token,
)
from app.modules.internal.template_install_models import InstallResults

from .helpers import override_dependency


class TemplateInstallServiceStub:
    """Configurable return result TemplateInstallService stub"""

    def __init__(self) -> None:
        self.last_slash_command_request: Any | None = None
        self.slash_commands_result: tuple[bool, InstallResults] = (
            True,
            InstallResults(created=["test.md"], updated=[], failed=[]),
        )
        self.subagents_result: tuple[bool, InstallResults] = (
            True,
            InstallResults(created=["agent.md"], updated=[], failed=[]),
        )
        self.output_styles_result: tuple[bool, InstallResults] = (
            True,
            InstallResults(created=["style.md"], updated=[], failed=[]),
        )
        self.claude_md_result: bool = True
        self.mcp_result: tuple[bool, InstallResults] = (
            True,
            InstallResults(created=["server1"], updated=[], failed=[]),
        )
        self.hooks_result: tuple[bool, InstallResults] = (
            True,
            InstallResults(created=["hook1"], updated=[], failed=[]),
        )
        self.scripts_result: tuple[bool, InstallResults, str, int] = (
            True,
            InstallResults(created=["script.sh"], updated=[], failed=[]),
            "/scripts/test-template",
            1024,
        )
        self.skills_result: tuple[bool, InstallResults, str, int] = (
            True,
            InstallResults(created=["skills/demo.md"], updated=[], failed=[]),
            "/workspace/.claude/skills",
            128,
        )
        self.compiled_files_result: dict[str, InstallResults] = {
            "claudeMd": InstallResults(created=["AGENTS.md"], updated=[], failed=[]),
            "slashCommands": InstallResults(created=[".codex/prompts/review.md"], updated=[], failed=[]),
            "subagents": InstallResults(created=[".codex/agents/reviewer.md"], updated=[], failed=[]),
            "outputStyles": InstallResults(created=[], updated=[], failed=[]),
            "files": InstallResults(created=[], updated=[], failed=[]),
        }

    async def install_slash_commands(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults]:
        self.last_slash_command_request = request
        return self.slash_commands_result

    async def install_subagents(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults]:
        return self.subagents_result

    async def install_output_styles(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults]:
        return self.output_styles_result

    async def install_claude_md(self, workspace_id: str, request: Any) -> bool:
        return self.claude_md_result

    async def install_mcp_servers(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults]:
        return self.mcp_result

    async def install_hooks(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults]:
        return self.hooks_result

    async def install_scripts(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults, str, int]:
        return self.scripts_result

    async def install_skills(
        self, workspace_id: str, request: Any
    ) -> tuple[bool, InstallResults, str, int]:
        return self.skills_result

    async def install_compiled_files(
        self, workspace_id: str, request: Any
    ) -> dict[str, InstallResults]:
        return self.compiled_files_result

    async def install_target_mcp_servers(
        self, workspace_id: str, cli_type: str, mcp_servers: Any
    ) -> tuple[bool, InstallResults]:
        return self.mcp_result

    async def install_target_output_style(
        self, workspace_id: str, cli_type: str, output_styles: Any
    ) -> tuple[bool, InstallResults]:
        return self.output_styles_result

    async def install_target_hooks(
        self, workspace_id: str, cli_type: str, hooks: Any
    ) -> tuple[bool, InstallResults]:
        return self.hooks_result

    async def execute_init_commands(
        self, workspace_id: str, commands: str
    ) -> tuple[bool, str, str]:
        return True, "success", ""


async def _allow_internal_token():  # pragma: no cover - for override
    return None


def test_ti_001_install_slash_commands_success(client):
    """Test Slash Commands installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/slash-commands/install",
            json={
                "commands": [
                    {"fileName": "test.md", "content": "# Test Command\nTest content"}
                ]
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "slash commands" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"
    assert len(payload["results"]["created"]) == 1


def test_ti_002_install_subagents_success(client):
    """Test Subagents installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/subagents/install",
            json={
                "subagents": [
                    {"fileName": "agent.md", "content": "# Test Agent\nAgent content"}
                ]
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "subagents" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"
    assert len(payload["results"]["created"]) == 1


def test_ti_003_install_output_styles_success(client):
    """Test Output Styles installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/output-styles/install",
            json={
                "outputStyles": [
                    {"fileName": "style.md", "content": "# Test Style\nStyle content"}
                ]
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "output styles" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"
    assert len(payload["results"]["created"]) == 1


def test_ti_004_install_claude_md_success(client):
    """Test Claude.md installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/claude-md/install",
            json={"content": "# Claude.md\nProject instructions"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Claude.md" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"


def test_ti_005_install_mcp_servers_success(client):
    """Test MCP Servers installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/mcp/install",
            json={
                "mcpServers": {
                    "test-server": {
                        "type": "stdio",
                        "command": "node",
                        "args": ["server.js"],
                    }
                }
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "MCP servers" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"
    assert len(payload["results"]["created"]) == 1


def test_ti_006_install_hooks_success(client):
    """Test Hooks installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/claude-code/hooks/install",
            json={
                "hooks": {
                    "onFileChange": [
                        {
                            "matcher": "*.py",
                            "hooks": [{"type": "command", "command": "echo test"}],
                        }
                    ]
                }
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "hooks" in payload["message"]
    assert payload["workspaceId"] == "test-workspace"


def test_ti_007_install_scripts_success(client):
    """Test Scripts installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/scripts/install",
            json={
                "templateName": "test-template",
                "scripts": [
                    {
                        "path": "setup.sh",
                        "content": "#!/bin/bash\necho 'setup'",
                        "executable": True,
                    }
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "scripts" in payload["message"]
    assert payload["templateName"] == "test-template"
    assert "/scripts/test-template" in payload["targetPath"]
    assert payload["totalFiles"] == 1
    assert payload["totalSize"] == 1024


def test_ti_008_install_template_batch_success(client):
    """Test batch template installation success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/templates/install",
            json={
                "templateId": "test-template-id",
                "templateName": "test-template",
                "claudeMd": {"content": "# Claude.md\nTest content"},
                "slashCommands": [
                    {"fileName": "test.md", "content": "# Test\nContent"}
                ],
                "subagents": [{"fileName": "agent.md", "content": "# Agent\nContent"}],
                "outputStyles": [
                    {"fileName": "style.md", "content": "# Style\nContent"}
                ],
                "mcpServers": {
                    "test-server": {"type": "stdio", "command": "node", "args": []}
                },
                "hooks": {
                    "onFileChange": [
                        {
                            "matcher": "*.py",
                            "hooks": [{"type": "command", "command": "echo test"}],
                        }
                    ]
                },
                "scripts": [
                    {
                        "path": "setup.sh",
                        "content": "#!/bin/bash\necho 'setup'",
                        "executable": True,
                    }
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Template installation completed" in payload["message"]
    assert payload["templateId"] == "test-template-id"
    assert payload["templateName"] == "test-template"
    assert payload["results"]["claudeMd"] is not None
    assert payload["results"]["slashCommands"] is not None
    assert payload["results"]["subagents"] is not None
    assert payload["results"]["outputStyles"] is not None
    assert payload["results"]["mcp"] is not None
    assert payload["results"]["hooks"] is not None
    assert payload["results"]["scripts"] is not None


def test_ti_009_install_template_batch_with_init_commands(client):
    """Test batch template installation (with init commands) success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/templates/install",
            json={
                "templateId": "test-template-id",
                "templateName": "test-template",
                "initCommands": "npm install",
                "claudeMd": {"content": "# Claude.md\nTest content"},
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Template installation completed" in payload["message"]


def test_ti_010_install_template_batch_partial_install(client):
    """Test batch template installation (partial items) success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/templates/install",
            json={
                "templateId": "test-template-id",
                "templateName": "test-template",
                "cliType": "codex",
                "slashCommands": [
                    {"fileName": "test.md", "content": "# Test\nContent"}
                ],
                "scripts": [
                    {
                        "path": "setup.sh",
                        "content": "#!/bin/bash\necho 'setup'",
                        "executable": True,
                    }
                ],
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["results"]["slashCommands"] is not None
    assert payload["results"]["scripts"] is not None
    assert payload["results"]["claudeMd"] is None
    assert payload["results"]["subagents"] is None
    assert service.last_slash_command_request is not None
    assert service.last_slash_command_request.cliType == "codex"


def test_ti_011_install_template_compiled_plan_success(client):
    """Test batch template installation (compiled install plan) success"""
    service = TemplateInstallServiceStub()

    with override_dependency(
        verify_internal_token, _allow_internal_token
    ), override_dependency(get_template_install_service, lambda: service):
        response = client.post(
            "/api/v1/internal/workspaces/test-workspace/templates/install",
            json={
                "templateId": "test-template-id",
                "templateName": "test-template",
                "cliType": "codex",
                "installPlan": {
                    "target": "codex",
                    "files": [
                        {"path": "AGENTS.md", "source": "agents.md", "content": "# Agents"},
                        {
                            "path": ".codex/prompts/review.md",
                            "source": "commands/review.md",
                            "content": "# Review",
                        },
                    ],
                    "installHints": {
                        "outputStyles": [{"fileName": "output-style.yaml", "content": "Keep answers concise."}],
                        "mcpServers": {"test-server": {"type": "stdio", "command": "node", "args": []}},
                        "skills": [{"path": "review/SKILL.md", "content": "# Skill"}],
                    },
                },
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["results"]["claudeMd"] is not None
    assert payload["results"]["slashCommands"] is not None
    assert payload["results"]["outputStyles"] is not None
    assert payload["results"]["mcp"] is not None
    assert payload["results"]["skills"] is not None
