"""WorkspaceService 單元測試"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.db import models as db_models
from app.models import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    WorkspaceEnvVar,
    WorkspacePortMapping,
    WorkspaceResourceRequirements,
    WorkspaceResourceValues,
)
from app.models.workspace import (
    RuntimeStatus,
    FirewallConfig,
    FirewallRuleConfig,
)
from app.services.workspace_service import WorkspaceService


# ============================================================================
# Fixtures
# ============================================================================


def _apply_workspace_defaults(obj, owner=None):
    """補齊 WorkspaceService 轉換所需的欄位預設值。"""
    defaults = {
        "runtime_container_id": None,
        "runtime_internal_url": None,
        "runtime_external_url": None,
        "runtime_internal_port": 3002,
        "runtime_external_port": None,
        "runtime_last_seen": None,
        "canvas_internal_port": 3003,
        "canvas_external_port": None,
        "canvas_internal_url": None,
        "canvas_external_url": None,
        "terminal_external_port": None,
        "terminal_external_url": None,
        "browser_container_id": None,
        "browser_status": "stopped",
        "browser_created_at": None,
        "browser_last_seen": None,
        "browser_webrtc_internal_url": None,
        "browser_webrtc_external_url": None,
        "browser_webrtc_internal_port": 6080,
        "browser_webrtc_external_port": None,
        "browser_cdp_internal_port": 9223,
        "browser_cdp_external_port": None,
        "canvas_container_id": None,
        "canvas_status": "stopped",
        "canvas_created_at": None,
        "canvas_last_seen": None,
        "canvas_internal_url": None,
        "canvas_external_url": None,
        "canvas_internal_port": 3003,
        "canvas_external_port": None,
        "canvas_api_internal_port": 3013,
        "canvas_api_external_port": None,
        "provisioner": "docker",
        "target_namespace": None,
        "runtime_resources": None,
        "workspace_firewall_network_access_enabled": True,
        "workspace_firewall_domain_access_mode": "all",
        "workspace_firewall_allowed_domains": [],
        "browser_firewall_network_access_enabled": True,
        "browser_firewall_domain_access_mode": "all",
        "browser_firewall_allowed_domains": [],
        "acp_cli_args": [],
        "runtime_logs": [],
        "runtime_jobs": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    current_owner = getattr(obj, "owner", None)
    if owner is not None and (current_owner is None or isinstance(current_owner, Mock)):
        obj.owner = owner

    for attr, default in defaults.items():
        current = getattr(obj, attr, None)
        if current is None or isinstance(current, Mock):
            setattr(obj, attr, default)


@pytest.fixture
def mock_db_session():
    """Mock 資料庫 Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=0)
    return session


@pytest.fixture
def workspace_service(mock_db_session):
    """WorkspaceService 實例"""
    return WorkspaceService(mock_db_session)


