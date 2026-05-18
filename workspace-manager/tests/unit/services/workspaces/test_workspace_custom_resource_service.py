"""WorkspaceCustomResourceService Unit Test"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml
from kubernetes.client.rest import ApiException

from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_settings(tmp_path: Path):
    settings = Mock()
    settings.RUNTIME_SCRIPT_ROOT = str(tmp_path)
    settings.RUNTIME_K8S_NAMESPACE = "workspace-system"
    settings.RUNTIME_K8S_CR_NAMESPACE = "aileron"
    settings.RUNTIME_K8S_IMAGE = "ailerondocker/workspace-runtime:latest"
    settings.RUNTIME_K8S_AGENT_STATE_PVC_NAME = "workspace-runtime-pvc"
    settings.RUNTIME_K8S_AGENT_STATE_SUB_PATH_ROOT = "agent-state"
    settings.RUNTIME_K8S_BROWSER_IMAGE = "ailerondocker/workspace-browser:latest"
    settings.RUNTIME_K8S_CANVAS_IMAGE = "ailerondocker/workspace-canvas:latest"
    settings.RUNTIME_K8S_RUNTIME_RESOURCES = {
        "requests": {"cpu": "500m", "memory": "2Gi"},
        "limits": {"cpu": "2000m", "memory": "4Gi"},
    }
    settings.RUNTIME_K8S_BROWSER_RESOURCES = {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "2000m", "memory": "2Gi"},
    }
    settings.RUNTIME_K8S_CANVAS_RESOURCES = {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "2000m", "memory": "2Gi"},
    }
    return settings


@pytest.fixture
def sample_workspace():
    workspace = Mock()
    workspace.id = "workspace-123"
    workspace.owner_id = "user-123"
    workspace.name = "Test Workspace"
    workspace.provisioner = "kubernetes"
    workspace.target_namespace = "team-a"
    workspace.runtime = "universal"
    workspace.git_url = "https://github.com/example/repo.git"
    workspace.branch = "main"
    workspace.workspace_path = "/workspace"
    workspace.env_vars = [{"key": "FOO", "value": "bar"}]
    workspace.runtime_resources = None
    workspace.workspace_firewall_network_access_enabled = True
    workspace.workspace_firewall_domain_access_mode = "specific"
    workspace.workspace_firewall_allowed_domains = ["example.com"]
    workspace.browser_firewall_network_access_enabled = False
    workspace.browser_firewall_domain_access_mode = "all"
    workspace.browser_firewall_allowed_domains = ["browser.example.com"]
    workspace.knowledge_base_attachments = []
    workspace.runtime_status = "starting"
    workspace.updated_at = datetime.utcnow()
    return workspace


@pytest.fixture
def custom_resource_service(mock_db_session, mock_settings):
    with patch(
        "app.services.workspace_custom_resource_service.get_settings",
        return_value=mock_settings,
    ):
        return WorkspaceCustomResourceService(mock_db_session)


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest(custom_resource_service, sample_workspace):
    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)

    assert manifest["kind"] == "Workspace"
    assert manifest["metadata"]["namespace"] == "aileron"
    assert manifest["spec"]["workspaceId"] == "workspace-123"
    assert manifest["spec"]["targetNamespace"] == "team-a"
    assert manifest["spec"]["runtime"]["image"] == "ailerondocker/workspace-runtime:latest"
    assert manifest["spec"]["runtime"]["imageKey"] == "universal"
    assert manifest["spec"]["runtime"]["resources"]["requests"]["cpu"] == "500m"
    assert manifest["spec"]["runtime"]["resources"]["limits"]["memory"] == "4Gi"
    assert manifest["spec"]["runtime"]["agentState"] == {
        "pvcName": "workspace-runtime-pvc",
        "subPathRoot": "agent-state",
        "mounts": [
            {
                "provider": "claude",
                "sourceSubPath": "agent-state/workspace_123/claude/home",
                "mountPath": "/home/developer/.claude",
            },
            {
                "provider": "codex",
                "sourceSubPath": "agent-state/workspace_123/codex/home",
                "mountPath": "/home/developer/.codex",
            },
            {
                "provider": "codex-sessions",
                "sourceSubPath": "agent-state/workspace_123/codex/sessions",
                "mountPath": "/home/developer/.codex-sessions",
            },
            {
                "provider": "gemini",
                "sourceSubPath": "agent-state/workspace_123/gemini/home",
                "mountPath": "/home/developer/.gemini",
            },
        ],
    }
    assert manifest["spec"]["browser"]["image"] == "ailerondocker/workspace-browser:latest"
    assert manifest["spec"]["browser"]["resources"]["limits"]["memory"] == "2Gi"
    assert manifest["spec"]["canvas"]["image"] == "ailerondocker/workspace-canvas:latest"
    assert manifest["spec"]["canvas"]["resources"]["requests"]["memory"] == "1Gi"
    assert "portMappings" not in manifest["spec"]
    assert manifest["spec"]["firewall"]["workspace"]["networkAccessEnabled"] is True
    assert manifest["spec"]["firewall"]["workspace"]["domainAccessMode"] == "specific"
    assert manifest["spec"]["firewall"]["workspace"]["allowedDomains"] == ["example.com"]
    assert manifest["spec"]["firewall"]["browser"]["networkAccessEnabled"] is False
    assert manifest["spec"]["firewall"]["browser"]["domainAccessMode"] == "all"
    assert manifest["spec"]["firewall"]["browser"]["allowedDomains"] == [
        "browser.example.com"
    ]
    assert manifest["spec"]["knowledgeBases"] == []


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest_includes_active_knowledge_bases(
    custom_resource_service, sample_workspace
):
    sample_workspace.knowledge_base_attachments = [
        Mock(
            kb_id="kb-1",
            mount_alias="docs",
            mode="rw",
            knowledge_base=Mock(id="kb-1", tombstoned_at=None),
        ),
        Mock(
            kb_id="kb-2",
            mount_alias="readonly-docs",
            mode="ro",
            knowledge_base=Mock(id="kb-2", tombstoned_at=None),
        ),
        Mock(
            kb_id="kb-3",
            mount_alias="deleted-docs",
            mode="ro",
            knowledge_base=Mock(id="kb-3", tombstoned_at=datetime.utcnow()),
        ),
    ]

    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)

    assert manifest["spec"]["knowledgeBases"] == [
        {"kbId": "kb-1", "mountAlias": "docs", "readOnly": False},
        {"kbId": "kb-2", "mountAlias": "readonly-docs", "readOnly": True},
    ]


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest_excludes_docker_specific_browser_webrtc_fields(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)

    browser_spec = manifest["spec"]["browser"]

    assert "hostPort" not in browser_spec
    assert "webrtcHostPort" not in browser_spec
    assert "nat1to1" not in browser_spec
    assert "environment" not in browser_spec


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest_prefers_runtime_override(
    custom_resource_service, sample_workspace
):
    sample_workspace.runtime_resources = {
        "requests": {"cpu": "750m", "memory": "3Gi"},
        "limits": {"cpu": "2500m", "memory": "5Gi"},
    }

    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)

    assert manifest["spec"]["runtime"]["resources"] == {
        "requests": {"cpu": "750m", "memory": "3Gi"},
        "limits": {"cpu": "2500m", "memory": "5Gi"},
    }


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_workspace_custom_resource_writes_manifest(
    custom_resource_service, mock_db_session, sample_workspace
):
    mock_db_session.get.side_effect = [sample_workspace]
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)

    with (
        patch.object(custom_resource_service, "_get_custom_objects_api", return_value=mock_api),
        patch.object(custom_resource_service, "_wait_for_status_sync", return_value=True) as mock_wait,
    ):
        custom_resource_service.apply_workspace_custom_resource("workspace-123")

    manifest_path = (
        Path(custom_resource_service.settings.RUNTIME_SCRIPT_ROOT)
        / "k8s-workspaces"
        / "aileron"
        / "workspace-123.yaml"
    )
    assert manifest_path.exists()
    content = manifest_path.read_text(encoding="utf-8")
    assert "kind: Workspace" in content
    assert "workspaceId: workspace-123" in content
    mock_api.create_namespaced_custom_object.assert_called_once()
    mock_api.patch_namespaced_custom_object.assert_not_called()
    mock_wait.assert_called_once_with("workspace-123")


@pytest.mark.unit
@pytest.mark.workspace
def test_delete_workspace_custom_resource_removes_manifest(
    custom_resource_service, mock_db_session, sample_workspace
):
    mock_db_session.get.side_effect = [sample_workspace]
    with patch.object(custom_resource_service, "_apply_manifest_to_cluster"):
        custom_resource_service.apply_workspace_custom_resource("workspace-123")
    mock_db_session.get.reset_mock()
    mock_db_session.get.side_effect = [sample_workspace]

    manifest_path = (
        Path(custom_resource_service.settings.RUNTIME_SCRIPT_ROOT)
        / "k8s-workspaces"
        / "aileron"
        / "workspace-123.yaml"
    )
    assert manifest_path.exists()

    with patch.object(custom_resource_service, "_delete_custom_resource_from_cluster") as mock_delete:
        result = custom_resource_service.delete_workspace_custom_resource("workspace-123")

    assert result is True
    assert not manifest_path.exists()
    mock_db_session.delete.assert_called_once_with(sample_workspace)
    mock_delete.assert_called_once_with(sample_workspace)


@pytest.mark.unit
@pytest.mark.workspace
def test_request_workspace_restart_updates_manifest_operations(
    custom_resource_service, mock_db_session, sample_workspace
):
    mock_db_session.get.side_effect = [sample_workspace]
    with patch.object(custom_resource_service, "_apply_manifest_to_cluster"):
        custom_resource_service.apply_workspace_custom_resource("workspace-123")

    mock_db_session.get.reset_mock()
    mock_db_session.get.side_effect = [sample_workspace]

    with patch.object(custom_resource_service, "_apply_manifest_to_cluster") as mock_apply:
        custom_resource_service.request_workspace_restart("workspace-123")

    manifest_path = (
        Path(custom_resource_service.settings.RUNTIME_SCRIPT_ROOT)
        / "k8s-workspaces"
        / "aileron"
        / "workspace-123.yaml"
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    operations = manifest["spec"]["operations"]

    assert operations["restartWorkspaceAt"]
    assert operations["restartRuntimeAt"]
    assert operations["restartBrowserAt"]
    assert operations["restartCanvasAt"]
    mock_apply.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_request_browser_restart_updates_only_browser_operation(
    custom_resource_service, mock_db_session, sample_workspace
):
    mock_db_session.get.side_effect = [sample_workspace]
    with patch.object(custom_resource_service, "_apply_manifest_to_cluster"):
        custom_resource_service.apply_workspace_custom_resource("workspace-123")

    mock_db_session.get.reset_mock()
    mock_db_session.get.side_effect = [sample_workspace]

    with patch.object(custom_resource_service, "_apply_manifest_to_cluster") as mock_apply:
        custom_resource_service.request_browser_restart("workspace-123")

    manifest_path = (
        Path(custom_resource_service.settings.RUNTIME_SCRIPT_ROOT)
        / "k8s-workspaces"
        / "aileron"
        / "workspace-123.yaml"
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    operations = manifest["spec"]["operations"]

    assert operations["restartBrowserAt"]
    assert "restartWorkspaceAt" not in operations
    assert "restartRuntimeAt" not in operations
    assert "restartCanvasAt" not in operations
    mock_apply.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_manifest_to_cluster_patches_existing_custom_resource(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)
    mock_api = MagicMock()

    with patch.object(custom_resource_service, "_get_custom_objects_api", return_value=mock_api):
        custom_resource_service._apply_manifest_to_cluster(manifest)

    mock_api.get_namespaced_custom_object.assert_called_once()
    mock_api.patch_namespaced_custom_object.assert_called_once()
    mock_api.create_namespaced_custom_object.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_manifest_to_cluster_creates_missing_custom_resource(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(sample_workspace)
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)

    with patch.object(custom_resource_service, "_get_custom_objects_api", return_value=mock_api):
        custom_resource_service._apply_manifest_to_cluster(manifest)

    mock_api.create_namespaced_custom_object.assert_called_once()
    mock_api.patch_namespaced_custom_object.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_sync_workspace_record_status_persists_internal_and_external_urls(
    custom_resource_service, sample_workspace
):
    sample_workspace.runtime_internal_url = None
    sample_workspace.runtime_external_url = None
    sample_workspace.browser_status = "starting"
    sample_workspace.browser_webrtc_internal_url = None
    sample_workspace.browser_webrtc_external_url = None
    sample_workspace.canvas_status = "starting"
    sample_workspace.canvas_internal_url = None
    sample_workspace.canvas_external_url = None
    sample_workspace.canvas_internal_url = None
    sample_workspace.canvas_external_url = None
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "status": {
            "phase": "Running",
            "components": {
                "runtime": {
                    "phase": "Running",
                    "internalUrl": "http://workspace-runtime-123.team-a.svc.cluster.local:3002",
                    "externalUrl": "https://workspace-runtime-workspace-123.example.com",
                },
                "browser": {
                    "phase": "Running",
                    "internalUrl": "http://workspace-browser-123.team-a.svc.cluster.local:6080",
                    "externalUrl": "https://workspace-browser-workspace-123.example.com",
                },
                "canvas": {
                    "phase": "Disabled",
                    "internalUrl": "http://workspace-canvas-123.team-a.svc.cluster.local:3003",
                    "externalUrl": "https://workspace-canvas-workspace-123.example.com",
                },
            },
        }
    }

    with patch.object(custom_resource_service, "_get_custom_objects_api", return_value=mock_api):
        changed = custom_resource_service.sync_workspace_record_status(sample_workspace)

    assert changed is True
    assert sample_workspace.runtime_status == "running"
    assert sample_workspace.runtime_internal_url == (
        "http://workspace-runtime-123.team-a.svc.cluster.local:3002"
    )
    assert sample_workspace.runtime_external_url == (
        "https://workspace-runtime-workspace-123.example.com"
    )
    assert sample_workspace.runtime_internal_port == 3002
    assert sample_workspace.runtime_external_port is None
    assert sample_workspace.browser_status == "running"
    assert sample_workspace.browser_webrtc_internal_url == (
        "http://workspace-browser-123.team-a.svc.cluster.local:6080"
    )
    assert sample_workspace.browser_webrtc_external_url == (
        "https://workspace-browser-workspace-123.example.com"
    )
    assert sample_workspace.canvas_status == "stopped"
    assert sample_workspace.canvas_internal_url == (
        "http://workspace-canvas-123.team-a.svc.cluster.local:3003"
    )
    assert sample_workspace.canvas_external_url == (
        "https://workspace-canvas-workspace-123.example.com"
    )
    assert sample_workspace.canvas_internal_url == sample_workspace.canvas_internal_url
    assert sample_workspace.canvas_external_url == sample_workspace.canvas_external_url
    custom_resource_service.db.commit.assert_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_sync_default_workspace_record_status_uses_control_plane_urls(
    custom_resource_service,
):
    workspace = Mock()
    workspace.id = "default-workspace"
    workspace.owner_id = "admin-user-default"
    workspace.name = "Default Workspace"
    workspace.provisioner = "kubernetes"
    workspace.target_namespace = "workspace-system"
    workspace.runtime_status = "starting"
    workspace.runtime_internal_url = None
    workspace.runtime_external_url = None
    workspace.runtime_internal_port = 3002
    workspace.runtime_external_port = None
    workspace.browser_status = "starting"
    workspace.browser_webrtc_internal_url = None
    workspace.browser_webrtc_external_url = None
    workspace.browser_webrtc_internal_port = 6080
    workspace.browser_webrtc_external_port = None
    workspace.canvas_status = "starting"
    workspace.canvas_internal_url = None
    workspace.canvas_external_url = None
    workspace.canvas_internal_port = 3003
    workspace.canvas_external_port = None
    workspace.canvas_internal_url = None
    workspace.canvas_external_url = None
    workspace.canvas_internal_port = 3003
    workspace.canvas_external_port = None
    workspace.terminal_external_url = None
    workspace.terminal_external_port = None
    workspace.updated_at = datetime.utcnow()

    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "status": {
            "phase": "Running",
            "components": {
                "runtime": {
                    "phase": "Running",
                    "internalUrl": "http://workspace-runtime-default-workspace.workspace-system.svc.cluster.local:3002",
                    "externalUrl": "https://workspace-runtime-default-workspace.example.com",
                },
                "browser": {
                    "phase": "Running",
                    "internalUrl": "http://workspace-browser-default-workspace.workspace-system.svc.cluster.local:6080",
                    "externalUrl": "https://workspace-browser-default-workspace.example.com",
                },
                "canvas": {
                    "phase": "Running",
                    "internalUrl": "http://workspace-canvas-default-workspace.workspace-system.svc.cluster.local:3003",
                    "externalUrl": "https://workspace-canvas-default-workspace.example.com",
                },
            },
        }
    }

    with patch.object(custom_resource_service, "_get_custom_objects_api", return_value=mock_api):
        changed = custom_resource_service.sync_workspace_record_status(workspace)

    assert changed is True
    assert workspace.runtime_internal_url == (
        "http://workspace-runtime-default-workspace.workspace-system.svc.cluster.local:3002"
    )
    assert workspace.runtime_external_url == (
        "https://workspace-runtime-default-workspace.example.com"
    )
    assert workspace.browser_webrtc_internal_url == (
        "http://workspace-browser-default-workspace.workspace-system.svc.cluster.local:6080"
    )
    assert workspace.canvas_internal_url == (
        "http://workspace-canvas-default-workspace.workspace-system.svc.cluster.local:3003"
    )
    assert workspace.canvas_external_url == (
        "https://workspace-canvas-default-workspace.example.com"
    )
    assert workspace.terminal_external_url == (
        "https://workspace-runtime-default-workspace.example.com"
    )


@pytest.mark.unit
@pytest.mark.workspace
def test_wait_for_status_sync_retries_until_changed(custom_resource_service):
    with (
        patch.object(
            custom_resource_service,
            "sync_workspace_status",
            side_effect=[False, False, True],
        ) as mock_sync,
        patch("app.services.workspace_custom_resource_service.time.sleep") as mock_sleep,
    ):
        changed = custom_resource_service._wait_for_status_sync(
            "workspace-123",
            max_attempts=3,
            interval_seconds=0.01,
        )

    assert changed is True
    assert mock_sync.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.unit
@pytest.mark.workspace
def test_wait_for_status_sync_returns_false_after_timeout(custom_resource_service):
    with (
        patch.object(
            custom_resource_service,
            "sync_workspace_status",
            return_value=False,
        ) as mock_sync,
        patch("app.services.workspace_custom_resource_service.time.sleep") as mock_sleep,
    ):
        changed = custom_resource_service._wait_for_status_sync(
            "workspace-123",
            max_attempts=3,
            interval_seconds=0.01,
        )

    assert changed is False
    assert mock_sync.call_count == 3
    assert mock_sleep.call_count == 2
