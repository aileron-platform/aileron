"""Unit Tests for WorkspaceService"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.exc import ProgrammingError

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.settings.models import UserSettings
from app.modules.workspace.browser_credentials import BrowserCredentialService
from app.modules.workspace.capabilities import (
    WorkspaceCapabilities,
    build_capabilities_from_settings,
)
from app.modules.workspace.catalog import (
    WorkspaceCapabilitiesSelectionError,
    WorkspaceService,
    WorkspaceUpdatePostCommitEffects,
)
from app.modules.workspace.firewall_contract import FirewallConfig, FirewallRuleConfig
from app.modules.workspace.models import (
    WorkspaceCreateRequest,
    WorkspaceSensitiveSettingsReplaceRequest,
    WorkspaceShareUpdateRequest,
    WorkspaceUpdateRequest,
)

# ============================================================================
# Fixtures
# ============================================================================


def _apply_workspace_defaults(obj, owner=None):
    """Fill in Required Field Default Values for WorkspaceService Conversion."""
    defaults = {
        "bootstrap_revision": 1,
        "bootstrap_observed_revision": 1,
        "bootstrap_status": "ready",
        "bootstrap_error_code": None,
        "bootstrap_last_transition_at": None,
        "runtime_container_id": None,
        "runtime_desired_revision": 1,
        "runtime_observed_revision": 1,
        "runtime_reason": None,
        "runtime_error_code": None,
        "runtime_last_transition_at": None,
        "runtime_internal_url": None,
        "runtime_internal_port": 3002,
        "runtime_last_seen": None,
        "canvas_internal_port": 3003,
        "canvas_internal_url": None,
        "terminal_internal_url": None,
        "browser_container_id": None,
        "browser_desired_revision": 1,
        "browser_observed_revision": 1,
        "browser_reason": None,
        "browser_error_code": None,
        "browser_last_transition_at": None,
        "browser_status": "stopped",
        "browser_created_at": None,
        "browser_last_seen": None,
        "browser_webrtc_internal_url": None,
        "browser_webrtc_internal_port": 6080,
        "browser_cdp_internal_port": 9223,
        "canvas_container_id": None,
        "canvas_desired_revision": 1,
        "canvas_observed_revision": 1,
        "canvas_reason": None,
        "canvas_error_code": None,
        "canvas_last_transition_at": None,
        "canvas_status": "stopped",
        "canvas_created_at": None,
        "canvas_last_seen": None,
        "canvas_internal_url": None,
        "canvas_internal_port": 3003,
        "canvas_api_internal_port": 3013,
        "provisioner": "docker",
        "target_namespace": None,
        "knowledge_base_mount_active_revision": 0,
        "knowledge_base_mount_desired_revision": 0,
        "knowledge_base_mount_observed_revision": 0,
        "knowledge_base_mount_sync_status": "ready",
        "knowledge_base_mount_error_code": None,
        "runtime_access_revision": 0,
        "runtime_access_observed_revision": 0,
        "runtime_instance_id": None,
        "workspace_firewall_egress_mode": "unrestricted",
        "workspace_firewall_allowed_domains": [],
        "browser_firewall_egress_mode": "unrestricted",
        "browser_firewall_allowed_domains": [],
        "agentic_tools": ["claude-code"],
        "worktree_subdir": ".worktrees",
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


def _added_workspace(mock_db_session):
    return next(
        call.args[0]
        for call in mock_db_session.add.call_args_list
        if isinstance(call.args[0], db_models.Workspace)
    )


def _workspace_and_owner_get(workspace):
    """Return a model-aware SQLAlchemy Session.get test double."""

    def get(model, object_id):
        if model is db_models.Workspace and object_id == workspace.id:
            return workspace
        if model is db_models.User and object_id == workspace.owner_id:
            return workspace.owner
        return None

    return get


@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=0)
    return session


@pytest.fixture
def workspace_service(mock_db_session, monkeypatch):
    """WorkspaceService Instance"""
    monkeypatch.setattr(
        BrowserCredentialService,
        "from_settings",
        classmethod(lambda cls: Mock(active_key_id="test-browser-key")),
    )
    return WorkspaceService(mock_db_session)


def test_authorization_context_is_read_only_for_kubernetes_workspace(
    workspace_service, mock_db_session
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-k8s"
    workspace.owner_id = "owner"
    workspace.provisioner = "kubernetes"
    workspace.agentic_tools = ["codex"]
    workspace.agentic_capabilities = None
    mock_db_session.get.return_value = workspace

    context = workspace_service.get_authorization_context(
        "workspace-k8s", current_user_id="owner"
    )

    assert context is not None
    assert context.access_role == "owner"
    assert [tool.id for tool in context.capabilities.tools] == ["codex"]
    assert context.capabilities.default_tool == "codex"
    mock_db_session.commit.assert_not_called()
    mock_db_session.rollback.assert_not_called()


def test_get_capabilities_filters_persisted_snapshot_by_workspace_selection(
    workspace_service,
    mock_db_session,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    workspace.owner_id = "owner"
    workspace.agentic_tools = ["codex"]
    persisted = build_capabilities_from_settings(UserSettings())
    workspace.agentic_capabilities = persisted.model_dump(by_alias=True)
    mock_db_session.get.return_value = workspace

    capabilities = workspace_service.get_capabilities(
        workspace.id,
        actor=AuthorizationActor("owner", "member"),
    )

    assert capabilities is not None
    assert [tool.id for tool in capabilities.tools] == ["codex"]
    assert capabilities.default_tool == "codex"
    persisted_codex = next(tool for tool in persisted.tools if tool.id == "codex")
    assert capabilities.tools[0] == persisted_codex


def test_get_capabilities_filters_default_snapshot_by_workspace_selection(
    workspace_service,
    mock_db_session,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    workspace.owner_id = "owner"
    workspace.agentic_tools = ["opencode"]
    workspace.agentic_capabilities = None
    mock_db_session.get.return_value = workspace

    capabilities = workspace_service.get_capabilities(
        workspace.id,
        actor=AuthorizationActor("owner", "member"),
    )

    assert capabilities is not None
    assert [tool.id for tool in capabilities.tools] == ["opencode"]
    assert capabilities.default_tool == "opencode"


def test_update_capabilities_serializes_with_workspace_lifecycle(
    workspace_service,
    mock_db_session,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    workspace.owner_id = "owner"
    workspace.agentic_tools = ["claude-code"]
    workspace.agentic_capabilities = None
    mock_db_session.get.return_value = workspace
    mock_db_session.scalar.return_value = workspace
    capabilities = build_capabilities_from_settings(UserSettings())

    with patch(
        "app.modules.workspace.catalog.acquire_workspace_transaction_lock"
    ) as acquire_lock:
        result = workspace_service.update_capabilities(
            workspace.id,
            capabilities,
            actor=AuthorizationActor("owner", "member"),
        )

    acquire_lock.assert_called_once_with(mock_db_session, workspace.id)
    mock_db_session.scalar.assert_called_once()
    assert workspace.agentic_capabilities == capabilities.model_dump(by_alias=True)
    assert result == capabilities
    mock_db_session.rollback.assert_not_called()
    mock_db_session.refresh.assert_not_called()


@pytest.mark.parametrize(
    "agentic_tools",
    (["claude-code"], ["claude-code", "codex"]),
    ids=("no-selected-provider", "partial-selected-providers"),
)
def test_update_capabilities_rejects_snapshot_missing_selected_provider(
    workspace_service,
    mock_db_session,
    agentic_tools,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    workspace.owner_id = "owner"
    workspace.agentic_tools = agentic_tools
    workspace.agentic_capabilities = None
    mock_db_session.get.return_value = workspace
    mock_db_session.scalar.return_value = workspace
    full_snapshot = build_capabilities_from_settings(UserSettings())
    codex = next(tool for tool in full_snapshot.tools if tool.id == "codex")
    capabilities = WorkspaceCapabilities(
        default_tool="codex",
        tools=[codex],
    )

    with (
        patch("app.modules.workspace.catalog.acquire_workspace_transaction_lock"),
        pytest.raises(WorkspaceCapabilitiesSelectionError) as exc_info,
    ):
        workspace_service.update_capabilities(
            workspace.id,
            capabilities,
            actor=AuthorizationActor("owner", "member"),
        )

    assert exc_info.value.code == "WORKSPACE_CAPABILITIES_SELECTION_MISMATCH"
    assert workspace.agentic_capabilities is None
    mock_db_session.commit.assert_not_called()
    mock_db_session.rollback.assert_called_once()


def test_update_capabilities_rolls_back_when_workspace_disappears_after_lock(
    workspace_service,
    mock_db_session,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    mock_db_session.get.return_value = workspace
    mock_db_session.scalar.return_value = None

    with patch(
        "app.modules.workspace.catalog.acquire_workspace_transaction_lock"
    ) as acquire_lock:
        result = workspace_service.update_capabilities(
            workspace.id,
            build_capabilities_from_settings(UserSettings()),
            actor=AuthorizationActor("owner", "member"),
        )

    assert result is None
    acquire_lock.assert_called_once_with(mock_db_session, workspace.id)
    mock_db_session.rollback.assert_called_once()
    mock_db_session.commit.assert_not_called()


def test_update_capabilities_rolls_back_when_commit_fails(
    workspace_service,
    mock_db_session,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-capabilities"
    workspace.owner_id = "owner"
    mock_db_session.get.return_value = workspace
    mock_db_session.scalar.return_value = workspace
    mock_db_session.commit.side_effect = RuntimeError("commit failed")
    with (
        patch("app.modules.workspace.catalog.acquire_workspace_transaction_lock"),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        workspace_service.update_capabilities(
            workspace.id,
            build_capabilities_from_settings(UserSettings()),
            actor=AuthorizationActor("owner", "member"),
        )

    mock_db_session.rollback.assert_called_once()


@pytest.fixture
def sample_workspace_db(user_factory):
    """Sample Workspace Database Model"""
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
    workspace.knowledge_base_mount_active_revision = 0
    workspace.knowledge_base_mount_desired_revision = 0
    workspace.knowledge_base_mount_observed_revision = 0
    workspace.knowledge_base_mount_sync_status = "ready"
    workspace.knowledge_base_mount_error_code = None
    workspace.runtime_access_revision = 0
    workspace.runtime_access_observed_revision = 0
    workspace.runtime_instance_id = None
    workspace.agentic_tools = ["claude-code"]
    workspace.agentic_capabilities = None
    workspace.setup_script = "npm install"
    workspace.env_vars = []
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "container-123"
    workspace.runtime_internal_url = "http://localhost:3002"
    workspace.runtime_internal_port = 3002
    workspace.runtime_last_seen = datetime.now()
    workspace.browser_container_id = "browser-container-123"
    workspace.browser_status = "running"
    workspace.browser_connectivity_state = "ready"
    workspace.browser_connectivity_contract_version = "browser-connectivity/v1"
    workspace.browser_connectivity_admission = "allowed"
    workspace.browser_connectivity_browser_generation = None
    workspace.browser_connectivity_profile_revision = "profile-1"
    workspace.browser_connectivity_credential_revision = "1"
    workspace.browser_connectivity_backend_state = "pending"
    workspace.browser_connectivity_backend_accepted_at = None
    workspace.browser_connectivity_backend_expires_at = None
    workspace.browser_connectivity_backend_reason = None
    workspace.browser_connectivity_backend_error_code = None
    workspace.browser_connectivity_frontend_state = "pending"
    workspace.browser_connectivity_frontend_accepted_at = None
    workspace.browser_connectivity_frontend_expires_at = None
    workspace.browser_connectivity_frontend_reason = None
    workspace.browser_connectivity_frontend_error_code = None
    workspace.browser_connectivity_accepted_at = datetime.now()
    workspace.browser_connectivity_expires_at = datetime.now() + timedelta(minutes=1)
    workspace.browser_connectivity_reason = "BrowserConnectivityReady"
    workspace.browser_connectivity_error_code = None
    workspace.browser_connectivity_last_transition_at = datetime.now()
    workspace.browser_created_at = None
    workspace.browser_last_seen = None
    workspace.browser_webrtc_internal_url = None
    workspace.browser_webrtc_internal_port = 6080
    workspace.browser_cdp_internal_port = 9223
    workspace.canvas_container_id = None
    workspace.canvas_status = "stopped"
    workspace.canvas_created_at = None
    workspace.canvas_last_seen = None
    workspace.canvas_internal_url = None
    workspace.canvas_internal_port = 3003
    workspace.canvas_api_internal_port = 3013
    workspace.workspace_firewall_egress_mode = "unrestricted"
    workspace.workspace_firewall_allowed_domains = []
    workspace.browser_firewall_egress_mode = "unrestricted"
    workspace.browser_firewall_allowed_domains = []
    workspace.preferred_cli = "claude-code"
    workspace.fallback_enabled = True
    workspace.workspace_path = "/workspace"
    workspace.worktree_subdir = ".worktrees"
    workspace.acp_cli_args = []
    workspace.canvas_internal_port = 3003
    workspace.canvas_internal_url = None
    workspace.created_at = datetime.now()
    workspace.updated_at = datetime.now()
    workspace.runtime_logs = []
    workspace.runtime_jobs = []
    _apply_workspace_defaults(workspace, owner=owner)
    return workspace


# ============================================================================
# Workspace Get Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceGet:
    """Workspace Query Tests"""

    def test_get_workspace_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Successfully Retrieve Workspace"""
        # Arrange
        workspace_service.settings.CILIUM_ENABLED = True
        sample_workspace_db.workspace_firewall_egress_mode = "allowlist"
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_egress_mode = "allowlist"
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        # Act
        result = workspace_service.get(
            "workspace-123",
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
        )

        # Assert
        assert result is not None
        assert result.provisioner == "docker"
        assert result.target_namespace is None
        assert result.overall_phase == "running"
        assert result.id == "workspace-123"
        assert result.name == "Test Workspace"
        assert result.components.runtime.phase == "Running"
        assert result.runtime_status.runtime_url == "/workspaces/workspace-123/runtime"
        assert result.runtime_status.browser_url == "/workspaces/workspace-123/browser"
        assert result.runtime_status.canvas_url == "/workspaces/workspace-123/canvas"
        assert result.components.browser.phase == "Running"
        assert result.components.canvas.phase == "Stopped"
        assert result.firewall_available is True
        assert result.firewall.workspace.allowed_domains == ["example.com"]
        assert result.firewall.browser.allowed_domains == ["browser.example.com"]
        mock_db_session.get.assert_any_call(
            db_models.Workspace,
            "workspace-123",
        )

    def test_get_workspace_not_found(self, workspace_service, mock_db_session):
        """Test: Return None When Workspace Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        result = workspace_service.get(
            "nonexistent-workspace",
            actor=AuthorizationActor("owner", "member"),
        )

        # Assert
        assert result is None

    def test_to_workspace_owner_falls_back_to_stable_columns_when_owner_lazy_load_fails(
        self, workspace_service, mock_db_session
    ):
        """Test: Convert workspace owner without relying on newer User ORM columns."""

        class WorkspaceWithBrokenOwner:
            id = "workspace-123"
            owner_id = "workspace-owner-id"

            @property
            def owner(self):
                raise ProgrammingError(
                    "SELECT users.identity_enabled FROM users",
                    {},
                    Exception("column users.identity_enabled does not exist"),
                )

        mock_db_session.execute.return_value.mappings.return_value.first.return_value = {
            "id": "workspace-owner-id",
            "username": "admin",
            "email": "admin@aileron.com",
            "display_name": "System Administrator",
            "avatar_url": None,
        }

        owner = workspace_service._to_workspace_owner(WorkspaceWithBrokenOwner())

        assert owner.id == "workspace-owner-id"
        assert owner.username == "admin"
        assert owner.email == "admin@aileron.com"
        assert owner.display_name == "System Administrator"
        mock_db_session.rollback.assert_called_once()

    def test_get_workspace_projects_same_origin_urls_without_internal_topology(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.target_namespace = "team-a"
        sample_workspace_db.runtime_status = "running"
        sample_workspace_db.runtime_internal_url = (
            "http://workspace-runtime-123.team-a.svc.cluster.local:3002"
        )
        sample_workspace_db.browser_status = "running"
        sample_workspace_db.canvas_status = "stopped"
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        result = workspace_service.get(
            "workspace-123",
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
        )

        assert result is not None
        assert result.runtime_status.runtime_url == "/workspaces/workspace-123/runtime"
        assert result.runtime_status.browser_url == "/workspaces/workspace-123/browser"
        assert result.runtime_status.canvas_url == "/workspaces/workspace-123/canvas"
        payload = result.model_dump(by_alias=True)
        runtime_status = payload["runtimeStatus"]
        assert "internalUrl" not in runtime_status
        assert "externalUrl" not in runtime_status
        assert "externalPort" not in runtime_status
        assert "terminalExternalUrl" not in runtime_status
        assert "browserWebrtcInternalUrl" not in runtime_status
        assert "browserWebrtcExternalUrl" not in runtime_status
        assert "canvasInternalUrl" not in runtime_status
        assert "canvasExternalUrl" not in runtime_status
        assert "internalUrl" not in payload["components"]["runtime"]
        assert "externalUrl" not in payload["components"]["runtime"]
        mock_db_session.commit.assert_not_called()


# ============================================================================
# Workspace Create Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceCreate:
    """Workspace Creation Tests"""

    def test_create_workspace_success(
        self, workspace_service, mock_db_session, user_factory, sample_workspace_db
    ):
        """Test: Successfully Create Workspace"""
        # Arrange
        workspace_service.settings.CILIUM_ENABLED = True
        owner = user_factory()
        mock_db_session.get.return_value = owner

        # When refresh is called, set up necessary workspace properties
        def mock_refresh(obj):
            if hasattr(obj, "id") and not obj.id:
                obj.id = "workspace-123"
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="New Workspace",
            description="New workspace description",
            runtime="docker",
            agentic_tools=["claude-code"],
            preferred_cli="claude-code",
            fallback_enabled=True,
            workspace_path="/workspace",
        )

        # Act
        result = workspace_service.create(create_request)

        # Assert
        assert _added_workspace(mock_db_session) is not None
        mock_db_session.commit.assert_called_once()
        assert result is not None
        assert result.worktree_subdir == ".worktrees"
        assert result.runtime_status.runtime_url.startswith("/workspaces/")
        assert result.runtime_status.runtime_url.endswith("/runtime")
        assert result.runtime_status.browser_url.endswith("/browser")
        assert result.runtime_status.canvas_url.endswith("/canvas")

    def test_create_workspace_persists_worktree_subdir(
        self, workspace_service, mock_db_session, user_factory
    ):
        """Test: Create Workspace With Custom Worktree Subdirectory"""
        # Arrange
        owner = user_factory()
        mock_db_session.get.return_value = owner

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh
        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="New Workspace",
            runtime="docker",
            worktree_subdir=" worktree ",
        )

        # Act
        result = workspace_service.create(create_request)

        # Assert
        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.worktree_subdir == "worktree"
        assert result.worktree_subdir == "worktree"

    def test_create_workspace_with_nonexistent_owner(
        self, workspace_service, mock_db_session
    ):
        """Test: Creation Fails When Owner Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = None

        create_request = WorkspaceCreateRequest(
            owner_id="nonexistent-user",
            name="New Workspace",
            runtime="docker",
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Workspace owner does not exist"):
            workspace_service.create(create_request)

    def test_create_workspace_initializes_empty_sensitive_settings(
        self, workspace_service, mock_db_session, user_factory
    ):
        """General workspace creation does not accept sensitive settings."""
        # Arrange
        owner = user_factory()
        mock_db_session.get.return_value = owner

        # When refresh is called, set up necessary workspace properties
        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="Workspace with Env",
            runtime="docker",
        )

        # Act
        result = workspace_service.create(create_request)

        # Assert
        assert _added_workspace(mock_db_session) is not None
        assert result is not None
        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.setup_script is None
        assert created_workspace.env_vars == []
        assert created_workspace.acp_cli_args == []

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
            runtime="docker",
            firewall=FirewallConfig(
                workspace=FirewallRuleConfig(
                    egress_mode="allowlist",
                    allowed_domains=["example.com"],
                ),
                browser=FirewallRuleConfig(),
            ),
        )

        result = workspace_service.create(create_request)

        assert result is not None
        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.workspace_firewall_allowed_domains == ["example.com"]

    def test_create_workspace_seeds_firewall_when_request_omits_it(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings._firewall_seed = FirewallConfig(
            workspace=FirewallRuleConfig(
                egress_mode="allowlist",
                allowed_domains=["GitHub.com.", "registry.npmjs.org"],
            ),
            browser=FirewallRuleConfig(
                egress_mode="allowlist",
                allowed_domains=["google.com"],
            ),
        )

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        workspace_service.create(
            WorkspaceCreateRequest(
                owner_id=owner.id,
                name="Seeded Workspace",
                runtime="docker",
            )
        )

        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.workspace_firewall_egress_mode == "allowlist"
        assert created_workspace.workspace_firewall_allowed_domains == [
            "github.com",
            "registry.npmjs.org",
        ]
        assert created_workspace.browser_firewall_egress_mode == "allowlist"
        assert created_workspace.browser_firewall_allowed_domains == ["google.com"]

    def test_create_workspace_explicit_firewall_does_not_union_seed(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings._firewall_seed = FirewallConfig(
            workspace=FirewallRuleConfig(
                egress_mode="allowlist",
                allowed_domains=["github.com"],
            ),
            browser=FirewallRuleConfig(
                egress_mode="allowlist",
                allowed_domains=["google.com"],
            ),
        )

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        workspace_service.create(
            WorkspaceCreateRequest(
                owner_id=owner.id,
                name="Explicit Firewall Workspace",
                runtime="docker",
                firewall=FirewallConfig(
                    workspace=FirewallRuleConfig(
                        egress_mode="blocked",
                        allowed_domains=[],
                    ),
                    browser=FirewallRuleConfig(
                        egress_mode="blocked",
                        allowed_domains=[],
                    ),
                ),
            )
        )

        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.workspace_firewall_allowed_domains == []
        assert created_workspace.browser_firewall_allowed_domains == []

    def test_create_kubernetes_workspace_sets_default_namespace(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
        )

        result = workspace_service.create(create_request)

        created_workspace = _added_workspace(mock_db_session)
        assert created_workspace.provisioner == "kubernetes"
        assert created_workspace.target_namespace == "workspace-system"
        assert result.provisioner == "kubernetes"
        assert result.target_namespace == "workspace-system"

    def test_create_kubernetes_workspace_without_port_configuration(
        self, workspace_service, mock_db_session, user_factory
    ):
        owner = user_factory()
        mock_db_session.get.return_value = owner
        workspace_service.settings.RUNTIME_PROVISIONER = "kubernetes"
        workspace_service.settings.RUNTIME_K8S_NAMESPACE = "workspace-system"

        create_request = WorkspaceCreateRequest(
            owner_id=owner.id,
            name="K8s Workspace",
            runtime="universal",
        )

        def mock_refresh(obj):
            _apply_workspace_defaults(obj, owner=owner)

        mock_db_session.refresh.side_effect = mock_refresh
        result = workspace_service.create(create_request)
        assert result is not None

    def test_create_workspace_uses_deployment_runtime_without_public_override(
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
        )

        result = workspace_service.create(create_request)

        created_workspace = _added_workspace(mock_db_session)
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
    """Workspace update tests"""

    def test_update_workspace_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: update workspace successfully"""
        # Arrange
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        update_request = WorkspaceUpdateRequest(
            name="Updated Workspace", description="Updated description"
        )

        # Act
        result = workspace_service.update(
            "workspace-123",
            update_request,
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
        )

        # Assert
        assert result is not None
        mock_db_session.commit.assert_called_once()

    def test_update_workspace_persists_agentic_tools(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Workspace enabled tools can be updated."""
        # Arrange
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)
        sample_workspace_db.agentic_tools = ["codex"]
        sample_workspace_db.runtime_instance_id = "runtime-instance-1"
        post_commit_effects = WorkspaceUpdatePostCommitEffects()

        update_request = WorkspaceUpdateRequest(
            agenticTools=["opencode", "claude-code"],
        )

        # Act
        result = workspace_service.update(
            "workspace-123",
            update_request,
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
            post_commit_effects=post_commit_effects,
        )

        # Assert
        assert result is not None
        assert sample_workspace_db.agentic_tools == ["claude-code", "opencode"]
        assert post_commit_effects.capabilities_sync_target is not None
        assert post_commit_effects.capabilities_sync_target.workspace_id == (
            sample_workspace_db.id
        )
        assert post_commit_effects.capabilities_sync_target.runtime_url == (
            sample_workspace_db.runtime_internal_url
        )
        mock_db_session.commit.assert_called_once()

    @pytest.mark.parametrize(
        (
            "runtime_status",
            "runtime_url",
            "runtime_instance_id",
            "requested_tools",
        ),
        [
            (
                "running",
                "http://localhost:3002",
                "runtime-instance-1",
                ["claude-code"],
            ),
            (
                "stopped",
                "http://localhost:3002",
                "runtime-instance-1",
                ["codex"],
            ),
            ("running", None, "runtime-instance-1", ["codex"]),
            ("running", "http://localhost:3002", None, ["codex"]),
        ],
    )
    def test_update_workspace_skips_docker_capabilities_sync_when_ineligible(
        self,
        workspace_service,
        mock_db_session,
        sample_workspace_db,
        runtime_status,
        runtime_url,
        runtime_instance_id,
        requested_tools,
    ):
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)
        sample_workspace_db.agentic_tools = ["claude-code"]
        sample_workspace_db.runtime_status = runtime_status
        sample_workspace_db.runtime_internal_url = runtime_url
        sample_workspace_db.runtime_instance_id = runtime_instance_id
        post_commit_effects = WorkspaceUpdatePostCommitEffects()

        result = workspace_service.update(
            sample_workspace_db.id,
            WorkspaceUpdateRequest(agenticTools=requested_tools),
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
            post_commit_effects=post_commit_effects,
        )

        assert result is not None
        assert post_commit_effects.capabilities_sync_target is None

    @pytest.mark.parametrize(
        "requested_tools",
        (["claude-code"], ["claude-code", "codex"]),
        ids=("no-selected-provider", "partial-selected-providers"),
    )
    def test_update_workspace_rejects_selection_missing_from_persisted_snapshot(
        self,
        workspace_service,
        mock_db_session,
        sample_workspace_db,
        requested_tools,
    ):
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)
        full_snapshot = build_capabilities_from_settings(UserSettings())
        codex = next(tool for tool in full_snapshot.tools if tool.id == "codex")
        sample_workspace_db.agentic_tools = ["codex"]
        sample_workspace_db.agentic_capabilities = WorkspaceCapabilities(
            default_tool="codex",
            tools=[codex],
        ).model_dump(by_alias=True)
        post_commit_effects = WorkspaceUpdatePostCommitEffects()

        with pytest.raises(WorkspaceCapabilitiesSelectionError) as exc_info:
            workspace_service.update(
                sample_workspace_db.id,
                WorkspaceUpdateRequest(agenticTools=requested_tools),
                actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
                post_commit_effects=post_commit_effects,
            )

        assert exc_info.value.code == "WORKSPACE_CAPABILITIES_SELECTION_MISMATCH"
        assert sample_workspace_db.agentic_tools == ["codex"]
        assert post_commit_effects.capabilities_sync_target is None
        mock_db_session.commit.assert_not_called()
        mock_db_session.rollback.assert_called_once()

    def test_update_workspace_persists_worktree_subdir_and_notifies_runtime(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Update Worktree Subdirectory And Notify Runtime"""
        # Arrange
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)
        sample_workspace_db.runtime_instance_id = "runtime-instance-1"
        signed_headers = {
            "Authorization": "Bearer manager-signed-runtime-command",
            "Content-Type": "application/json",
        }
        response = MagicMock()
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response

        # Act
        with (
            patch(
                "app.modules.workspace.catalog.runtime_command_headers",
                return_value=signed_headers,
            ) as command_headers,
            patch("app.modules.workspace.catalog.httpx.Client", return_value=client),
        ):
            result = workspace_service.update(
                "workspace-123",
                WorkspaceUpdateRequest(worktree_subdir="worktree"),
                actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
            )

        # Assert
        assert result is not None
        assert sample_workspace_db.worktree_subdir == "worktree"
        command_headers.assert_called_once_with(
            workspace_id="workspace-123",
            runtime_instance_id="runtime-instance-1",
            action="worktree.sync",
        )
        client.post.assert_called_once_with(
            "http://localhost:3002/api/v1/internal/worktree/sync-gitignore",
            json={"subdir": "worktree", "previous": ".worktrees"},
            headers=signed_headers,
        )

    def test_update_workspace_worktree_sync_failure_does_not_rollback(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Runtime Sync Failure Does Not Roll Back Database Update"""
        # Arrange
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)
        sample_workspace_db.runtime_instance_id = "runtime-instance-1"
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = RuntimeError("offline")

        # Act
        with (
            patch(
                "app.modules.workspace.catalog.runtime_command_headers",
                return_value={
                    "Authorization": "Bearer manager-signed-runtime-command",
                    "Content-Type": "application/json",
                },
            ),
            patch("app.modules.workspace.catalog.httpx.Client", return_value=client),
        ):
            result = workspace_service.update(
                "workspace-123",
                WorkspaceUpdateRequest(worktree_subdir="worktree"),
                actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
            )

        # Assert
        assert result is not None
        assert sample_workspace_db.worktree_subdir == "worktree"
        client.post.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "/",
            "a/",
            "/a",
            "a//b",
            "\\",
            ".",
            "..",
            "a/../b",
            "a\\b",
            "x" * 65,
        ],
    )
    def test_worktree_subdir_validator_rejects_invalid_values(self, value):
        """Test: Invalid Worktree Subdirectory Values Are Rejected"""
        with pytest.raises(Exception) as exc:
            WorkspaceUpdateRequest(worktree_subdir=value)

        assert "WORKSPACE_WORKTREE_SUBDIR_INVALID" in str(exc.value)

    @pytest.mark.parametrize("value", ["worktree", "branches/team-a", "a..b"])
    def test_worktree_subdir_validator_accepts_relative_paths(self, value):
        """Test: Valid Worktree Relative Paths Are Accepted"""
        request = WorkspaceUpdateRequest(worktree_subdir=value)

        assert request.worktree_subdir == value

    def test_update_workspace_not_found(self, workspace_service, mock_db_session):
        """Test: Return None When Updating Non-Existent Workspace"""
        # Arrange
        mock_db_session.get.return_value = None

        update_request = WorkspaceUpdateRequest(name="Updated Workspace")

        # Act
        result = workspace_service.update(
            "nonexistent-workspace",
            update_request,
            actor=AuthorizationActor("owner", "member"),
        )

        # Assert
        assert result is None

    def test_replace_sensitive_settings_env_vars(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Sensitive settings use the dedicated operation-gated endpoint."""
        # Arrange
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        update_request = WorkspaceSensitiveSettingsReplaceRequest(
            env_vars=[{"key": "NEW_VAR", "value": "new_value"}]
        )

        # Act
        with patch(
            "app.modules.workspace.catalog.AuthorizationOperationPolicy."
            "require_workspace_operation"
        ):
            result = workspace_service.replace_sensitive_settings(
                "workspace-123",
                update_request,
                actor=AuthorizationActor(
                    user_id=sample_workspace_db.owner_id,
                    platform_role="member",
                ),
            )

        # Assert
        assert result is not None
        assert result.env_vars[0].key == "NEW_VAR"
        assert result.env_vars[0].is_configured is True
        assert sample_workspace_db.env_vars == [
            {"key": "NEW_VAR", "value": "new_value"}
        ]
        mock_db_session.commit.assert_called_once()


# ============================================================================
# Workspace List Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceList:
    """Workspace List Tests"""

    def test_list_workspaces_success(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Successfully List Workspaces"""
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
        assert result.items[0].runtime_url == "/workspaces/workspace-123/runtime"
        assert "runtimeExternalUrl" not in result.items[0].model_dump(by_alias=True)
        assert result.pagination.total == 1
        assert result.pagination.page == 1

    def test_list_workspaces_with_owner_filter(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Filter Workspace List by Owner"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(page=1, page_size=10, owner_id="user-123")

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_with_status_filter(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Filter Workspace List by Status"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(page=1, page_size=10, status="running")

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_with_search(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: Search Workspaces"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_workspace_db]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 1

        # Act
        result = workspace_service.list(page=1, page_size=10, search="Test")

        # Assert
        assert result is not None
        assert len(result.items) == 1

    def test_list_workspaces_empty(self, workspace_service, mock_db_session):
        """Test: Empty Workspace List"""
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

    def test_list_workspaces_returns_persisted_records_without_external_io(
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
        docker_workspace.agentic_tools = ["claude-code"]
        _apply_workspace_defaults(docker_workspace, owner=docker_owner)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            kubernetes_workspace,
            docker_workspace,
        ]
        mock_db_session.execute.return_value = mock_result
        mock_db_session.scalar.return_value = 2

        result = workspace_service.list(page=1, page_size=10)

        assert len(result.items) == 2
        mock_db_session.commit.assert_not_called()


# ============================================================================
# Workspace Lifecycle Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceLifecycle:
    """Workspace Lifecycle Tests"""

    def test_to_detail_returns_firewall_available_for_docker_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        workspace_service.settings.CILIUM_ENABLED = False
        sample_workspace_db.workspace_firewall_egress_mode = "allowlist"
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_egress_mode = "allowlist"
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        result = workspace_service.get(
            "workspace-123",
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
        )

        assert result is not None
        assert result.firewall_available is True
        assert result.firewall_unavailable_reason is None
        assert result.firewall.workspace.allowed_domains == ["example.com"]
        assert result.firewall.browser.allowed_domains == ["browser.example.com"]

    def test_to_detail_returns_firewall_unavailable_for_kubernetes_when_cilium_disabled(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        workspace_service.settings.CILIUM_ENABLED = False
        sample_workspace_db.provisioner = "kubernetes"
        sample_workspace_db.workspace_firewall_egress_mode = "allowlist"
        sample_workspace_db.workspace_firewall_allowed_domains = ["example.com"]
        sample_workspace_db.browser_firewall_egress_mode = "allowlist"
        sample_workspace_db.browser_firewall_allowed_domains = ["browser.example.com"]
        mock_db_session.get.side_effect = _workspace_and_owner_get(sample_workspace_db)

        result = workspace_service.get(
            "workspace-123",
            actor=AuthorizationActor(sample_workspace_db.owner_id, "member"),
        )

        assert result is not None
        assert result.firewall_available is False
        assert result.firewall_unavailable_reason == "CILIUM_NOT_ENABLED"
        assert result.firewall.workspace.allowed_domains == ["example.com"]
        assert result.firewall.browser.allowed_domains == ["browser.example.com"]

    def test_to_detail_with_runtime_job(
        self, workspace_service, mock_db_session, sample_workspace_db
    ):
        """Test: _to_detail Includes Runtime Job"""
        # Arrange
        runtime_job = db_models.WorkspaceRuntimeJob(
            id="job-123",
            workspace_id="workspace-123",
            operation="workspace_start",
            strategy="docker",
            status="running",
            retries=0,
            scheduled_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            finished_at=None,
            correlation_id="correlation-123",
            root_correlation_id="correlation-123",
            job_metadata={},
            error_code=None,
        )
        sample_workspace_db.runtime_jobs = [runtime_job]

        # Act
        result = workspace_service._to_detail(
            sample_workspace_db,
            access_role="owner",
            access_source="owned",
            current_user_id=sample_workspace_db.owner_id,
        )

        # Assert
        assert result is not None
        assert result.runtime_job is not None
        assert result.runtime_job.id == "job-123"
        assert result.runtime_job.operation == "workspace_start"
        assert result.runtime_job.status == "running"

    def test_to_summary_and_detail_preserve_empty_agentic_tools(
        self, workspace_service, sample_workspace_db
    ):
        sample_workspace_db.agentic_tools = []

        summary = workspace_service._to_summary(
            sample_workspace_db,
            access_role="owner",
            access_source="owned",
            current_user_id=sample_workspace_db.owner_id,
        )
        detail = workspace_service._to_detail(
            sample_workspace_db,
            access_role="owner",
            access_source="owned",
            current_user_id=sample_workspace_db.owner_id,
        )

        assert summary.agentic_tools == []
        assert detail.agentic_tools == []

    def test_to_detail_includes_restart_metadata_from_runtime_jobs(
        self, workspace_service, sample_workspace_db
    ):
        scheduled_at = datetime.utcnow()
        browser_job = db_models.WorkspaceRuntimeJob(
            id="job-browser",
            workspace_id="workspace-123",
            operation="browser_restart",
            strategy="kubernetes",
            status="succeeded",
            retries=0,
            target_component="browser",
            scheduled_at=scheduled_at,
            started_at=scheduled_at,
            finished_at=scheduled_at,
            correlation_id="correlation-browser",
            root_correlation_id="correlation-browser",
            job_metadata={},
            error_code=None,
        )
        sample_workspace_db.runtime_jobs = [browser_job]

        result = workspace_service._to_detail(
            sample_workspace_db,
            access_role="owner",
            access_source="owned",
            current_user_id=sample_workspace_db.owner_id,
        )

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

        result = workspace_service._to_detail(
            sample_workspace_db,
            access_role="owner",
            access_source="owned",
            current_user_id=sample_workspace_db.owner_id,
        )

        assert result.components.runtime.last_restart_requested_at == created_at
        assert result.components.canvas.last_restart_requested_at == created_at


def test_update_share_downgrade_converges_principal_authorization(
    workspace_service, mock_db_session
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace"
    workspace.owner_id = "owner"
    share = Mock(spec=db_models.WorkspaceShare)
    share.id = "share"
    share.workspace_id = "workspace"
    share.target_type = "user"
    share.target_id = "principal"
    share.role = "manager"
    workspace_service._lock_workspace = Mock(return_value=workspace)
    workspace_service._lock_workspace_share = Mock(return_value=share)
    mock_db_session.get.return_value = workspace
    workspace_service._reload_share = Mock(return_value=share)
    workspace_service._record_access_reduction = Mock(
        return_value=["running-cancellation"]
    )
    workspace_service._cancel_automation_after_commit = Mock()

    workspace_service.update_share(
        "workspace",
        "share",
        WorkspaceShareUpdateRequest(role="reader"),
        actor=AuthorizationActor("owner", "member"),
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
    )

    workspace_service._record_access_reduction.assert_called_once_with(
        workspace=workspace,
        principal_user_id="principal",
        actor_user_id="owner",
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
        reason="workspace_share_downgraded",
    )
    mock_db_session.commit.assert_called_once_with()
    workspace_service._cancel_automation_after_commit.assert_called_once_with(
        ["running-cancellation"]
    )


def test_delete_share_converges_principal_authorization(
    workspace_service, mock_db_session
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace"
    workspace.owner_id = "owner"
    share = Mock(spec=db_models.WorkspaceShare)
    share.id = "share"
    share.workspace_id = "workspace"
    share.target_type = "user"
    share.target_id = "principal"
    share.role = "manager"
    workspace_service._lock_workspace = Mock(return_value=workspace)
    workspace_service._lock_workspace_share = Mock(return_value=share)
    mock_db_session.get.return_value = workspace
    workspace_service._record_access_reduction = Mock(
        return_value=["running-cancellation"]
    )
    workspace_service._cancel_automation_after_commit = Mock()

    assert workspace_service.delete_share(
        "workspace",
        "share",
        actor=AuthorizationActor("owner", "member"),
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
    )

    workspace_service._record_access_reduction.assert_called_once_with(
        workspace=workspace,
        principal_user_id="principal",
        actor_user_id="owner",
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
        reason="workspace_share_deleted",
    )
    mock_db_session.commit.assert_called_once_with()
    workspace_service._cancel_automation_after_commit.assert_called_once_with(
        ["running-cancellation"]
    )


@pytest.mark.parametrize(
    ("previous_role", "next_role"),
    [
        ("reader", "manager"),
    ],
)
def test_update_share_non_reducing_role_change_does_not_recycle_access(
    workspace_service,
    mock_db_session,
    previous_role: str,
    next_role: str,
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace"
    workspace.owner_id = "owner"
    share = Mock(spec=db_models.WorkspaceShare)
    share.id = "share"
    share.workspace_id = "workspace"
    share.target_type = "user"
    share.target_id = "principal"
    share.role = previous_role
    workspace_service._lock_workspace = Mock(return_value=workspace)
    workspace_service._lock_workspace_share = Mock(return_value=share)
    mock_db_session.get.return_value = workspace
    workspace_service._reload_share = Mock(return_value=share)
    workspace_service._record_access_reduction = Mock()
    workspace_service._cancel_automation_after_commit = Mock()

    workspace_service.update_share(
        "workspace",
        "share",
        WorkspaceShareUpdateRequest(role=next_role),
        actor=AuthorizationActor("owner", "member"),
        correlation_id="http-correlation",
        root_correlation_id="http-correlation",
    )

    workspace_service._record_access_reduction.assert_not_called()
    workspace_service._cancel_automation_after_commit.assert_called_once_with([])
    mock_db_session.commit.assert_called_once_with()


def test_share_recycle_commit_failure_rolls_back_without_runtime_cancel(
    workspace_service, mock_db_session
) -> None:
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace"
    workspace.owner_id = "owner"
    share = Mock(spec=db_models.WorkspaceShare)
    share.id = "share"
    share.workspace_id = "workspace"
    share.target_type = "user"
    share.target_id = "principal"
    share.role = "manager"
    workspace_service._lock_workspace = Mock(return_value=workspace)
    workspace_service._lock_workspace_share = Mock(return_value=share)
    mock_db_session.get.return_value = workspace
    workspace_service._reload_share = Mock(return_value=share)
    workspace_service._record_access_reduction = Mock(
        return_value=["running-cancellation"]
    )
    workspace_service._cancel_automation_after_commit = Mock()
    mock_db_session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        workspace_service.update_share(
            "workspace",
            "share",
            WorkspaceShareUpdateRequest(role="reader"),
            actor=AuthorizationActor("owner", "member"),
            correlation_id="http-correlation",
            root_correlation_id="http-correlation",
        )

    mock_db_session.rollback.assert_called_once_with()
    workspace_service._cancel_automation_after_commit.assert_not_called()