@pytest.fixture
def sample_workspace_db(user_factory):
    """範例工作區資料庫模型"""
    from app.db import models as db_models

    owner = user_factory()
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-123"
    workspace.owner_id = owner.id
    workspace.owner = owner
    workspace.name = "Test Workspace"
    workspace.description = "Test workspace description"
    workspace.git_url = "https://github.com/test/repo.git"
    workspace.branch = "main"
    workspace.runtime = "docker"
    workspace.provisioner = "docker"
    workspace.target_namespace = None
    workspace.runtime_resources = None
    workspace.cli_type = "claude-code"
    workspace.setup_script = "npm install"
    workspace.env_vars = []
    workspace.port_mappings = []
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "container-123"
    workspace.runtime_internal_url = "http://localhost:3002"
    workspace.runtime_external_url = "https://workspace.example.com"
    workspace.runtime_internal_port = 3002
    workspace.runtime_external_port = 8080
    workspace.runtime_last_seen = datetime.now()
    workspace.browser_container_id = "browser-container-123"
    workspace.browser_status = "running"
    workspace.browser_created_at = None
    workspace.browser_last_seen = None
    workspace.browser_webrtc_internal_url = None
    workspace.browser_webrtc_external_url = None
    workspace.browser_webrtc_internal_port = 6080
    workspace.browser_webrtc_external_port = None
    workspace.browser_cdp_internal_port = 9223
    workspace.browser_cdp_external_port = None
    workspace.canvas_container_id = None
    workspace.canvas_status = "stopped"
    workspace.canvas_created_at = None
    workspace.canvas_last_seen = None
    workspace.canvas_internal_url = None
    workspace.canvas_external_url = None
    workspace.canvas_internal_port = 3003
    workspace.canvas_external_port = None
    workspace.canvas_api_internal_port = 3013
    workspace.canvas_api_external_port = None
    workspace.workspace_firewall_network_access_enabled = True
    workspace.workspace_firewall_domain_access_mode = "all"
    workspace.workspace_firewall_allowed_domains = []
    workspace.browser_firewall_network_access_enabled = True
    workspace.browser_firewall_domain_access_mode = "all"
    workspace.browser_firewall_allowed_domains = []
    workspace.preferred_cli = "claude-code"
    workspace.fallback_enabled = True
    workspace.workspace_path = "/workspace"
    workspace.acp_cli_args = []
    workspace.canvas_internal_port = 3003
    workspace.canvas_external_port = None
    workspace.canvas_internal_url = None
    workspace.canvas_external_url = None
    workspace.terminal_external_port = None
    workspace.terminal_external_url = None
    workspace.created_at = datetime.now()
    workspace.updated_at = datetime.now()
    workspace.runtime_logs = []
    workspace.runtime_jobs = []
    return workspace


