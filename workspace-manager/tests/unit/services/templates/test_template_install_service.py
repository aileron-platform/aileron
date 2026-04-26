"""TemplateInstallService 單元測試"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.db.models import Template as TemplateDB, Workspace
from app.models.template_canonical import CanonicalTarget, InstallPlan
from app.services.template_install_service import TemplateInstallError, TemplateInstallService


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
             patch.object(install_service, '_call_runtime_install_api') as mock_call_api, \
             patch.object(install_service.template_compiler, "compile_template") as mock_compile, \
             patch.object(install_service.artifact_cache, "record_install_manifest") as mock_record_manifest:

            mock_get_template.return_value = mock_template_db
            mock_prepare.return_value = {"templateId": "test-template"}
            mock_call_api.return_value = {"success": True}
            mock_compile.return_value = InstallPlan(target=CanonicalTarget.CLAUDE_CODE, installHints={})

            # Act
            result = await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )

            # Assert
            assert result["success"] is True
            mock_call_api.assert_called_once()
            mock_record_manifest.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_template_workspace_not_found(self, install_service, mock_db_session):
        """測試：Workspace does not exist時安裝失敗"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(TemplateInstallError, match="Workspace .* not found") as exc_info:
            await install_service.install_template_to_workspace(
                "nonexistent-workspace",
                "test-template"
            )
        assert exc_info.value.code == "TEMPLATE_INSTALL_WORKSPACE_NOT_FOUND"

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
        with pytest.raises(TemplateInstallError, match="is not running") as exc_info:
            await install_service.install_template_to_workspace(
                "workspace-123",
                "test-template"
            )
        assert exc_info.value.code == "TEMPLATE_INSTALL_WORKSPACE_NOT_RUNNING"

    @pytest.mark.asyncio
    async def test_install_template_template_not_found(
        self,
        install_service,
        mock_db_session,
        mock_workspace
    ):
        """測試：Template does not exist時安裝失敗"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_workspace
        mock_db_session.query.return_value = mock_query

        with patch.object(install_service.template_service, '_get_template') as mock_get_template:
            mock_get_template.return_value = None

            # Act & Assert
            with pytest.raises(TemplateInstallError, match="Template .* not found") as exc_info:
                await install_service.install_template_to_workspace(
                    "workspace-123",
                    "nonexistent-template"
                )
            assert exc_info.value.code == "TEMPLATE_INSTALL_TEMPLATE_NOT_FOUND"


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
        with patch.object(install_service.template_compiler, "compile_template") as mock_compile:
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                installHints={},
            )

            result = await install_service._prepare_install_payload(mock_template_db)

        assert result["templateId"] == "test-template"
        assert result["templateName"] == "Test Template"
        assert result["cliType"] == "claude-code"
        assert result["initCommands"] == ["echo 'Hello'"]
        mock_compile.assert_called_once_with("test-template", "claude-code")

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_agents_md(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 install plan 的安裝資料"""
        with patch.object(install_service.template_compiler, "compile_template") as mock_compile:
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                files=[],
                installHints={"agentsMdContent": "# AGENTS content"},
            )

            result = await install_service._prepare_install_payload(mock_template_db)

        assert "installPlan" in result
        assert result["installPlan"]["target"] == "claude-code"
        assert result["installPlan"]["installHints"]["agentsMdContent"] == "# AGENTS content"

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_commands(
        self,
        install_service,
        mock_template_db
    ):
        """測試：安裝 payload 攜帶 compiled files 而非 legacy commands 欄位"""
        with patch.object(install_service.template_compiler, "compile_template") as mock_compile:
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                files=[
                    {
                        "path": ".claude/commands/test-command.md",
                        "source": "commands/test-command.md",
                        "content": "Command content",
                    }
                ],
                installHints={},
            )

            result = await install_service._prepare_install_payload(mock_template_db)

        assert "installPlan" in result
        assert len(result["installPlan"]["files"]) == 1
        assert result["installPlan"]["files"][0]["path"] == ".claude/commands/test-command.md"
        assert "commands" not in result

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_mcp_servers(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 MCP compile hint 的安裝資料"""
        with patch.object(install_service.template_compiler, "compile_template") as mock_compile:
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                installHints={
                    "mcpServers": {
                        "test-mcp": {
                            "type": "stdio",
                            "command": "python",
                            "args": ["-m", "test"],
                            "env": {"KEY": "value"},
                        }
                    }
                },
            )

            result = await install_service._prepare_install_payload(mock_template_db)

        assert "installPlan" in result
        assert "test-mcp" in result["installPlan"]["installHints"]["mcpServers"]
        assert result["installPlan"]["installHints"]["mcpServers"]["test-mcp"]["type"] == "stdio"
        assert result["installPlan"]["installHints"]["mcpServers"]["test-mcp"]["command"] == "python"

    @pytest.mark.asyncio
    async def test_prepare_install_payload_with_skills(
        self,
        install_service,
        mock_template_db
    ):
        """測試：準備含 Skills 的安裝資料"""
        with patch.object(install_service.template_compiler, "compile_template") as mock_compile:
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                installHints={
                    "skills": [
                        {
                            "path": "openspec-ff-change/SKILL.md",
                            "content": "# Skill",
                        }
                    ]
                },
            )

            result = await install_service._prepare_install_payload(mock_template_db)

        assert result["installPlan"]["installHints"]["skills"] == [{
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
            with pytest.raises(Exception, match="Template installation failed"):
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
            with pytest.raises(Exception, match="Cannot connect to workspace runtime"):
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
        """測試：Workspace does not exist返回 None"""
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

    def test_get_runtime_url_prefers_internal_url(self, install_service, mock_workspace):
        """測試：有 internal URL 時優先使用 internal URL"""
        result = install_service._get_runtime_url(mock_workspace)

        assert result == "http://runtime-internal:8080"

    def test_get_runtime_url_falls_back_to_external_url(self, install_service, mock_workspace):
        """測試：沒有 internal URL 時回退到 external URL"""
        mock_workspace.runtime_internal_url = None

        result = install_service._get_runtime_url(mock_workspace)

        assert result == "http://localhost:8080"

    def test_get_runtime_url_no_url(self, install_service, mock_workspace):
        """測試：無 Runtime URL 拋出異常"""
        # Arrange
        mock_workspace.runtime_internal_url = None
        mock_workspace.runtime_external_url = None

        # Act & Assert
        with pytest.raises(TemplateInstallError, match="does not have an available runtime URL") as exc_info:
            install_service._get_runtime_url(mock_workspace)
        assert exc_info.value.code == "TEMPLATE_INSTALL_RUNTIME_URL_MISSING"


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
             patch.object(install_service.template_compiler, "compile_template") as mock_compile, \
             patch('app.services.template_install_service.httpx.AsyncClient') as mock_client:

            mock_get_template.return_value = mock_template_db
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                files=[{"path": "CLAUDE.md", "source": "agents.md", "content": "# Template"}],
                installHints={"agentsMdContent": "# Template"},
            )

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
            call_args = mock_client_instance.post.call_args
            payload = call_args[1]["json"]
            assert "installPlan" in payload

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

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        with patch.object(install_service.template_service, '_get_template') as mock_get_template, \
             patch.object(install_service.template_compiler, "compile_template") as mock_compile, \
             patch('app.services.template_install_service.httpx.AsyncClient') as mock_client:

            mock_get_template.return_value = mock_template_db
            mock_compile.return_value = InstallPlan(
                target=CanonicalTarget.CLAUDE_CODE,
                files=[
                    {"path": "CLAUDE.md", "source": "agents.md", "content": "# Claude.md"},
                    {"path": ".claude/commands/cmd.md", "source": "commands/cmd.md", "content": "content"},
                    {"path": ".claude/agents/user/agent.md", "source": "agents/agent.md", "content": "content"},
                ],
                installHints={
                    "agentsMdContent": "# Claude.md",
                    "outputStyle": [{"fileName": "style.yaml", "content": "concise"}],
                    "mcpServers": {"mcp": {"type": "stdio", "command": "python"}},
                    "hooks": {"before_chat": [{"matcher": "*", "hooks": [{"type": "exec", "command": "echo", "timeout": 30}]}]},
                    "skills": [{"path": "review/SKILL.md", "content": "# skill"}],
                },
            )

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
            assert "installPlan" in payload
            assert len(payload["installPlan"]["files"]) == 3
            assert "mcpServers" in payload["installPlan"]["installHints"]
            assert "hooks" in payload["installPlan"]["installHints"]
            assert "skills" in payload["installPlan"]["installHints"]
