"""TemplateInstallService 單元測試"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.db.models import Template as TemplateDB, Workspace
from app.services.template_install_service import TemplateInstallService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock 資料庫 Session"""
    session = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_template_db():
    """範例模板資料庫模型"""
    return TemplateDB(
        id="test-template",
        name="Test Template",
        description="A test template",
        author_name="Test Author",
        author_email="test@example.com",
        author_url="https://example.com",
        category="general",
        version="1.0.0",
        cli_type="claude-code",
        status="active",
        keywords=["test"],
        init_commands=["echo 'Hello'"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_workspace():
    """範例 Workspace 模型"""
    workspace = MagicMock(spec=Workspace)
    workspace.id = "workspace-123"
    workspace.name = "Test Workspace"
    workspace.runtime_status = "running"
    workspace.runtime_internal_url = "http://runtime-internal:8080"
    workspace.runtime_external_url = "http://localhost:8080"
    return workspace


@pytest.fixture
def install_service(mock_db_session):
    """TemplateInstallService 實例"""
    with patch('app.services.template_install_service.get_settings') as mock_settings:
        mock_settings.return_value.INTERNAL_API_TOKEN = "test-token"
        service = TemplateInstallService(mock_db_session)
        return service


# ============================================================================
# Installation Tests
# ============================================================================

@pytest.mark.unit
class TestInstallation:
    """模板安裝測試"""

    @pytest.mark.asyncio
    async def test_install_template_success(
        self,
        install_service,
        mock_db_session,
        mock_template_db,
        mock_workspace
    ):
        """測試：安裝模板成功"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        with patch.object(install_service.template_service, '_get_template') as mock_get_template, \
             patch.object(install_service, '_prepare_install_payload') as mock_prepare, \
             patch.object(install_service, '_call_runtime_install_api') as mock_call_api:

            mock_get_template.return_value = mock_template_db
            mock_prepare.return_value = {"templateId": "test-template"}
            mock_call_api.return_value = {"success": True}

            # Act
            result = await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )

            # Assert
            assert result["success"] is True
            mock_call_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_template_workspace_not_found(self, install_service, mock_db_session):
        """測試：Workspace 不存在時安裝失敗"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(ValueError, match="Workspace .* not found"):
            await install_service.install_template_to_workspace(
                "nonexistent-workspace",
                "test-template"
            )

    @pytest.mark.asyncio
    async def test_install_template_workspace_not_running(
        self,
        install_service,
        mock_db_session,
        mock_workspace
    ):
        """測試：Workspace 未運行時安裝失敗"""
        # Arrange
        mock_workspace.runtime_status = "stopped"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(ValueError, match="is not running"):
            await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )

    @pytest.mark.asyncio
    async def test_install_template_template_not_found(
        self,
        install_service,
        mock_db_session,
        mock_workspace
    ):
        """測試：Template 不存在時安裝失敗"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        with patch.object(install_service.template_service, '_get_template') as mock_get_template:
            mock_get_template.return_value = None

            # Act & Assert
            with pytest.raises(ValueError, match="Template .* not found"):
                await install_service.install_template_to_workspace(
                    "workspace-123",
                    "nonexistent-template"
                )


# ============================================================================
# Payload Preparation Tests
# ============================================================================

@pytest.mark.unit
class TestPayloadPreparation:
    """安裝資料準備測試"""

    @pytest.mark.asyncio
    async def test_prepare_install_payload_basic(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備基本安裝資料"""
        # Arrange
        with patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch.object(install_service.template_service.file_service, 'load_skills') as mock_skills:

            mock_claude_md.return_value = None
            mock_commands.return_value = []
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = []
            mock_hooks.return_value = []
            mock_files.return_value = []
            mock_skills.return_value = []

            # Act
            result = await install_service._prepare_install_payload(mock_template_db)

            # Assert
            assert result["templateId"] == "test-template"
            assert result["templateName"] == "Test Template"
            assert result["cliType"] == "claude-code"
            assert result["initCommands"] == ["echo 'Hello'"]

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_claude_md(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 Claude.md 的安裝資料"""
        # Arrange
        with patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch.object(install_service.template_service.file_service, 'load_skills') as mock_skills:

            mock_claude_md.return_value = "# Claude.md content"
            mock_commands.return_value = []
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = []
            mock_hooks.return_value = []
            mock_files.return_value = []
            mock_skills.return_value = []

            # Act
            result = await install_service._prepare_install_payload(mock_template_db)

            # Assert
            assert "claudeMd" in result
            assert result["claudeMd"]["content"] == "# Claude.md content"

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_commands(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 Slash Commands 的安裝資料"""
        # Arrange
        mock_command = MagicMock()
        mock_command.fileName = "test-command"
        mock_command.content = "Command content"

        with patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch.object(install_service.template_service.file_service, 'load_skills') as mock_skills:

            mock_claude_md.return_value = None
            mock_commands.return_value = [mock_command]
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = []
            mock_hooks.return_value = []
            mock_files.return_value = []
            mock_skills.return_value = []

            # Act
            result = await install_service._prepare_install_payload(mock_template_db)

            # Assert
            assert "slashCommands" in result
            assert len(result["slashCommands"]) == 1
            assert result["slashCommands"][0]["fileName"] == "test-command.md"
            assert result["slashCommands"][0]["content"] == "Command content"

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_mcp_servers(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 MCP Servers 的安裝資料"""
        # Arrange
        mock_server = MagicMock()
        mock_server.name = "test-mcp"
        mock_server.type = "stdio"
        mock_server.command = "python"
        mock_server.args = ["-m", "test"]
        mock_server.env = {"KEY": "value"}
        mock_server.url = None
        mock_server.headers = None

        with patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch.object(install_service.template_service.file_service, 'load_skills') as mock_skills:

            mock_claude_md.return_value = None
            mock_commands.return_value = []
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = [mock_server]
            mock_hooks.return_value = []
            mock_files.return_value = []
            mock_skills.return_value = []

            # Act
            result = await install_service._prepare_install_payload(mock_template_db)

            # Assert
            assert "mcpServers" in result
            assert "test-mcp" in result["mcpServers"]
            assert result["mcpServers"]["test-mcp"]["type"] == "stdio"
            assert result["mcpServers"]["test-mcp"]["command"] == "python"

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_skills(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 Skills 的安裝資料"""
        mock_skill = MagicMock()
        mock_skill.type = "file"
        mock_skill.path = "openspec-ff-change/SKILL.md"
        mock_skill.content = "# Skill"

        with patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch.object(install_service.template_service.file_service, 'load_skills') as mock_skills:

            mock_claude_md.return_value = None
            mock_commands.return_value = []
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = []
            mock_hooks.return_value = []
            mock_files.return_value = []
            mock_skills.return_value = [mock_skill]

            result = await install_service._prepare_install_payload(mock_template_db)

            assert result["skills"] == [{
                "path": "openspec-ff-change/SKILL.md",
                "content": "# Skill",
            }]


# ============================================================================
# Runtime API Call Tests
# ============================================================================

@pytest.mark.unit
class TestRuntimeAPICall:
    """Runtime API 呼叫測試"""

    @pytest.mark.asyncio
    async def test_call_runtime_install_api_success(self, install_service, mock_workspace):
        """測試：呼叫 Runtime API 成功"""
        # Arrange
        runtime_url = "http://runtime:8080"
        workspace_id = "workspace-123"
        payload = {"templateId": "test-template"}

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        with patch('app.services.template_install_service.httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            # Act
            result = await install_service._call_runtime_install_api(
                runtime_url,
                workspace_id,
                payload
            )

            # Assert
            assert result["success"] is True
            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_runtime_install_api_http_error(self, install_service):
        """測試：Runtime API 返回 HTTP 錯誤"""
        # Arrange
        runtime_url = "http://runtime:8080"
        workspace_id = "workspace-123"
        payload = {"templateId": "test-template"}

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch('app.services.template_install_service.httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error",
                    request=MagicMock(),
                    response=mock_response
                )
            )
            mock_client.return_value = mock_client_instance

            # Act & Assert
            with pytest.raises(Exception, match="Failed to install template"):
                await install_service._call_runtime_install_api(
                    runtime_url,
                    workspace_id,
                    payload
                )

    @pytest.mark.asyncio
    async def test_call_runtime_install_api_connection_error(self, install_service):
        """測試：Runtime API 連接失敗"""
        # Arrange
        runtime_url = "http://runtime:8080"
        workspace_id = "workspace-123"
        payload = {"templateId": "test-template"}

        with patch('app.services.template_install_service.httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed", request=MagicMock())
            )
            mock_client.return_value = mock_client_instance

            # Act & Assert
            with pytest.raises(Exception, match="Failed to connect to runtime"):
                await install_service._call_runtime_install_api(
                    runtime_url,
                    workspace_id,
                    payload
                )


# ============================================================================
# Workspace Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestWorkspaceRetrieval:
    """Workspace 檢索測試"""

    def test_get_workspace_success(self, install_service, mock_db_session, mock_workspace):
        """測試：取得 Workspace 成功"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        # Act
        result = install_service._get_workspace("workspace-123")

        # Assert
        assert result == mock_workspace

    def test_get_workspace_not_found(self, install_service, mock_db_session):
        """測試：Workspace 不存在返回 None"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act
        result = install_service._get_workspace("nonexistent-workspace")

        # Assert
        assert result is None


# ============================================================================
# Runtime URL Tests
# ============================================================================

@pytest.mark.unit
class TestRuntimeURL:
    """Runtime URL 測試"""

    def test_get_runtime_url_external_in_dev(self, install_service, mock_workspace):
        """測試：開發模式使用外部 URL"""
        # Arrange
        with patch('os.path.exists', return_value=False):  # 不在容器中

            # Act
            result = install_service._get_runtime_url(mock_workspace)

            # Assert
            assert result == "http://localhost:8080"

    def test_get_runtime_url_internal_in_container(self, install_service, mock_workspace):
        """測試：容器模式使用內部 URL"""
        # Arrange
        with patch('os.path.exists', return_value=True):  # 在容器中

            # Act
            result = install_service._get_runtime_url(mock_workspace)

            # Assert
            assert result == "http://runtime-internal:8080"

    def test_get_runtime_url_no_url(self, install_service, mock_workspace):
        """測試：無 Runtime URL 拋出異常"""
        # Arrange
        mock_workspace.runtime_internal_url = None
        mock_workspace.runtime_external_url = None

        with patch('os.path.exists', return_value=False):

            # Act & Assert
            with pytest.raises(ValueError, match="has no runtime URL"):
                install_service._get_runtime_url(mock_workspace)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.unit
class TestIntegration:
    """整合測試"""

    @pytest.mark.asyncio
    async def test_full_installation_flow(
        self,
        install_service,
        mock_db_session,
        mock_template_db,
        mock_workspace
    ):
        """測試：完整安裝流程"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Template installed successfully"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(install_service.template_service, '_get_template') as mock_get_template, \
             patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch('app.services.template_install_service.httpx.AsyncClient') as mock_client, \
             patch('os.path.exists', return_value=False):

            mock_get_template.return_value = mock_template_db
            mock_claude_md.return_value = "# Template"
            mock_commands.return_value = []
            mock_agents.return_value = []
            mock_styles.return_value = []
            mock_mcp.return_value = []
            mock_hooks.return_value = []
            mock_files.return_value = []

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            # Act
            result = await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )

            # Assert
            assert result["success"] is True
            assert "installed successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_installation_with_all_components(
        self,
        install_service,
        mock_db_session,
        mock_template_db,
        mock_workspace
    ):
        """測試：安裝包含所有組件的模板"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        # 建立各種 mock 組件
        mock_command = MagicMock()
        mock_command.fileName = "cmd"
        mock_command.content = "content"

        mock_agent = MagicMock()
        mock_agent.fileName = "agent"
        mock_agent.content = "content"

        mock_style = MagicMock()
        mock_style.fileName = "style"
        mock_style.content = "content"

        mock_server = MagicMock()
        mock_server.name = "mcp"
        mock_server.type = "stdio"
        mock_server.command = "python"
        mock_server.args = []
        mock_server.env = {}
        mock_server.url = None
        mock_server.headers = None

        mock_hook = MagicMock()
        mock_hook.event = "before_chat"
        mock_hook.matcher = "*"
        mock_hook.action = "exec"
        mock_hook.command = "echo"
        mock_hook.timeout = 30

        mock_file = MagicMock()
        mock_file.type = "file"
        mock_file.path = "script.py"
        mock_file.content = "print('hello')"

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        with patch.object(install_service.template_service, '_get_template') as mock_get_template, \
             patch.object(install_service.template_service, 'get_claude_md') as mock_claude_md, \
             patch.object(install_service.template_service, '_load_commands') as mock_commands, \
             patch.object(install_service.template_service, '_load_agents') as mock_agents, \
             patch.object(install_service.template_service, '_load_output_styles') as mock_styles, \
             patch.object(install_service.template_service, '_load_mcp_servers') as mock_mcp, \
             patch.object(install_service.template_service, '_load_hooks') as mock_hooks, \
             patch.object(install_service.template_service, '_load_files') as mock_files, \
             patch('app.services.template_install_service.httpx.AsyncClient') as mock_client, \
             patch('os.path.exists', return_value=False):

            mock_get_template.return_value = mock_template_db
            mock_claude_md.return_value = "# Claude.md"
            mock_commands.return_value = [mock_command]
            mock_agents.return_value = [mock_agent]
            mock_styles.return_value = [mock_style]
            mock_mcp.return_value = [mock_server]
            mock_hooks.return_value = [mock_hook]
            mock_files.return_value = [mock_file]

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            # Act
            result = await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )

            # Assert
            assert result["success"] is True

            # 驗證 API 被呼叫，並且 payload 包含所有組件
            call_args = mock_client_instance.post.call_args
            assert call_args is not None
            payload = call_args[1]["json"]
            assert "claudeMd" in payload
            assert "slashCommands" in payload
            assert "subagents" in payload
            assert "outputStyles" in payload
            assert "mcpServers" in payload
            assert "hooks" in payload
            assert "scripts" in payload