# ============================================================================
# Workspace Get Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceGet:
    """工作區查詢測試"""

    def test_get_workspace_success(self, workspace_service, mock_db_session, sample_workspace_db):
        """測試：成功獲取工作區"""
        # Arrange
        workspace_service.settings.CILIUM_ENABLED = True
        workspace_service.settings.FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS = [
            "github.com",
            "registry.npmjs.org",
        ]
        workspace_service.settings.FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS = [
            "google.com"
        ]
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.return_value = sample_workspace_db

        # Act
        result = workspace_service.get("workspace-123")

        # Assert
        assert result is not None
        assert result.provisioner == "docker"
        assert result.target_namespace is None
        assert result.overall_phase == "running"
        assert result.id == "workspace-123"
        assert result.name == "Test Workspace"
        assert result.components.runtime.phase == "running"
        assert result.components.runtime.external_url == "https://workspace.example.com"
        assert result.components.browser.phase == "running"
        assert result.components.canvas.phase == "stopped"
        assert result.runtime_resources is None
        assert [item.name for item in result.system_port_mappings] == [
            "runtime",
            "terminal",
            "browser-webrtc",
            "browser-cdp",
            "canvas",
            "canvas-api",
        ]
        assert all(item.editable is False for item in result.system_port_mappings)
        assert result.firewall_available is True
        assert result.firewall.workspace.effective_allowed_domains == [
            "github.com",
            "registry.npmjs.org",
            "example.com",
        ]
        assert result.firewall.browser.effective_allowed_domains == [
            "google.com",
            "browser.example.com",
        ]
        mock_db_session.get.assert_called_once()

    def test_get_workspace_not_found(self, workspace_service, mock_db_session):
        """測試：工作區不存在返回 None"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        result = workspace_service.get("nonexistent-workspace")

        # Assert
        assert result is None

    def test_get_workspace_syncs_kubernetes_status_before_return(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.target_namespace = "team-a"
        mock_db_session.get.return_value = sample_workspace_db

        def _sync_status(workspace):
            workspace.runtime_status = "running"
            workspace.runtime_internal_url = (
                "http://workspace-runtime-123.team-a.svc.cluster.local:3002"
            )
            workspace.runtime_external_url = (
                "https://workspace-runtime-workspace-123.example.com"
            )
            workspace.browser_status = "running"
            workspace.browser_webrtc_external_url = (
                "https://workspace-browser-workspace-123.example.com"
            )
            workspace.canvas_status = "stopped"
            workspace.canvas_external_url = (
                "https://workspace-canvas-workspace-123.example.com"
            )
            workspace.canvas_external_url = workspace.canvas_external_url

        with patch(
            "app.services.workspace_service.WorkspaceCustomResourceService"
        ) as mock_sync_service:
            mock_sync_service.return_value.sync_workspace_record_status.side_effect = _sync_status
            result = workspace_service.get("workspace-123")

        assert result is not None
        assert result.runtime_status.internal_url == (
            "http://workspace-runtime-123.team-a.svc.cluster.local:3002"
        )
        assert result.runtime_status.external_url == (
            "https://workspace-runtime-workspace-123.example.com"
        )
        assert result.components.browser.external_url == (
            "https://workspace-browser-workspace-123.example.com"
        )
        assert result.components.canvas.external_url == (
            "https://workspace-canvas-workspace-123.example.com"
        )
        mock_sync_service.return_value.sync_workspace_record_status.assert_called_once_with(
            sample_workspace_db
        )


# ============================================================================
# Workspace Create Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceCreate:
    """工作區創建測試"""

    def test_create_workspace_success(
        self, workspace_service, mock_db_session, user_factory, sample_workspace_db
    ):
        """測試：成功創建工作區"""
        # Arrange
        workspace_service.settings.CILIUM_ENABLED = True
        owner = user_factory()
        mock_db_session.get.return_value = owner

        # 當 refresh 被調用時,設置 workspace 的必要屬性
        def mock_refresh(obj):
            if hasattr(obj, 'id') and not obj.id:
                obj.id = "workspace-123"
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="New Workspace",
            description="New workspace description",
            git_url="https://github.com/test/repo.git",
            branch="main",
            runtime="docker",
            cli_type="claude-code",
            setup_script="npm install",
            env_vars=[],
            port_mappings=[
                WorkspacePortMapping(
                    container_port=3002,
                    host_port=8080,
                    protocol="tcp"
                )
            ],
            preferred_cli="claude-code",
            fallback_enabled=True,
            workspace_path="/workspace"
        )

        # Act
        result = workspace_service.create(create_request)

        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        assert result is not None

    def test_create_workspace_with_nonexistent_owner(
        self, workspace_service, mock_db_session
    ):
        """測試：owner 不存在時創建失敗"""
        # Arrange
        mock_db_session.get.return_value = None

        create_request = WorkspaceCreateRequest(
            owner_id="nonexistent-user",
            name="New Workspace",
            git_url="https://github.com/test/repo.git",
            runtime="docker",
            env_vars=[],
            port_mappings=[]
        )

        # Act & Assert
        with pytest.raises(ValueError, match="工作區擁有者不存在"):
            workspace_service.create(create_request)

    def test_create_workspace_with_env_vars(
        self, workspace_service, mock_db_session, user_factory
    ):
        """測試：創建帶環境變量的工作區"""
        # Arrange
        owner = user_factory()
        mock_db_session.get.return_value = owner

        # 當 refresh 被調用時,設置 workspace 的必要屬性
        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Workspace with Env",
            git_url="https://github.com/test/repo.git",
            runtime="docker",
            env_vars=[
                WorkspaceEnvVar(key="NODE_ENV", value="production"),
                WorkspaceEnvVar(key="PORT", value="3000")
            ],
            port_mappings=[]
        )

        # Act
        result = workspace_service.create(create_request)

        # Assert
        mock_db_session.add.assert_called_once()
        assert result is not None
        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.env_vars == [
            {"key": "NODE_ENV", "value": "production"},
            {"key": "PORT", "value": "3000"},
        ]

    def test_create_workspace_sets_external_port_from_default_mapping(
        self, workspace_service, mock_db_session, user_factory
    ):
        """測試：建立工作區時會從 container port 3002 的 mapping 推導 external port"""
        owner = user_factory()
        mock_db_session.get.return_value = owner

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Mapped Workspace",
            git_url="https://github.com/test/repo.git",
            runtime="docker",
            env_vars=[],
            port_mappings=[
                WorkspacePortMapping(container_port=3002, host_port=43002, protocol="tcp"),
                WorkspacePortMapping(container_port=8080, host_port=48080, protocol="tcp"),
            ],
        )

        result = workspace_service.create(create_request)

        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.runtime_external_port == 43002
        assert result.runtime_status.external_port == 43002

    def test_create_docker_workspace_accepts_firewall_when_cilium_disabled(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.CILIUM_ENABLED = False
        workspace_service.settings.RUNTIME_PROVISIONER = "docker"

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Docker Workspace",
            git_url="https://github.com/test/repo.git",
            runtime="docker",
            env_vars=[],
            port_mappings=[],
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    network_access_enabled=True,
                    domain_access_mode="specific",
                    allowed_domains=["example.com"],
                ),
                browser=FirewallRuleConfig(),
            ),
        )

        result = workspace_service.create(create_request)

        assert result is not None
        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.workspace_firewall_allowed_domains == ["example.com"]

    def test_create_kubernetes_workspace_sets_default_namespace(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = [
            "workspace-system",
            "team-a",
        ]

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
            env_vars=[],
            port_mappings=[],
        )

        result = workspace_service.create(create_request)

        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.provisioner == "kubernetes"
        assert created_workspace.target_namespace == "workspace-system"
        assert created_workspace.runtime_resources is None
        assert result.provisioner == "kubernetes"
        assert result.target_namespace == "workspace-system"
        assert result.runtime_resources is not None
        assert result.runtime_resources.requests.cpu == "500m"
        assert result.runtime_resources.limits.memory == "4Gi"

    def test_create_docker_workspace_rejects_runtime_resources(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "docker"

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Docker Workspace",
            runtime="universal",
            env_vars=[],
            port_mappings=[],
            runtime_resources=WorkspaceResourceRequirements(
                requests=WorkspaceResourceValues(cpu="500m", memory="2Gi"),
                limits=WorkspaceResourceValues(cpu="2000m", memory="4Gi"),
            ),
        )

        with pytest.raises(
            ValueError,
            match="runtimeResources 僅支援 Kubernetes 工作區",
        ):
            workspace_service.create(create_request)

    def test_create_kubernetes_workspace_rejects_port_mappings(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = ["workspace-system"]

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
            env_vars=[],
            port_mappings=[
                WorkspacePortMapping(container_port=3000, host_port=3100, protocol="tcp")
            ],
        )

        with pytest.raises(
            ValueError,
            match="portMappings 僅支援 Docker 工作區",
        ):
            workspace_service.create(create_request)

    def test_create_kubernetes_workspace_persists_runtime_resources_override(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = [
            "workspace-system",
            "team-a",
        ]

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
            env_vars=[],
            port_mappings=[],
            runtime_resources=WorkspaceResourceRequirements(
                requests=WorkspaceResourceValues(cpu="750m", memory="3Gi"),
                limits=WorkspaceResourceValues(cpu="2500m", memory="5Gi"),
            ),
        )

        result = workspace_service.create(create_request)

        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.runtime_resources == {
            "requests": {"cpu": "750m", "memory": "3Gi"},
            "limits": {"cpu": "2500m", "memory": "5Gi"},
        }
        assert result.runtime_resources is not None
        assert result.runtime_resources.requests.cpu == "750m"
        assert result.runtime_resources.limits.memory == "5Gi"

    def test_create_kubernetes_workspace_rejects_invalid_namespace(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = ["workspace-system"]

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
            provisioner="kubernetes",
            target_namespace="forbidden",
            env_vars=[],
            port_mappings=[],
        )

        with pytest.raises(ValueError, match="無效的 Kubernetes namespace"):
            workspace_service.create(create_request)

    def test_create_workspace_ignores_payload_provisioner_and_uses_deployment_runtime(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "docker"

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Docker Workspace",
            runtime="universal",
            provisioner="kubernetes",
            target_namespace="workspace-system",
            env_vars=[],
            port_mappings=[],
        )

        result = workspace_service.create(create_request)

        created_workspace = mock_db_session.add.call_args[0][0]
        assert created_workspace.provisioner == "docker"
        assert created_workspace.target_namespace is None
        assert result.provisioner == "docker"
        assert result.target_namespace is None


# ============================================================================
# Workspace Update Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceUpdate:
    """工作區更新測試"""

    def test_update_workspace_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：成功更新工作區"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            name="Updated Workspace",
            description="Updated description"
        )

        # Act
        result = workspace_service.update("workspace-123", update_request)

        # Assert
        assert result is not None
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_not_found(
        self, workspace_service, mock_db_session
    ):
        """測試：更新不存在的工作區返回 None"""
        # Arrange
        mock_db_session.get.return_value = None

        update_request = WorkspaceUpdateRequest(
            name="Updated Workspace"
        )

        # Act
        result = workspace_service.update("nonexistent-workspace", update_request)

        # Assert
        assert result is None

    def test_update_workspace_env_vars(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：更新工作區環境變量"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            env_vars=[
                WorkspaceEnvVar(key="NEW_VAR", value="new_value")
            ]
        )

        # Act
        result = workspace_service.update("workspace-123", update_request)

        # Assert
        assert result is not None
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_provisioner_and_namespace(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = ["workspace-system", "team-a"]

        update_request = WorkspaceUpdateRequest(
            provisioner="kubernetes",
            target_namespace="team-a",
        )

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.provisioner == "kubernetes"
        assert sample_workspace_db.target_namespace == "team-a"

    def test_update_docker_workspace_rejects_runtime_resources(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            runtime_resources=WorkspaceResourceRequirements(
                requests=WorkspaceResourceValues(cpu="750m", memory="3Gi"),
                limits=WorkspaceResourceValues(cpu="2500m", memory="5Gi"),
            )
        )

        with pytest.raises(
            ValueError,
            match="runtimeResources 僅支援 Kubernetes 工作區",
        ):
            workspace_service.update("workspace-123", update_request)

    def test_update_kubernetes_workspace_rejects_port_mappings(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.target_namespace = "workspace-system"

        update_request = WorkspaceUpdateRequest(
            port_mappings=[
                WorkspacePortMapping(container_port=3000, host_port=3100, protocol="tcp")
            ]
        )

        with pytest.raises(
            ValueError,
            match="portMappings 僅支援 Docker 工作區",
        ):
            workspace_service.update("workspace-123", update_request)

    def test_update_kubernetes_workspace_persists_runtime_resources(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.target_namespace = "workspace-system"

        update_request = WorkspaceUpdateRequest(
            runtime_resources=WorkspaceResourceRequirements(
                requests=WorkspaceResourceValues(cpu="750m", memory="3Gi"),
                limits=WorkspaceResourceValues(cpu="2500m", memory="5Gi"),
            )
        )

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.runtime_resources == {
            "requests": {"cpu": "750m", "memory": "3Gi"},
            "limits": {"cpu": "2500m", "memory": "5Gi"},
        }
        assert result.runtime_resources is not None
        assert result.runtime_resources.requests.memory == "3Gi"

    def test_update_workspace_switching_to_docker_clears_runtime_resources(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.target_namespace = "workspace-system"
        sample_workspace_db.runtime_resources = {
            "requests": {"cpu": "750m", "memory": "3Gi"},
            "limits": {"cpu": "2500m", "memory": "5Gi"},
        }

        update_request = WorkspaceUpdateRequest(provisioner="docker")

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.runtime_resources is None

    def test_update_workspace_kubernetes_sets_default_namespace_when_missing(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = [
            "workspace-system",
            "team-a",
        ]

        update_request = WorkspaceUpdateRequest(
            provisioner="kubernetes",
            target_namespace=None,
        )

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.provisioner == "kubernetes"
        assert sample_workspace_db.target_namespace == "workspace-system"

    def test_update_workspace_kubernetes_rejects_invalid_namespace(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
        workspace_service.settings.RUNTIME_K8S_ALLOWED_NAMESPACES = ["workspace-system"]

        update_request = WorkspaceUpdateRequest(
            provisioner="kubernetes",
            target_namespace="forbidden",
        )

        with pytest.raises(ValueError, match="無效的 Kubernetes namespace"):
            workspace_service.update("workspace-123", update_request)


# ============================================================================
# Workspace List Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceList:
    """工作區列表測試"""

    def test_list_workspaces_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：成功列出工作區"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(page=1, page_size=10)

        # Assert
        assert result is not None
        assert len(result.items) == 1
        assert result.items[0].overall_phase == "running"
        assert result.pagination.total == 1
        assert result.pagination.page == 1

    def test_list_workspaces_with_owner_filter(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：按 owner 過濾工作區列表"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(
            page=1,
            page_size=10,
            owner_id="user-123"
        )

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_with_status_filter(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：按狀態過濾工作區列表"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(
            page=1,
            page_size=10,
            status="running"
        )

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_with_search(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：搜索工作區"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(
            page=1,
            page_size=10,
            search="Test"
        )

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_empty(
        self, workspace_service, mock_db_session
    ):
        """測試：空工作區列表"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 0

        # Act
        result = workspace_service.list(page=1, page_size=10)

        # Assert
        assert result is not None
        assert len(result.items) == 0
        assert result.pagination.total == 0

    def test_list_workspaces_syncs_only_kubernetes_records(
        self, workspace_service, mock_db_session, sample_workspace_db, user_factory
    ):
        kubernetes_workspace = sample_workspace_db
        kubernetes_workspace.provisioner = "kubernetes"
        kubernetes_workspace.target_namespace = "team-a"

        docker_owner = user_factory()
        docker_workspace = Mock(spec=db_models.Workspace)
        docker_workspace.id = "workspace-docker"
        docker_workspace.owner_id = docker_owner.id
        docker_workspace.owner = docker_owner
        docker_workspace.name = "Docker Workspace"
        docker_workspace.description = None
        docker_workspace.git_url = None
        docker_workspace.branch = "main"
        docker_workspace.runtime = "universal"
        docker_workspace.runtime_status = "running"
        docker_workspace.cli_type = "claude-code"
        _apply_workspace_defaults(docker_workspace, owner=docker_owner)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            kubernetes_workspace,
            docker_workspace,
        ]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 2

        with patch(
            "app.services.workspace_service.WorkspaceCustomResourceService"
        ) as mock_sync_service:
            result = workspace_service.list(page=1, page_size=10)

        assert len(result.items) == 2
        mock_sync_service.return_value.sync_workspace_record_status.assert_called_once_with(
            kubernetes_workspace
        )


