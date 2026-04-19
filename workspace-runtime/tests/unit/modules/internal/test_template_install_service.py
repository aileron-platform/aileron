"""Tests for app/modules/internal/template_install_service.py"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import asyncio

from app.modules.internal.template_install_service import TemplateInstallService
from app.modules.internal.template_install_models import (
    SlashCommandInstallRequest,
    SlashCommandInstallItem,
    SubagentInstallRequest,
    SubagentInstallItem,
    OutputStyleInstallRequest,
    OutputStyleInstallItem,
    ClaudeMdInstallRequest,
    McpInstallRequest,
    McpServerConfigInstall,
    HooksInstallRequest,
    HookRuleInstall,
    HookActionInstall,
    ScriptsInstallRequest,
    ScriptFileItem,
    SkillsInstallRequest,
    SkillFileItem,
    InstallResults,
)
from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.mcp.models import McpImportResponse
from app.modules.claude_code.hooks.models import HookImportResponse
from app.modules.claude_code.claude_md.models import ClaudeMdScope


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir) / "home"
        claude_dir = home_dir / ".claude"
        scripts_dir = Path(tmpdir) / "scripts"

        home_dir.mkdir(parents=True)
        claude_dir.mkdir(parents=True)
        scripts_dir.mkdir(parents=True)

        yield {
            "home_dir": home_dir,
            "claude_dir": claude_dir,
            "scripts_dir": scripts_dir,
        }


@pytest.fixture
def mock_services():
    """Create mock services"""
    return {
        "mcp_service": MagicMock(),
        "hook_service": MagicMock(),
        "claude_md_service": MagicMock(),
    }


@pytest.fixture
def service(temp_dirs, mock_services):
    """Create TemplateInstallService with mocked dependencies"""
    with patch.dict("os.environ", {"HOME": str(temp_dirs["home_dir"])}):
        service = TemplateInstallService(
            mcp_service=mock_services["mcp_service"],
            hook_service=mock_services["hook_service"],
            claude_md_service=mock_services["claude_md_service"],
        )
        # Override directories to use temp dirs
        service.claude_dir = temp_dirs["claude_dir"]
        service.scripts_base_dir = temp_dirs["scripts_dir"]
        return service


class TestServiceInitialization:
    """Test TemplateInstallService initialization"""

    def test_init_with_provided_services(self, mock_services, temp_dirs):
        """Test initialization with provided services"""
        with patch.dict("os.environ", {"HOME": str(temp_dirs["home_dir"])}):
            service = TemplateInstallService(**mock_services)

            assert service.mcp_service == mock_services["mcp_service"]
            assert service.hook_service == mock_services["hook_service"]
            assert service.claude_md_service == mock_services["claude_md_service"]

    def test_init_with_default_services(self, temp_dirs):
        """Test initialization with default services"""
        with patch.dict("os.environ", {"HOME": str(temp_dirs["home_dir"])}):
            service = TemplateInstallService()

            assert service.mcp_service is not None
            assert service.hook_service is not None
            assert service.claude_md_service is not None

    def test_init_creates_directories(self, temp_dirs):
        """Test that initialization creates required directories"""
        with patch.dict("os.environ", {"HOME": str(temp_dirs["home_dir"])}):
            service = TemplateInstallService()

            assert service.claude_dir.exists()
            assert service.scripts_base_dir.exists()

    def test_init_with_scripts_env_var(self, temp_dirs):
        """Test initialization with SCRIPTS_DIR environment variable"""
        scripts_dir = temp_dirs["scripts_dir"]
        with patch.dict("os.environ", {
            "HOME": str(temp_dirs["home_dir"]),
            "SCRIPTS_DIR": str(scripts_dir)
        }):
            service = TemplateInstallService()

            assert service.scripts_base_dir == scripts_dir

    def test_init_with_nonexistent_scripts_mount(self, temp_dirs):
        """Test initialization when /scripts mount point does not exist"""
        with patch.dict("os.environ", {"HOME": str(temp_dirs["home_dir"])}):
            with patch("pathlib.Path.exists", return_value=False):
                service = TemplateInstallService()
                # Should use home directory for scripts
                assert service.scripts_base_dir == temp_dirs["home_dir"] / "scripts"


class TestSlashCommandsInstallation:
    """Test slash commands installation"""

    @pytest.mark.asyncio
    async def test_install_single_slash_command(self, service):
        """Test installing a single slash command"""
        request = SlashCommandInstallRequest(
            commands=[
                SlashCommandInstallItem(
                    fileName="test-command.md",
                    content="# Test Command\n\nThis is a test."
                )
            ]
        )

        success, results = await service.install_slash_commands("workspace-1", request)

        assert success is True
        assert len(results.created) == 1
        assert results.created[0] == "test-command.md"
        assert len(results.failed) == 0

        # Verify file was created
        command_file = service.claude_dir / "commands" / "test-command.md"
        assert command_file.exists()
        assert command_file.read_text() == "# Test Command\n\nThis is a test."

    @pytest.mark.asyncio
    async def test_install_slash_command_with_namespace(self, service):
        """Test installing slash command with namespace (subdirectory)"""
        request = SlashCommandInstallRequest(
            commands=[
                SlashCommandInstallItem(
                    fileName="deploy/build.md",
                    content="# Build Command"
                )
            ]
        )

        success, results = await service.install_slash_commands("workspace-1", request)

        assert success is True
        assert results.created[0] == "deploy/build.md"

        # Verify file was created in subdirectory
        command_file = service.claude_dir / "commands" / "deploy" / "build.md"
        assert command_file.exists()
        assert command_file.parent.name == "deploy"

    @pytest.mark.asyncio
    async def test_update_existing_slash_command(self, service):
        """Test updating an existing slash command"""
        # Create initial command
        commands_dir = service.claude_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        existing_file = commands_dir / "existing.md"
        existing_file.write_text("Old content")

        request = SlashCommandInstallRequest(
            commands=[
                SlashCommandInstallItem(
                    fileName="existing.md",
                    content="New content"
                )
            ]
        )

        success, results = await service.install_slash_commands("workspace-1", request)

        assert success is True
        assert len(results.updated) == 1
        assert results.updated[0] == "existing.md"
        assert len(results.created) == 0
        assert existing_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_install_multiple_slash_commands(self, service):
        """Test installing multiple slash commands"""
        request = SlashCommandInstallRequest(
            commands=[
                SlashCommandInstallItem(fileName="cmd1.md", content="Content 1"),
                SlashCommandInstallItem(fileName="cmd2.md", content="Content 2"),
                SlashCommandInstallItem(fileName="ns/cmd3.md", content="Content 3"),
            ]
        )

        success, results = await service.install_slash_commands("workspace-1", request)

        assert success is True
        assert len(results.created) == 3
        assert len(results.failed) == 0


class TestSubagentsInstallation:
    """Test subagents installation"""

    @pytest.mark.asyncio
    async def test_install_single_subagent(self, service):
        """Test installing a single subagent"""
        request = SubagentInstallRequest(
            subagents=[
                SubagentInstallItem(
                    fileName="test-agent.md",
                    content="# Test Agent\n\nAgent instructions."
                )
            ]
        )

        success, results = await service.install_subagents("workspace-1", request)

        assert success is True
        assert len(results.created) == 1
        assert results.created[0] == "test-agent.md"

        # Verify file was created in correct location
        agent_file = service.claude_dir / "agents" / "user" / "test-agent.md"
        assert agent_file.exists()
        assert agent_file.read_text() == "# Test Agent\n\nAgent instructions."

    @pytest.mark.asyncio
    async def test_update_existing_subagent(self, service):
        """Test updating an existing subagent"""
        # Create initial subagent
        agents_dir = service.claude_dir / "agents" / "user"
        agents_dir.mkdir(parents=True, exist_ok=True)
        existing_file = agents_dir / "existing-agent.md"
        existing_file.write_text("Old instructions")

        request = SubagentInstallRequest(
            subagents=[
                SubagentInstallItem(
                    fileName="existing-agent.md",
                    content="New instructions"
                )
            ]
        )

        success, results = await service.install_subagents("workspace-1", request)

        assert success is True
        assert len(results.updated) == 1
        assert results.updated[0] == "existing-agent.md"
        assert existing_file.read_text() == "New instructions"

    @pytest.mark.asyncio
    async def test_install_multiple_subagents(self, service):
        """Test installing multiple subagents"""
        request = SubagentInstallRequest(
            subagents=[
                SubagentInstallItem(fileName="agent1.md", content="Agent 1"),
                SubagentInstallItem(fileName="agent2.md", content="Agent 2"),
            ]
        )

        success, results = await service.install_subagents("workspace-1", request)

        assert success is True
        assert len(results.created) == 2


class TestOutputStylesInstallation:
    """Test output styles installation"""

    @pytest.mark.asyncio
    async def test_install_single_output_style(self, service):
        """Test installing a single output style"""
        request = OutputStyleInstallRequest(
            outputStyles=[
                OutputStyleInstallItem(
                    fileName="custom-style.md",
                    content="# Custom Style\n\nStyle instructions."
                )
            ]
        )

        success, results = await service.install_output_styles("workspace-1", request)

        assert success is True
        assert len(results.created) == 1
        assert results.created[0] == "custom-style.md"

        # Verify file was created
        style_file = service.claude_dir / "output-styles" / "custom-style.md"
        assert style_file.exists()
        assert style_file.read_text() == "# Custom Style\n\nStyle instructions."

    @pytest.mark.asyncio
    async def test_update_existing_output_style(self, service):
        """Test updating an existing output style"""
        # Create initial style
        styles_dir = service.claude_dir / "output-styles"
        styles_dir.mkdir(parents=True, exist_ok=True)
        existing_file = styles_dir / "existing-style.md"
        existing_file.write_text("Old style")

        request = OutputStyleInstallRequest(
            outputStyles=[
                OutputStyleInstallItem(
                    fileName="existing-style.md",
                    content="New style"
                )
            ]
        )

        success, results = await service.install_output_styles("workspace-1", request)

        assert success is True
        assert len(results.updated) == 1
        assert existing_file.read_text() == "New style"


class TestClaudeMdInstallation:
    """Test Claude.md installation"""

    @pytest.mark.asyncio
    async def test_install_claude_md(self, service, mock_services):
        """Test installing Claude.md"""
        request = ClaudeMdInstallRequest(content="# Project Instructions\n\nTest content.")

        success = await service.install_claude_md("workspace-1", request)

        assert success is True
        mock_services["claude_md_service"].update_document.assert_called_once()

        # Verify the call arguments
        call_args = mock_services["claude_md_service"].update_document.call_args
        assert call_args[0][0] == "workspace-1"
        update_request = call_args[0][1]
        assert update_request.scope == ClaudeMdScope.USER
        assert update_request.content == "# Project Instructions\n\nTest content."

    @pytest.mark.asyncio
    async def test_install_claude_md_handles_error(self, service, mock_services):
        """Test Claude.md installation handles errors"""
        mock_services["claude_md_service"].update_document.side_effect = Exception(
            "Service error"
        )

        request = ClaudeMdInstallRequest(content="Test content")
        success = await service.install_claude_md("workspace-1", request)

        assert success is False


class TestMcpServersInstallation:
    """Test MCP servers installation"""

    @pytest.mark.asyncio
    async def test_install_mcp_servers(self, service, mock_services):
        """Test installing MCP servers"""
        from app.modules.claude_code.common import DocumentScope
        mock_services["mcp_service"].import_servers.return_value = McpImportResponse(
            workspaceId="workspace-1",
            scope=DocumentScope.USER,
            created=["server1"],
            updated=[],
            skipped=[]
        )

        request = McpInstallRequest(
            mcpServers={
                "server1": McpServerConfigInstall(
                    type="stdio",
                    command="node",
                    args=["server.js"],
                )
            }
        )

        success, results = await service.install_mcp_servers("workspace-1", request)

        assert success is True
        assert results.created == ["server1"]
        mock_services["mcp_service"].import_servers.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_mcp_servers_handles_error(self, service, mock_services):
        """Test MCP servers installation handles errors"""
        mock_services["mcp_service"].import_servers.side_effect = Exception("Import error")

        request = McpInstallRequest(
            mcpServers={
                "server1": McpServerConfigInstall(type="stdio", command="node")
            }
        )

        success, results = await service.install_mcp_servers("workspace-1", request)

        assert success is False
        assert results.failed == ["server1"]


class TestHooksInstallation:
    """Test hooks installation"""

    @pytest.mark.asyncio
    async def test_install_hooks(self, service, mock_services):
        """Test installing hooks"""
        from app.modules.claude_code.hooks.models import HookImportMode
        mock_services["hook_service"].import_scopes.return_value = HookImportResponse(
            workspaceId="workspace-1",
            mode=HookImportMode.REPLACE,
            imported=1,
            updated=0,
            skipped=0
        )

        request = HooksInstallRequest(
            hooks={
                "user-prompt-submit": [
                    HookRuleInstall(
                        matcher="*",
                        hooks=[
                            HookActionInstall(
                                type="command",
                                command="echo 'test'",
                                timeout=30
                            )
                        ]
                    )
                ]
            }
        )

        success, results = await service.install_hooks("workspace-1", request)

        assert success is True
        mock_services["hook_service"].import_scopes.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_hooks_handles_error(self, service, mock_services):
        """Test hooks installation handles errors"""
        mock_services["hook_service"].import_scopes.side_effect = Exception("Import error")

        request = HooksInstallRequest(
            hooks={
                "event1": [
                    HookRuleInstall(
                        matcher="*",
                        hooks=[HookActionInstall(type="command", command="test")]
                    )
                ]
            }
        )

        success, results = await service.install_hooks("workspace-1", request)

        assert success is False
        assert results.failed == ["event1"]


class TestScriptsInstallation:
    """Test scripts installation"""

    @pytest.mark.asyncio
    async def test_install_scripts(self, service):
        """Test installing scripts"""
        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="setup.sh",
                    content="#!/bin/bash\necho 'Setup'",
                    executable=True
                ),
                ScriptFileItem(
                    path="config.json",
                    content='{"key": "value"}',
                    executable=False
                )
            ]
        )

        success, results, target_path, total_size = await service.install_scripts(
            "workspace-1", request
        )

        assert success is True
        assert len(results.created) == 2
        assert "setup.sh" in results.created
        assert "config.json" in results.created
        assert total_size > 0

        # Verify files were created
        template_dir = service.scripts_base_dir / "my-template"
        assert (template_dir / "setup.sh").exists()
        assert (template_dir / "config.json").exists()

        # Verify executable permissions
        setup_file = template_dir / "setup.sh"
        assert oct(setup_file.stat().st_mode)[-3:] == "755"

    @pytest.mark.asyncio
    async def test_install_scripts_with_subdirectories(self, service):
        """Test installing scripts with subdirectories"""
        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="src/main.py",
                    content="print('hello')",
                    executable=True
                )
            ]
        )

        success, results, target_path, total_size = await service.install_scripts(
            "workspace-1", request
        )

        assert success is True
        script_file = service.scripts_base_dir / "my-template" / "src" / "main.py"
        assert script_file.exists()

    @pytest.mark.asyncio
    async def test_install_scripts_rejects_path_traversal(self, service):
        """Test that script installation rejects path traversal attempts"""
        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="../../../etc/passwd",
                    content="malicious",
                    executable=False
                )
            ]
        )

        success, results, target_path, total_size = await service.install_scripts(
            "workspace-1", request
        )

        assert success is False
        assert len(results.failed) == 1
        assert results.failed[0] == "../../../etc/passwd"

    @pytest.mark.asyncio
    async def test_install_scripts_rejects_absolute_paths(self, service):
        """Test that script installation rejects absolute paths"""
        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="/etc/passwd",
                    content="malicious",
                    executable=False
                )
            ]
        )

        success, results, target_path, total_size = await service.install_scripts(
            "workspace-1", request
        )

        assert success is False
        assert len(results.failed) == 1


class TestSkillsInstallation:
    """Test skills installation"""

    @pytest.mark.asyncio
    async def test_install_codex_skills_to_project_scope(self, service):
        """Test installing Codex skills into the Codex project skills directory"""
        request = SkillsInstallRequest(
            cliType="codex",
            skills=[
                SkillFileItem(
                    path="openspec-ff-change/SKILL.md",
                    content="# Skill",
                )
            ],
        )

        with patch("app.modules.internal.template_install_service.get_workspace_path", return_value=str(service.scripts_base_dir.parent / "workspace")):
            success, results, target_path, total_size = await service.install_skills(
                "workspace-1", request
            )

        assert success is True
        assert results.created == ["openspec-ff-change/SKILL.md"]
        assert target_path.endswith("/workspace/.codex/skills")
        assert total_size == len("# Skill".encode("utf-8"))
        skill_file = Path(target_path) / "openspec-ff-change" / "SKILL.md"
        assert skill_file.exists()
        assert skill_file.read_text() == "# Skill"

    @pytest.mark.asyncio
    async def test_install_skills_rejects_path_traversal(self, service):
        """Test that skill installation rejects invalid paths"""
        request = SkillsInstallRequest(
            cliType="claude-code",
            skills=[SkillFileItem(path="../bad.md", content="bad")],
        )

        with patch("app.modules.internal.template_install_service.get_workspace_path", return_value=str(service.scripts_base_dir.parent / "workspace")):
            success, results, _, _ = await service.install_skills("workspace-1", request)

        assert success is False
        assert results.failed == ["../bad.md"]


class TestInitCommandsExecution:
    """Test init commands execution"""

    @pytest.mark.asyncio
    async def test_execute_init_commands_success(self, service):
        """Test successful init commands execution"""
        # 完全 mock 掉 subprocess
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"Hello World\nTest", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            init_commands = "echo 'Hello World'\necho 'Test'"
            success, stdout, stderr = await service.execute_init_commands(
                "workspace-1", init_commands
            )

            assert success is True
            assert "Hello World" in stdout
            assert "Test" in stdout

    @pytest.mark.asyncio
    async def test_execute_empty_init_commands(self, service):
        """Test executing empty init commands"""
        # Mock subprocess to avoid actual execution
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            success, stdout, stderr = await service.execute_init_commands(
                "workspace-1", ""
            )

            assert success is True
            assert stdout == ""
            assert stderr == ""

    @pytest.mark.asyncio
    async def test_execute_init_commands_failure(self, service):
        """Test init commands execution failure"""
        # Mock subprocess to simulate failure
        with patch("asyncio.create_subprocess_shell") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error occurred")
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            init_commands = "exit 1"

            success, stdout, stderr = await service.execute_init_commands(
                "workspace-1", init_commands
            )

            assert success is False

    @pytest.mark.asyncio
    async def test_execute_init_commands_timeout(self, service):
        """Test init commands execution timeout"""
        # Mock both subprocess and wait_for to avoid real execution
        with patch("asyncio.create_subprocess_shell") as mock_subprocess, \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):

            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            init_commands = "sleep 1000"

            success, stdout, stderr = await service.execute_init_commands(
                "workspace-1", init_commands
            )

            assert success is False
            assert "超時" in stderr

    @pytest.mark.asyncio
    async def test_execute_init_commands_exception(self, service):
        """Test init commands execution handles exceptions"""
        # Create a mock process that raises exception
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = Exception("Process error")
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            init_commands = "echo test"

            success, stdout, stderr = await service.execute_init_commands(
                "workspace-1", init_commands
            )

            assert success is False
            assert "發生錯誤" in stderr


class TestServiceInitializationEdgeCases:
    """Test TemplateInstallService initialization edge cases"""

    def test_init_with_scripts_dir_env(self, temp_dirs, mock_services):
        """Test initialization with SCRIPTS_DIR environment variable"""
        scripts_dir = temp_dirs["scripts_dir"]
        with patch.dict("os.environ", {
            "HOME": str(temp_dirs["home_dir"]),
            "SCRIPTS_DIR": str(scripts_dir)
        }):
            service = TemplateInstallService(**mock_services)

            # Should use SCRIPTS_DIR from environment
            assert service.scripts_base_dir == scripts_dir


class TestSlashCommandsInstallationEdgeCases:
    """Test slash commands installation edge cases"""

    @pytest.mark.asyncio
    async def test_install_slash_command_with_exception(self, service):
        """Test slash command installation with exception"""
        request = SlashCommandInstallRequest(
            commands=[
                SlashCommandInstallItem(
                    fileName="test-command.md",
                    content="# Test"
                )
            ]
        )

        # Mock write_text to raise exception
        with patch.object(Path, "write_text", side_effect=PermissionError("Cannot write")):
            success, results = await service.install_slash_commands("workspace-1", request)

            assert success is False
            assert len(results.failed) == 1
            assert results.failed[0] == "test-command.md"


class TestSubagentsInstallationEdgeCases:
    """Test subagents installation edge cases"""

    @pytest.mark.asyncio
    async def test_install_subagent_with_exception(self, service):
        """Test subagent installation with exception"""
        request = SubagentInstallRequest(
            subagents=[
                SubagentInstallItem(
                    fileName="test-agent.md",
                    content="# Agent"
                )
            ]
        )

        # Mock write_text to raise exception
        with patch.object(Path, "write_text", side_effect=OSError("Disk full")):
            success, results = await service.install_subagents("workspace-1", request)

            assert success is False
            assert len(results.failed) == 1
            assert results.failed[0] == "test-agent.md"


class TestOutputStylesInstallationEdgeCases:
    """Test output styles installation edge cases"""

    @pytest.mark.asyncio
    async def test_install_output_style_with_exception(self, service):
        """Test output style installation with exception"""
        request = OutputStyleInstallRequest(
            outputStyles=[
                OutputStyleInstallItem(
                    fileName="test-style.md",
                    content="# Style"
                )
            ]
        )

        # Mock write_text to raise exception
        with patch.object(Path, "write_text", side_effect=IOError("Write error")):
            success, results = await service.install_output_styles("workspace-1", request)

            assert success is False
            assert len(results.failed) == 1
            assert results.failed[0] == "test-style.md"


class TestHooksInstallationEdgeCases:
    """Test hooks installation edge cases"""

    @pytest.mark.asyncio
    async def test_install_hooks_with_updated_count(self, service, mock_services):
        """Test installing hooks with updated count > 0"""
        from app.modules.claude_code.hooks.models import HookImportMode
        mock_services["hook_service"].import_scopes.return_value = HookImportResponse(
            workspaceId="workspace-1",
            mode=HookImportMode.REPLACE,
            imported=0,
            updated=2,
            skipped=0
        )

        request = HooksInstallRequest(
            hooks={
                "user-prompt-submit": [
                    HookRuleInstall(
                        matcher="*",
                        hooks=[
                            HookActionInstall(
                                type="command",
                                command="echo 'test'",
                                timeout=30
                            )
                        ]
                    )
                ]
            }
        )

        success, results = await service.install_hooks("workspace-1", request)

        assert success is True
        assert len(results.updated) == 2


class TestScriptsInstallationEdgeCases:
    """Test scripts installation edge cases"""

    @pytest.mark.asyncio
    async def test_install_scripts_update_existing(self, service):
        """Test updating existing scripts"""
        # Create initial script
        template_dir = service.scripts_base_dir / "my-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        existing_script = template_dir / "setup.sh"
        existing_script.write_text("#!/bin/bash\necho 'old'")

        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="setup.sh",
                    content="#!/bin/bash\necho 'new'",
                    executable=True
                )
            ]
        )

        success, results, target_path, total_size = await service.install_scripts(
            "workspace-1", request
        )

        assert success is True
        assert len(results.updated) == 1
        assert results.updated[0] == "setup.sh"
        assert existing_script.read_text() == "#!/bin/bash\necho 'new'"

    @pytest.mark.asyncio
    async def test_install_scripts_with_exception(self, service):
        """Test script installation with exception"""
        request = ScriptsInstallRequest(
            templateName="my-template",
            scripts=[
                ScriptFileItem(
                    path="test.sh",
                    content="#!/bin/bash",
                    executable=True
                )
            ]
        )

        # Mock write_text to raise exception
        with patch.object(Path, "write_text", side_effect=RuntimeError("Write failed")):
            success, results, target_path, total_size = await service.install_scripts(
                "workspace-1", request
            )

            assert success is False
            assert len(results.failed) == 1
            assert results.failed[0] == "test.sh"