# ============================================================================
# Workspace Lifecycle Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceLifecycle:
    """工作區生命週期測試"""

    def test_mark_workspace_deleting_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：成功標記工作區為刪除中"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        # Act
        result = workspace_service.mark_workspace_deleting("workspace-123")

        # Assert
        assert result is True
        assert sample_workspace_db.runtime_status == "deleting"
        mock_db_session.commit.assert_called_once()

    def test_mark_workspace_deleting_not_found(
        self, workspace_service, mock_db_session
    ):
        """測試：工作區不存在時標記失敗"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        result = workspace_service.mark_workspace_deleting("nonexistent-workspace")

        # Assert
        assert result is False

    def test_mark_workspace_rebuilding_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：成功標記工作區為重啟中"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        # Act
        result = workspace_service.mark_workspace_rebuilding("workspace-123")

        # Assert
        assert result is True
        assert sample_workspace_db.runtime_status == "restarting"
        mock_db_session.commit.assert_called_once()

    def test_mark_workspace_rebuilding_not_found(
        self, workspace_service, mock_db_session
    ):
        """測試：工作區不存在時標記失敗"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        result = workspace_service.mark_workspace_rebuilding("nonexistent-workspace")

        # Assert
        assert result is False

    def test_mark_browser_restarting_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：成功標記 browser 為重啟中"""
        mock_db_session.get.return_value = sample_workspace_db

        result = workspace_service.mark_browser_restarting("workspace-123")

        assert result is True
        assert sample_workspace_db.browser_status == "restarting"
        mock_db_session.commit.assert_called_once()

    def test_mark_browser_restarting_not_found(
        self, workspace_service, mock_db_session
    ):
        """測試：找不到工作區時 browser 重啟標記失敗"""
        mock_db_session.get.return_value = None

        result = workspace_service.mark_browser_restarting("missing-workspace")

        assert result is False

    def test_update_workspace_with_port_mappings(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：更新工作區 port mappings"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            port_mappings=[
                WorkspacePortMapping(
                    container_port=8080,
                    host_port=8081,
                    protocol="tcp"
                )
            ]
        )

        # Act
        result = workspace_service.update("workspace-123", update_request)

        # Assert
        assert result is not None
        assert len(sample_workspace_db.port_mappings) == 1
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_with_runtime_status(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：更新工作區 runtime status"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            runtime_status=RuntimeStatus(
                status="running",
                container_id="container-456",
                internal_url="http://internal:8080",
                external_url="http://external:8080",
                internal_port=8080,
                external_port=8080,
                last_seen=datetime.utcnow()
            )
        )

        # Act
        result = workspace_service.update("workspace-123", update_request)

        # Assert
        assert result is not None
        assert sample_workspace_db.runtime_status == "running"
        assert sample_workspace_db.runtime_container_id == "container-456"
        assert sample_workspace_db.runtime_internal_url == "http://internal:8080"
        assert sample_workspace_db.runtime_external_url == "http://external:8080"
        assert sample_workspace_db.runtime_internal_port == 8080
        assert sample_workspace_db.runtime_external_port == 8080
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_with_firewall_config(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：更新工作區 firewall 配置"""
        # Arrange
        workspace_service.settings.CILIUM_ENABLED = True
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    network_access_enabled=True,
                    domain_access_mode="specific",
                    allowed_domains=["example.com", "test.com"],
                ),
                browser=FirewallRuleConfig(
                    network_access_enabled=False,
                    domain_access_mode="all",
                    allowed_domains=["browser.example.com"],
                ),
            )
        )

        # Act
        result = workspace_service.update("workspace-123", update_request)

        # Assert
        assert result is not None
        assert sample_workspace_db.workspace_firewall_network_access_enabled is True
        assert sample_workspace_db.workspace_firewall_domain_access_mode == "specific"
        assert sample_workspace_db.workspace_firewall_allowed_domains == ["example.com", "test.com"]
        assert sample_workspace_db.browser_firewall_network_access_enabled is False
        assert sample_workspace_db.browser_firewall_domain_access_mode == "all"
        assert sample_workspace_db.browser_firewall_allowed_domains == ["browser.example.com"]
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_with_empty_firewall_allowlist(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：更新 firewall 時會保留空 allowlist 與 network access 狀態"""
        workspace_service.settings.CILIUM_ENABLED = True
        mock_db_session.get.return_value = sample_workspace_db

        update_request = WorkspaceUpdateRequest(
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    network_access_enabled=False,
                    domain_access_mode="all",
                    allowed_domains=[],
                ),
                browser=FirewallRuleConfig(
                    network_access_enabled=True,
                    domain_access_mode="specific",
                    allowed_domains=[],
                ),
            )
        )

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.workspace_firewall_network_access_enabled is False
        assert sample_workspace_db.workspace_firewall_domain_access_mode == "all"
        assert sample_workspace_db.workspace_firewall_allowed_domains == []
        assert sample_workspace_db.browser_firewall_network_access_enabled is True
        assert sample_workspace_db.browser_firewall_domain_access_mode == "specific"
        assert sample_workspace_db.browser_firewall_allowed_domains == []

    def test_update_docker_workspace_accepts_firewall_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        workspace_service.settings.CILIUM_ENABLED = False

        update_request = WorkspaceUpdateRequest(
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    network_access_enabled=True,
                    domain_access_mode="specific",
                    allowed_domains=["example.com"],
                ),
                browser=FirewallRuleConfig(),
            )
        )

        result = workspace_service.update("workspace-123", update_request)

        assert result is not None
        assert sample_workspace_db.workspace_firewall_allowed_domains == ["example.com"]

    def test_update_kubernetes_workspace_rejects_firewall_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        mock_db_session.get.return_value = sample_workspace_db
        sample_workspace_db.provisioner = "kubernetes"
        workspace_service.settings.CILIUM_ENABLED = False

        update_request = WorkspaceUpdateRequest(
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    network_access_enabled=True,
                    domain_access_mode="specific",
                    allowed_domains=["example.com"],
                ),
                browser=FirewallRuleConfig(),
            )
        )

        with pytest.raises(ValueError, match="CILIUM_NOT_ENABLED"):
            workspace_service.update("workspace-123", update_request)

    def test_to_detail_returns_firewall_available_for_docker_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        workspace_service.settings.CILIUM_ENABLED = False
        workspace_service.settings.FIREWALL_DEFAULTS_WORKSPACE_ALLOWED_DOMAINS = [
            "github.com",
            "registry.npmjs.org",
        ]
        workspace_service.settings.FIREWALL_DEFAULTS_BROWSER_ALLOWED_DOMAINS = [
            "google.com"
        ]
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.return_value = sample_workspace_db

        result = workspace_service.get("workspace-123")

        assert result is not None
        assert result.firewall_available is True
        assert result.firewall_unavailable_reason is None
        assert result.firewall.workspace.effective_allowed_domains == [
            "github.com",
            "registry.npmjs.org",
            "example.com",
        ]
        assert result.firewall.browser.effective_allowed_domains == [
            "google.com",
            "browser.example.com",
        ]

    def test_to_detail_returns_firewall_unavailable_for_kubernetes_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        workspace_service.settings.CILIUM_ENABLED = False
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.return_value = sample_workspace_db

        with patch(
            "app.services.workspace_service.WorkspaceCustomResourceService"
        ) as mock_sync_service:
            result = workspace_service.get("workspace-123")

        assert result is not None
        assert result.firewall_available is False
        assert result.firewall_unavailable_reason == "CILIUM_NOT_ENABLED"
        assert result.firewall.workspace.effective_allowed_domains == []
        assert result.firewall.browser.effective_allowed_domains == []
        mock_sync_service.return_value.sync_workspace_record_status.assert_called_once_with(
            sample_workspace_db
        )

    def test_to_detail_with_runtime_job(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """測試：_to_detail 包含 runtime job"""
        # Arrange
        runtime_job = db_models.WorkspaceRuntimeJob(
            id="job-123",
            workspace_id="workspace-123",
            operation="start",
            strategy="immediate",
            status="running",
            retries=0,
            scheduled_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            finished_at=None,
            error_message=None
        )
        sample_workspace_db.runtime_jobs = [runtime_job]

        # Act
        result = workspace_service._to_detail(sample_workspace_db)

        # Assert
        assert result is not None
        assert result.runtime_job is not None
        assert result.runtime_job.id == "job-123"
        assert result.runtime_job.operation == "start"
        assert result.runtime_job.status == "running"

    def test_to_detail_includes_restart_metadata_from_runtime_jobs(
        self, workspace_service, sample_workspace_db
    ):
        scheduled_at = datetime.utcnow()
        browser_job = db_models.WorkspaceRuntimeJob(
            id="job-browser",
            workspace_id="workspace-123",
            operation="restart_browser_custom_resource",
            strategy="kubernetes",
            status="completed",
            retries=0,
            scheduled_at=scheduled_at,
            started_at=scheduled_at,
            finished_at=scheduled_at,
            error_message=None,
        )
        sample_workspace_db.runtime_jobs = [browser_job]

        result = workspace_service._to_detail(sample_workspace_db)

        assert result.components.browser.last_restart_requested_at == scheduled_at
        assert result.components.runtime.last_restart_requested_at is None

    def test_to_detail_includes_restart_metadata_from_runtime_logs(
        self, workspace_service, sample_workspace_db
    ):
        created_at = datetime.utcnow()
        runtime_log = Mock()
        runtime_log.stage = "restarting"
        runtime_log.created_at = created_at

        canvas_log = Mock()
        canvas_log.stage = "canvas_restarting"
        canvas_log.created_at = created_at

        sample_workspace_db.runtime_logs = [runtime_log, canvas_log]

        result = workspace_service._to_detail(sample_workspace_db)

        assert result.components.runtime.last_restart_requested_at == created_at
        assert result.components.canvas.last_restart_requested_at == created_at
