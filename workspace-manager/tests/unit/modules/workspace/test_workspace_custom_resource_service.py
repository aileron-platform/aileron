"""WorkspaceCustomResourceService Unit Test"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from kubernetes.client.rest import ApiException

from app.db import models as db_models
from app.modules.platform_resource_capacity.models import (
    StorageDesired,
    WorkspaceStorageDesiredState,
)
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionIdentity,
    WorkspaceCustomResourceNotReadyError,
    WorkspaceCustomResourceService,
    WorkspaceCustomResourceStatusSnapshot,
    WorkspaceKnowledgeBasePreflightError,
    _storage_observation,
)
from app.modules.workspace.execution_plane import (
    activate_runtime_generation,
)
from app.modules.workspace.orchestrator.base import (
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from app.modules.workspace.runtime.database import RuntimeDatabaseCredential

RUNTIME_INSTANCE_ID = "11111111-1111-4111-8111-111111111111"
NEXT_RUNTIME_INSTANCE_ID = "22222222-2222-4222-8222-222222222222"
RUNTIME_SECRET_NAME = "workspace-runtime-db-test"
KNOWLEDGE_BASE_ID_1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
KNOWLEDGE_BASE_ID_2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
KNOWLEDGE_BASE_ID_3 = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
KNOWLEDGE_BASE_ID_4 = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
ATTACHMENT_ID_1 = "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ATTACHMENT_ID_2 = "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RUNTIME_IMAGE = "registry.example.com/aileron/runtime@sha256:" + ("1" * 64)
BROWSER_IMAGE = "registry.example.com/aileron/browser@sha256:" + ("2" * 64)
CANVAS_IMAGE = "registry.example.com/aileron/canvas@sha256:" + ("3" * 64)


@pytest.mark.unit
@pytest.mark.workspace
def test_storage_observation_accepts_only_stable_operator_error_codes() -> None:
    unknown = _storage_observation(
        {
            "workspaceData": {
                "allocatedBytes": 20,
                "observedRevision": 2,
                "expansionSupported": True,
                "errorCode": "ARBITRARY_OPERATOR_FAILURE",
            }
        }
    )
    stable = _storage_observation(
        {
            "workspaceData": {
                "allocatedBytes": 20,
                "observedRevision": 2,
                "expansionSupported": False,
                "errorCode": "STORAGE_CLASS_EXPANSION_UNSUPPORTED",
            }
        }
    )

    assert unknown.items == ()
    assert len(stable.items) == 1
    assert stable.items[0].error_code == "STORAGE_CLASS_EXPANSION_UNSUPPORTED"


def _current_custom_resource(
    workspace,
    *,
    phase: str,
    components: dict,
) -> dict:
    current_components = dict(components)
    current_components["runtime"] = {
        "observedRevision": 1,
        "mountObservedRevision": workspace.knowledge_base_mount_desired_revision,
        "accessObservedRevision": workspace.runtime_access_revision,
        **current_components.get("runtime", {}),
    }
    return {
        "metadata": {"generation": 5},
        "spec": {
            "runtime": {
                "instanceId": workspace.runtime_instance_id,
                "revision": 1,
            }
        },
        "status": {
            "observedGeneration": 5,
            "phase": phase,
            "components": current_components,
        },
    }


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
    settings.WORKSPACE_STORAGE_SIZE = "20Gi"
    settings.RUNTIME_HOME_STORAGE_SIZE = "2Gi"
    settings.KNOWLEDGE_BASES_PVC_NAME = "knowledge-bases-pvc"
    settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS = 5
    settings.RUNTIME_K8S_IMAGE = RUNTIME_IMAGE
    settings.RUNTIME_ASSERTION_ISSUER = "workspace-manager"
    settings.RUNTIME_ASSERTION_PUBLIC_KEY_SET_SECRET_NAME = (
        "runtime-assertion-public-jwks"
    )
    settings.RUNTIME_K8S_BROWSER_IMAGE = BROWSER_IMAGE
    settings.RUNTIME_K8S_CANVAS_IMAGE = CANVAS_IMAGE
    settings.RUNTIME_K8S_RUNTIME_RESOURCES = {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "2000m", "memory": "3Gi"},
    }
    settings.RUNTIME_K8S_BROWSER_RESOURCES = {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "2000m", "memory": "2Gi"},
    }
    settings.RUNTIME_K8S_CANVAS_RESOURCES = {
        "requests": {"cpu": "100m", "memory": "1Gi"},
        "limits": {"cpu": "1000m", "memory": "2Gi"},
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
    workspace.worktree_subdir = ".worktrees"
    workspace.env_vars = [{"key": "FOO", "value": "bar"}]
    workspace.workspace_firewall_egress_mode = "allowlist"
    workspace.workspace_firewall_allowed_domains = ["example.com"]
    workspace.browser_firewall_egress_mode = "blocked"
    workspace.browser_firewall_allowed_domains = []
    workspace.firewall_revision = 4
    workspace.firewall_observed_revision = 3
    workspace.firewall_sync_status = "applying"
    workspace.firewall_error_code = None
    workspace.firewall_target_delivery_id = "delivery-8"
    workspace.knowledge_base_attachments = []
    workspace.bootstrap_revision = 1
    workspace.bootstrap_observed_revision = 0
    workspace.bootstrap_status = "pending"
    workspace.bootstrap_error_code = None
    workspace.bootstrap_last_transition_at = None
    workspace.runtime_desired_state = "running"
    workspace.runtime_desired_revision = 1
    workspace.runtime_observed_revision = 0
    workspace.runtime_reason = None
    workspace.runtime_error_code = None
    workspace.runtime_last_transition_at = None
    workspace.runtime_status = "starting"
    workspace.runtime_instance_id = RUNTIME_INSTANCE_ID
    workspace.browser_instance_id = RUNTIME_INSTANCE_ID
    workspace.canvas_instance_id = RUNTIME_INSTANCE_ID
    workspace.runtime_control_instance_id = None
    workspace.runtime_control_token_hash = None
    workspace.runtime_container_id = "runtime-old"
    workspace.browser_container_id = "browser-old"
    workspace.browser_desired_state = "running"
    workspace.browser_desired_revision = 1
    workspace.browser_observed_revision = 0
    workspace.browser_reason = None
    workspace.browser_error_code = None
    workspace.browser_last_transition_at = None
    workspace.browser_credential_revision = 1
    workspace.browser_credential_key_id = "test-key-v1"
    workspace.browser_credential_algorithm = "hkdf-sha256-v1"
    workspace.canvas_container_id = "canvas-old"
    workspace.canvas_desired_state = "running"
    workspace.canvas_desired_revision = 1
    workspace.canvas_observed_revision = 0
    workspace.canvas_reason = None
    workspace.canvas_error_code = None
    workspace.canvas_last_transition_at = None
    workspace.knowledge_base_mount_active_revision = 6
    workspace.knowledge_base_mount_desired_revision = 7
    workspace.knowledge_base_mount_observed_revision = 6
    workspace.knowledge_base_mount_sync_status = "applying"
    workspace.knowledge_base_mount_active_snapshot = []
    workspace.knowledge_base_mount_candidate_snapshot = []
    workspace.knowledge_base_mount_failed_snapshot = None
    workspace.runtime_access_revision = 3
    workspace.runtime_access_observed_revision = 2
    workspace.updated_at = datetime.utcnow()
    return workspace


@pytest.fixture
def custom_resource_service(mock_db_session, mock_settings):
    database_service = Mock()
    database_service.prepare.return_value = RuntimeDatabaseCredential(
        workspace_id="workspace-123",
        runtime_instance_id=RUNTIME_INSTANCE_ID,
        schema_name="ws_test",
        role_name="wsr_test_generation",
        role_prefix="wsr_test_",
        password="scoped-password",
        database_url="postgresql://wsr_test_generation:scoped-password@postgres/aileron",
        secret_name=RUNTIME_SECRET_NAME,
    )
    with patch(
        "app.modules.workspace.custom_resources.get_settings",
        return_value=mock_settings,
    ):
        return WorkspaceCustomResourceService(
            mock_db_session,
            runtime_database_service=database_service,
        )


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )

    assert manifest["kind"] == "Workspace"
    assert manifest["metadata"]["namespace"] == "workspace-system"
    assert manifest["spec"]["workspaceId"] == "workspace-123"
    assert manifest["spec"]["targetNamespace"] == "workspace-system"
    assert manifest["spec"]["bootstrap"] == {"revision": 1}
    assert manifest["spec"]["runtime"]["instanceId"] == RUNTIME_INSTANCE_ID
    assert manifest["spec"]["runtime"]["mountRevision"] == 7
    assert manifest["spec"]["runtime"]["accessRevision"] == 3
    assert manifest["spec"]["runtime"]["revision"] == 1
    assert manifest["spec"]["runtime"]["desiredState"] == "Running"
    assert manifest["spec"]["browser"]["instanceId"] == RUNTIME_INSTANCE_ID
    assert manifest["spec"]["browser"]["revision"] == 1
    assert manifest["spec"]["canvas"]["instanceId"] == RUNTIME_INSTANCE_ID
    assert manifest["spec"]["canvas"]["revision"] == 1
    assert "imageKey" not in manifest["spec"]["runtime"]
    assert manifest["spec"]["runtime"]["image"] == RUNTIME_IMAGE
    assert manifest["spec"]["browser"]["image"] == BROWSER_IMAGE
    assert manifest["spec"]["canvas"]["image"] == CANVAS_IMAGE

    assert manifest["spec"]["runtime"]["resources"]["requests"]["cpu"] == "500m"
    assert manifest["spec"]["runtime"]["resources"]["requests"]["memory"] == "1Gi"
    assert manifest["spec"]["runtime"]["resources"]["limits"]["memory"] == "3Gi"
    assert manifest["spec"]["runtime"]["assertion"] == {
        "issuer": "workspace-manager",
        "publicKeySetSecretName": "runtime-assertion-public-jwks",
    }
    assert "privateKey" not in manifest["spec"]["runtime"]["assertion"]
    assert manifest["spec"]["runtime"]["runtimeSecretName"] == RUNTIME_SECRET_NAME
    assert "controlAssertion" not in manifest["spec"]["runtime"]
    assert "stateDatabaseSecretName" not in manifest["spec"]["runtime"]
    assert manifest["spec"]["worktreeSubdir"] == ".worktrees"
    assert manifest["spec"]["browser"]["resources"]["limits"]["memory"] == "2Gi"
    assert manifest["spec"]["canvas"]["resources"]["requests"]["cpu"] == "100m"
    assert manifest["spec"]["canvas"]["resources"]["limits"]["cpu"] == "1000m"
    assert "portMappings" not in manifest["spec"]
    assert manifest["spec"]["firewall"]["workspace"]["egressMode"] == "allowlist"
    assert manifest["spec"]["firewall"]["workspace"]["allowedDomains"] == [
        "example.com"
    ]
    assert manifest["spec"]["firewall"]["browser"]["egressMode"] == "blocked"
    assert manifest["spec"]["firewall"]["browser"]["allowedDomains"] == []
    assert manifest["spec"]["knowledgeBases"] == []
    assert "git" not in manifest["spec"]


@pytest.mark.unit
@pytest.mark.workspace
def test_new_workspace_manifest_initializes_mandatory_storage_allocations(
    custom_resource_service,
    sample_workspace,
    mock_db_session,
):
    mock_db_session.scalars.return_value.all.return_value = []

    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )

    assert manifest["spec"]["storage"] == {
        "workspaceData": {"capacityBytes": 20 * 1024**3, "revision": 1},
        "runtimeHome": {"capacityBytes": 2 * 1024**3, "revision": 1},
    }
    allocations = {
        call.args[0].storage_kind: call.args[0]
        for call in mock_db_session.add.call_args_list
        if isinstance(call.args[0], db_models.WorkspaceStorageAllocation)
    }
    assert set(allocations) == {"workspace_data", "runtime_home"}
    assert allocations["workspace_data"].desired_bytes == 20 * 1024**3
    assert allocations["runtime_home"].desired_bytes == 2 * 1024**3
    assert all(allocation.phase == "pending" for allocation in allocations.values())
    mock_db_session.flush.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_component_revision_patches_only_target_and_waits_for_observed(
    custom_resource_service,
    sample_workspace,
):
    sample_workspace.browser_desired_revision = 4
    sample_workspace.browser_credential_revision = 2
    api = MagicMock()
    api.get_namespaced_custom_object.return_value = {
        "status": {
            "components": {
                "browser": {
                    "observedInstanceId": RUNTIME_INSTANCE_ID,
                    "observedRevision": 4,
                    "credentialObservedRevision": 2,
                    "credentialObservedKeyId": "test-key-v1",
                    "credentialObservedAlgorithm": "hkdf-sha256-v1",
                    "phase": "Running",
                    "ready": True,
                }
            }
        }
    }

    with patch.object(
        custom_resource_service,
        "_get_custom_objects_api",
        return_value=api,
    ):
        custom_resource_service.apply_component_desired_revision(
            sample_workspace,
            component="browser",
            assert_claim=Mock(),
            max_attempts=1,
        )

    assert api.patch_namespaced_custom_object.call_args.kwargs["body"] == {
        "spec": {
            "browser": {
                "desiredState": "Running",
                "instanceId": RUNTIME_INSTANCE_ID,
                "revision": 4,
                "credentialSecretName": (
                    "workspace-browser-credential-workspace-123-r2"
                ),
                "credentialRevision": 2,
                "credentialKeyId": "test-key-v1",
                "credentialAlgorithm": "hkdf-sha256-v1",
            }
        }
    }


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_browser_component_revision_waits_for_credential_fence(
    custom_resource_service,
    sample_workspace,
):
    sample_workspace.browser_desired_revision = 4
    sample_workspace.browser_credential_revision = 2
    api = MagicMock()
    api.get_namespaced_custom_object.return_value = {
        "status": {
            "components": {
                "browser": {
                    "observedInstanceId": RUNTIME_INSTANCE_ID,
                    "observedRevision": 4,
                    "credentialObservedRevision": 1,
                    "credentialObservedKeyId": "test-key-v1",
                    "credentialObservedAlgorithm": "hkdf-sha256-v1",
                    "phase": "Running",
                    "ready": True,
                }
            }
        }
    }

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=api,
        ),
        pytest.raises(
            WorkspaceCustomResourceNotReadyError,
            match="Kubernetes browser revision did not become ready",
        ),
    ):
        custom_resource_service.apply_component_desired_revision(
            sample_workspace,
            component="browser",
            assert_claim=Mock(),
            max_attempts=1,
        )


@pytest.mark.unit
@pytest.mark.workspace
def test_knowledge_base_preflight_requires_bound_shared_pvc(
    custom_resource_service,
    sample_workspace,
):
    core_api = MagicMock()
    core_api.read_namespaced_persistent_volume_claim.return_value.status.phase = (
        "Pending"
    )

    with (
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
        pytest.raises(
            WorkspaceKnowledgeBasePreflightError,
            match="not bound",
        ),
    ):
        custom_resource_service.preflight_knowledge_base_mounts(sample_workspace)

    core_api.read_namespaced_persistent_volume_claim.assert_called_once_with(
        name="knowledge-bases-pvc",
        namespace="workspace-system",
    )


@pytest.mark.unit
@pytest.mark.workspace
@pytest.mark.parametrize(
    "stale_field",
    ["mountObservedRevision", "accessObservedRevision"],
)
def test_runtime_component_apply_requires_exact_full_plane_observed_evidence(
    custom_resource_service,
    sample_workspace,
    stale_field,
):
    plan = custom_resource_service.prepare_execution_plane(
        sample_workspace,
        runtime_instance_id=NEXT_RUNTIME_INSTANCE_ID,
    )
    runtime_status = {
        "observedInstanceId": plan.runtime_instance_id,
        "observedRevision": sample_workspace.runtime_desired_revision,
        "mountObservedRevision": plan.mount_revision,
        "accessObservedRevision": plan.access_revision,
        "phase": "Running",
        "ready": True,
        "terminalReady": True,
        "podUid": "runtime-pod-uid",
    }
    runtime_status[stale_field] -= 1
    api = MagicMock()
    api.get_namespaced_custom_object.return_value = {
        "spec": plan.manifest["spec"],
        "status": {
            "phase": "Running",
            "components": {
                "runtime": runtime_status,
                "browser": {
                    "observedInstanceId": plan.manifest["spec"]["browser"][
                        "instanceId"
                    ],
                    "observedRevision": sample_workspace.browser_desired_revision,
                    "phase": "Running",
                    "ready": True,
                    "podUid": "browser-pod-uid",
                },
                "canvas": {
                    "observedInstanceId": plan.manifest["spec"]["canvas"]["instanceId"],
                    "observedRevision": sample_workspace.canvas_desired_revision,
                    "phase": "Running",
                    "ready": True,
                    "podUid": "canvas-pod-uid",
                },
            },
        },
    }

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=api,
        ),
        patch.object(custom_resource_service, "_upsert_runtime_secret"),
        pytest.raises(
            WorkspaceCustomResourceNotReadyError,
            match="Kubernetes runtime revision did not become ready",
        ),
    ):
        custom_resource_service.apply_component_desired_revision(
            sample_workspace,
            component="runtime",
            runtime_plan=plan,
            assert_claim=Mock(),
            max_attempts=1,
        )


@pytest.mark.unit
@pytest.mark.workspace
@pytest.mark.parametrize(
    ("setting_name", "invalid_reference", "error_code"),
    [
        ("RUNTIME_K8S_IMAGE", "", "RUNTIME_IMAGE_REFERENCE_INVALID"),
        (
            "RUNTIME_K8S_IMAGE",
            "repository:latest",
            "RUNTIME_IMAGE_REFERENCE_INVALID",
        ),
        ("RUNTIME_K8S_BROWSER_IMAGE", "", "BROWSER_IMAGE_REFERENCE_INVALID"),
        (
            "RUNTIME_K8S_BROWSER_IMAGE",
            "repository:latest",
            "BROWSER_IMAGE_REFERENCE_INVALID",
        ),
        ("RUNTIME_K8S_CANVAS_IMAGE", "", "CANVAS_IMAGE_REFERENCE_INVALID"),
        (
            "RUNTIME_K8S_CANVAS_IMAGE",
            "repository:latest",
            "CANVAS_IMAGE_REFERENCE_INVALID",
        ),
    ],
)
def test_build_workspace_custom_resource_rejects_mutable_image_reference(
    custom_resource_service,
    sample_workspace,
    setting_name,
    invalid_reference,
    error_code,
):
    setattr(custom_resource_service.settings, setting_name, invalid_reference)

    with pytest.raises(ValueError, match=error_code):
        custom_resource_service._build_workspace_custom_resource(
            sample_workspace,
            runtime_secret_name=RUNTIME_SECRET_NAME,
        )


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest_uses_canonical_candidate_snapshot(
    custom_resource_service, sample_workspace
):
    sample_workspace.knowledge_base_mount_active_snapshot = []
    sample_workspace.knowledge_base_mount_candidate_snapshot = [
        {
            "attachmentId": ATTACHMENT_ID_1,
            "knowledgeBaseId": KNOWLEDGE_BASE_ID_1,
            "mountAlias": "docs",
            "attachedById": "user-123",
        },
        {
            "attachmentId": ATTACHMENT_ID_2,
            "knowledgeBaseId": KNOWLEDGE_BASE_ID_2,
            "mountAlias": "readonly-docs",
            "attachedById": None,
        },
    ]

    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )

    assert manifest["spec"]["knowledgeBases"] == [
        {"kbId": KNOWLEDGE_BASE_ID_1, "alias": "docs"},
        {"kbId": KNOWLEDGE_BASE_ID_2, "alias": "readonly-docs"},
    ]


@pytest.mark.unit
@pytest.mark.workspace
def test_execution_only_api_applies_full_generation_without_job_or_commit(
    custom_resource_service,
    mock_db_session,
    sample_workspace,
):
    plan = custom_resource_service.prepare_execution_plane(
        sample_workspace,
        runtime_instance_id=NEXT_RUNTIME_INSTANCE_ID,
    )
    assert plan.observed_mount_revision == 6
    assert plan.runtime_control_token not in str(plan.manifest)
    assert sample_workspace.runtime_control_instance_id == NEXT_RUNTIME_INSTANCE_ID
    assert len(sample_workspace.runtime_control_token_hash) == 64
    assert plan.runtime_control_token != sample_workspace.runtime_control_token_hash
    activate_runtime_generation(sample_workspace, plan)
    custom_resource = {
        "spec": plan.manifest["spec"],
        "status": {
            "phase": "Running",
            "components": {
                "runtime": {
                    "observedInstanceId": NEXT_RUNTIME_INSTANCE_ID,
                    "observedRevision": 1,
                    "mountObservedRevision": 7,
                    "accessObservedRevision": 3,
                    "phase": "Running",
                    "ready": True,
                    "terminalReady": True,
                    "podUid": "runtime-pod-uid",
                },
                "browser": {
                    "observedInstanceId": NEXT_RUNTIME_INSTANCE_ID,
                    "observedRevision": 1,
                    "phase": "Running",
                    "ready": True,
                    "podUid": "browser-pod-uid",
                },
                "canvas": {
                    "observedInstanceId": NEXT_RUNTIME_INSTANCE_ID,
                    "observedRevision": 1,
                    "phase": "Running",
                    "ready": True,
                    "podUid": "canvas-pod-uid",
                },
            },
        },
    }
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service, "_apply_manifest_to_cluster"
        ) as apply_manifest,
        patch.object(
            custom_resource_service, "_upsert_runtime_secret"
        ) as upsert_secret,
        patch.object(
            custom_resource_service,
            "_get_workspace_custom_resource",
            return_value=custom_resource,
        ),
    ):
        result = custom_resource_service.apply_execution_plane(
            plan,
            assert_claim=Mock(),
            max_attempts=1,
        )

    apply_manifest.assert_called_once_with(plan.manifest)
    upsert_secret.assert_called_once_with(
        credential=plan.database_credential,
        runtime_control_token=plan.runtime_control_token,
        setup_script=plan.setup_script,
    )
    assert result.runtime_pod_uid == "runtime-pod-uid"
    assert result.browser_pod_uid == "browser-pod-uid"
    assert result.canvas_pod_uid == "canvas-pod-uid"
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()

    custom_resource_service.apply_execution_plane_result(sample_workspace, result)

    assert sample_workspace.runtime_instance_id == NEXT_RUNTIME_INSTANCE_ID
    assert sample_workspace.runtime_container_id == "runtime-pod-uid"
    assert sample_workspace.browser_container_id == "browser-pod-uid"
    assert sample_workspace.canvas_container_id == "canvas-pod-uid"
    assert sample_workspace.knowledge_base_mount_observed_revision == 7
    assert sample_workspace.runtime_access_observed_revision == 3
    assert sample_workspace.terminal_internal_url == (
        "http://runtime-workspace-123.workspace-system.svc.cluster.local:3004"
    )
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_runtime_secret_contains_only_scoped_runtime_credentials(
    custom_resource_service,
):
    core_api = MagicMock()
    credential = custom_resource_service.runtime_database_service.prepare.return_value

    with patch.object(
        custom_resource_service,
        "_get_core_v1_api",
        return_value=core_api,
    ):
        custom_resource_service._upsert_runtime_secret(
            credential=credential,
            runtime_control_token="generation-token",
            setup_script="printf 'configured\\n'\n",
        )

    body = core_api.create_namespaced_secret.call_args.kwargs["body"]
    assert body.string_data == {
        "state-database-url": credential.database_url,
        "runtime-control-token": "generation-token",
        "custom-setup.sh": "printf 'configured\\n'\n",
    }
    assert "INTERNAL_API_TOKEN" not in str(body.string_data)
    assert "REDIS_URL" not in str(body.string_data)
    core_api.read_namespaced_secret.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_runtime_secret_patches_only_after_create_conflict(custom_resource_service):
    core_api = MagicMock()
    core_api.create_namespaced_secret.side_effect = ApiException(status=409)
    credential = custom_resource_service.runtime_database_service.prepare.return_value

    with patch.object(
        custom_resource_service,
        "_get_core_v1_api",
        return_value=core_api,
    ):
        custom_resource_service._upsert_runtime_secret(
            credential=credential,
            runtime_control_token="generation-token",
            setup_script="#!/bin/sh\nexit 0\n",
        )

    core_api.patch_namespaced_secret.assert_called_once_with(
        name=credential.secret_name,
        namespace="workspace-system",
        body=core_api.create_namespaced_secret.call_args.kwargs["body"],
    )
    core_api.read_namespaced_secret.assert_not_called()


def _execution_identity() -> WorkspaceCustomResourceExecutionIdentity:
    return WorkspaceCustomResourceExecutionIdentity(
        workspace_id="workspace-123",
        target_namespace="workspace-system",
        runtime_instance_id=RUNTIME_INSTANCE_ID,
        runtime_pod_uid="runtime-pod-uid",
        browser_pod_uid="browser-pod-uid",
        canvas_pod_uid="canvas-pod-uid",
    )


def _stopped_execution_identity() -> WorkspaceCustomResourceExecutionIdentity:
    return WorkspaceCustomResourceExecutionIdentity(
        workspace_id="workspace-123",
        target_namespace="workspace-system",
        runtime_instance_id=None,
        runtime_pod_uid=None,
        browser_pod_uid=None,
        canvas_pod_uid=None,
    )


@pytest.mark.unit
@pytest.mark.workspace
def test_abandon_accepts_missing_cr_and_proves_old_pods_absent(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    custom_api.get_namespaced_custom_object.side_effect = ApiException(status=404)
    core_api = MagicMock()
    core_api.list_namespaced_pod.side_effect = [
        Mock(
            items=[
                Mock(metadata=Mock(uid="runtime-pod-uid")),
                Mock(metadata=Mock(uid="browser-pod-uid")),
            ]
        ),
        Mock(items=[]),
    ]
    assert_claim = Mock()
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
        patch("app.modules.workspace.custom_resources.time.sleep") as sleep,
    ):
        custom_resource_service.abandon_execution_plane_generation(
            _execution_identity(),
            assert_claim=assert_claim,
            max_attempts=2,
            interval_seconds=0.01,
        )

    custom_api.get_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
    )
    custom_api.delete_namespaced_custom_object.assert_not_called()
    custom_api.patch_namespaced_custom_object.assert_not_called()
    assert core_api.list_namespaced_pod.call_count == 2
    core_api.list_namespaced_pod.assert_called_with(
        namespace="workspace-system",
        label_selector="aileron.io/workspace-id=workspace-123",
    )
    sleep.assert_called_once_with(0.01)
    assert assert_claim.call_count >= 6
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_abandon_cas_stops_only_matching_runtime_generation(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {
            "uid": "workspace-cr-uid",
            "resourceVersion": "42",
        },
        "spec": {"runtime": {"instanceId": RUNTIME_INSTANCE_ID}},
    }
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(items=[])
    assert_claim = Mock()
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
    ):
        custom_resource_service.abandon_execution_plane_generation(
            _execution_identity(),
            assert_claim=assert_claim,
            max_attempts=1,
        )

    custom_api.patch_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
        body={
            "metadata": {"resourceVersion": "42"},
            "spec": {
                "runtime": {"desiredState": "Stopped"},
                "browser": {"desiredState": "Stopped"},
                "canvas": {"desiredState": "Stopped"},
            },
        },
    )
    custom_api.delete_namespaced_custom_object.assert_not_called()
    core_api.list_namespaced_pod.assert_called_once_with(
        namespace="workspace-system",
        label_selector="aileron.io/workspace-id=workspace-123",
    )
    assert assert_claim.call_count >= 6
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_abandon_does_not_stop_replaced_generation(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {"uid": "new-cr-uid", "resourceVersion": "43"},
        "spec": {"runtime": {"instanceId": NEXT_RUNTIME_INSTANCE_ID}},
    }
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(items=[])
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
    ):
        custom_resource_service.abandon_execution_plane_generation(
            _execution_identity(),
            assert_claim=Mock(),
            max_attempts=1,
        )

    custom_api.patch_namespaced_custom_object.assert_not_called()
    custom_api.delete_namespaced_custom_object.assert_not_called()
    core_api.list_namespaced_pod.assert_called_once()
    custom_resource_service.runtime_database_service.prepare.assert_called_once()
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_abandon_fails_closed_when_stop_precondition_conflicts(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {
            "uid": "workspace-cr-uid",
            "resourceVersion": "42",
        },
        "spec": {"runtime": {"instanceId": RUNTIME_INSTANCE_ID}},
    }
    custom_api.patch_namespaced_custom_object.side_effect = ApiException(status=409)
    core_api = MagicMock()
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
        pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError) as exc_info,
    ):
        custom_resource_service.abandon_execution_plane_generation(
            _execution_identity(),
            assert_claim=Mock(),
            max_attempts=1,
        )

    assert exc_info.value.code == "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"
    custom_api.patch_namespaced_custom_object.assert_called_once()
    custom_api.delete_namespaced_custom_object.assert_not_called()
    core_api.assert_not_called()
    custom_resource_service.runtime_database_service.prepare.assert_not_called()
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_failed_apply_stops_candidate_without_deleting_workspace(
    custom_resource_service,
    sample_workspace,
):
    plan = custom_resource_service.prepare_execution_plane(
        sample_workspace,
        runtime_instance_id=NEXT_RUNTIME_INSTANCE_ID,
    )
    with (
        patch.object(
            custom_resource_service,
            "_apply_manifest_to_cluster",
            side_effect=RuntimeError("apply failed"),
        ),
        patch.object(custom_resource_service, "_upsert_runtime_secret"),
        patch.object(
            custom_resource_service,
            "abandon_execution_plane_generation",
        ) as abandon,
        pytest.raises(RuntimeError, match="apply failed"),
    ):
        custom_resource_service.apply_execution_plane(
            plan,
            assert_claim=Mock(),
            max_attempts=1,
        )

    identity = abandon.call_args.args[0]
    assert identity.workspace_id == plan.workspace_id
    assert identity.runtime_instance_id == plan.runtime_instance_id
    abandon.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_stop_persisted_workspace_revokes_generation_but_preserves_storage(
    custom_resource_service,
    sample_workspace,
):
    with patch.object(
        custom_resource_service,
        "abandon_execution_plane_generation",
    ) as abandon:
        custom_resource_service.stop_persisted_execution_plane(
            sample_workspace,
            assert_claim=Mock(),
        )

    identity = abandon.call_args.args[0]
    assert identity.workspace_id == sample_workspace.id
    assert identity.runtime_instance_id == sample_workspace.runtime_instance_id
    assert identity.runtime_pod_uid == sample_workspace.runtime_container_id
    assert identity.browser_pod_uid == sample_workspace.browser_container_id
    assert identity.canvas_pod_uid == sample_workspace.canvas_container_id


@pytest.mark.unit
@pytest.mark.workspace
def test_prove_execution_plane_absent_times_out_with_stable_error(
    custom_resource_service,
    mock_db_session,
):
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(
        items=[
            Mock(metadata=Mock(uid="runtime-pod-uid")),
            Mock(metadata=Mock(uid="browser-pod-uid")),
            Mock(metadata=Mock(uid="canvas-pod-uid")),
        ]
    )
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
        patch("app.modules.workspace.custom_resources.time.sleep"),
        pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError) as exc_info,
    ):
        custom_resource_service.prove_execution_plane_absent(
            _execution_identity(),
            assert_claim=Mock(),
            max_attempts=2,
            interval_seconds=0.01,
        )

    assert exc_info.value.code == "WORKSPACE_RUNTIME_TERMINATION_UNCONFIRMED"
    assert core_api.list_namespaced_pod.call_count == 2
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.flush.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_delete_persisted_stopped_workspace_deletes_cr_and_waits_for_finalizer(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    custom_api.get_namespaced_custom_object.side_effect = [
        {
            "metadata": {
                "uid": "workspace-cr-uid",
                "resourceVersion": "42",
            },
            "spec": {"runtime": {"instanceId": RUNTIME_INSTANCE_ID}},
        },
        ApiException(status=404),
    ]
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(items=[])
    assert_claim = Mock()
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
    ):
        custom_resource_service.delete_persisted_workspace(
            _stopped_execution_identity(),
            assert_claim=assert_claim,
            max_attempts=1,
        )

    custom_api.delete_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
        body={
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {
                "uid": "workspace-cr-uid",
                "resourceVersion": "42",
            },
        },
    )
    assert custom_api.get_namespaced_custom_object.call_count == 2
    custom_api.get_namespaced_custom_object.assert_called_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
    )
    core_api.list_namespaced_pod.assert_called_once_with(
        namespace="workspace-system",
        label_selector="aileron.io/workspace-id=workspace-123",
    )
    assert assert_claim.call_count >= 6
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_prove_execution_plane_absent_accepts_disabled_component_identity(
    custom_resource_service,
    mock_db_session,
):
    identity = WorkspaceCustomResourceExecutionIdentity(
        workspace_id="workspace-123",
        target_namespace="workspace-system",
        runtime_instance_id=RUNTIME_INSTANCE_ID,
        runtime_pod_uid="runtime-pod-uid",
        browser_pod_uid=None,
        canvas_pod_uid="canvas-pod-uid",
    )
    custom_api = MagicMock()
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(items=[])
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
    ):
        custom_resource_service.prove_execution_plane_absent(
            identity,
            assert_claim=Mock(),
            max_attempts=1,
        )

    custom_api.assert_not_called()
    core_api.list_namespaced_pod.assert_called_once()
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_prove_workspace_pods_absent_preserves_custom_resource(
    custom_resource_service,
    mock_db_session,
):
    custom_api = MagicMock()
    core_api = MagicMock()
    core_api.list_namespaced_pod.return_value = Mock(items=[])
    assert_claim = Mock()
    mock_db_session.reset_mock()

    with (
        patch.object(
            custom_resource_service,
            "_get_custom_objects_api",
            return_value=custom_api,
        ),
        patch.object(
            custom_resource_service,
            "_get_core_v1_api",
            return_value=core_api,
        ),
    ):
        custom_resource_service.prove_workspace_pods_absent(
            workspace_id="workspace-123",
            assert_claim=assert_claim,
            max_attempts=1,
        )

    custom_api.assert_not_called()
    core_api.list_namespaced_pod.assert_called_once_with(
        namespace="workspace-system",
        label_selector="aileron.io/workspace-id=workspace-123",
    )
    assert assert_claim.call_count == 2
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_build_workspace_custom_resource_manifest_excludes_docker_specific_browser_webrtc_fields(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )

    browser_spec = manifest["spec"]["browser"]

    assert "hostPort" not in browser_spec
    assert "webrtcHostPort" not in browser_spec
    assert "nat1to1" not in browser_spec
    assert "environment" not in browser_spec


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_firewall_spec_patches_delivery_identity_and_only_firewall_spec(
    custom_resource_service, sample_workspace
):
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "metadata": {"resourceVersion": "resource-version-7"}
    }

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        custom_resource_service.apply_firewall_spec(
            sample_workspace,
            delivery_id="delivery-8",
        )

    mock_api.patch_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
        body={
            "metadata": {
                "resourceVersion": "resource-version-7",
                "annotations": {
                    "platform.aileron.io/firewall-delivery-id": "delivery-8",
                },
            },
            "spec": {
                "firewall": {
                    "revision": 4,
                    "workspace": {
                        "egressMode": "allowlist",
                        "allowedDomains": ["example.com"],
                    },
                    "browser": {
                        "egressMode": "blocked",
                        "allowedDomains": [],
                    },
                }
            },
        },
        _request_timeout=5,
    )
    mock_api.get_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
        _request_timeout=5,
    )


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_storage_spec_patches_integer_bytes_only(
    custom_resource_service,
    sample_workspace,
    mock_db_session,
):
    mock_db_session.scalars.return_value.all.return_value = [
        db_models.WorkspaceStorageAllocation(
            workspace_id=sample_workspace.id,
            storage_kind="workspace_data",
            desired_bytes=25 * 1024**3,
            observed_bytes=20 * 1024**3,
            revision=2,
            phase="pending",
        ),
        db_models.WorkspaceStorageAllocation(
            workspace_id=sample_workspace.id,
            storage_kind="runtime_home",
            desired_bytes=4 * 1024**3,
            observed_bytes=2 * 1024**3,
            revision=2,
            phase="pending",
        ),
    ]
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = {
        "metadata": {"resourceVersion": "resource-version-storage"}
    }

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        custom_resource_service.apply_storage_spec(
            sample_workspace,
            storage_spec=WorkspaceStorageDesiredState(
                workspace_data=StorageDesired(
                    storage_kind="workspace_data",
                    capacity_bytes=25 * 1024**3,
                    revision=2,
                ),
                runtime_home=StorageDesired(
                    storage_kind="runtime_home",
                    capacity_bytes=4 * 1024**3,
                    revision=2,
                ),
            ),
        )

    body = mock_api.patch_namespaced_custom_object.call_args.kwargs["body"]
    assert body == {
        "metadata": {"resourceVersion": "resource-version-storage"},
        "spec": {
            "storage": {
                "workspaceData": {
                    "capacityBytes": 25 * 1024**3,
                    "revision": 2,
                },
                "runtimeHome": {
                    "capacityBytes": 4 * 1024**3,
                    "revision": 2,
                },
            }
        },
    }


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_manifest_to_cluster_patches_existing_custom_resource(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )
    mock_api = MagicMock()

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        custom_resource_service._apply_manifest_to_cluster(manifest)

    mock_api.get_namespaced_custom_object.assert_called_once()
    mock_api.patch_namespaced_custom_object.assert_called_once()
    mock_api.create_namespaced_custom_object.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_manifest_to_cluster_creates_missing_custom_resource(
    custom_resource_service, sample_workspace
):
    manifest = custom_resource_service._build_workspace_custom_resource(
        sample_workspace,
        runtime_secret_name=RUNTIME_SECRET_NAME,
    )
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.side_effect = ApiException(status=404)

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        custom_resource_service._apply_manifest_to_cluster(manifest)

    mock_api.create_namespaced_custom_object.assert_called_once()
    mock_api.patch_namespaced_custom_object.assert_not_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_derives_adapter_internal_urls(
    custom_resource_service, sample_workspace
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.runtime_internal_url = None
    sample_workspace.browser_status = "running"
    sample_workspace.browser_webrtc_internal_url = None
    sample_workspace.canvas_status = "stopped"
    sample_workspace.canvas_internal_url = None
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
            },
            "browser": {
                "phase": "Running",
            },
            "canvas": {
                "phase": "Disabled",
            },
        },
    )

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            sample_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    mock_api.get_namespaced_custom_object.assert_called_once_with(
        group="platform.aileron.io",
        version="v1alpha1",
        namespace="workspace-system",
        plural="workspaces",
        name="workspace-workspace-123",
        _request_timeout=5,
    )
    assert sample_workspace.runtime_status == "running"
    assert sample_workspace.runtime_internal_url == (
        "http://runtime-workspace-123.workspace-system.svc.cluster.local:3002"
    )
    assert sample_workspace.runtime_internal_port == 3002
    assert sample_workspace.browser_status == "running"
    assert sample_workspace.browser_webrtc_internal_url == (
        "http://browser-workspace-123.workspace-system.svc.cluster.local:6080"
    )
    assert sample_workspace.canvas_status == "stopped"
    assert sample_workspace.canvas_internal_url == (
        "http://canvas-workspace-123.workspace-system.svc.cluster.local:3003"
    )
    custom_resource_service.db.commit.assert_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_projects_browser_connectivity_evidence(
    custom_resource_service, sample_workspace
):
    custom_resource_service.db.get.return_value = sample_workspace
    resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {"phase": "Running"},
            "browser": {"phase": "Running"},
            "canvas": {"phase": "Disabled"},
        },
    )
    resource["status"]["browserConnectivity"] = {
        "contractVersion": "browser-connectivity/v1",
        "state": "degraded",
        "admission": "allowed",
        "observedBrowserGeneration": "browser-generation-1",
        "profileRevision": "profile-7",
        "credentialRevision": "credential-9",
        "backendState": "ready",
        "backendAcceptedAt": "2026-08-05T01:02:00Z",
        "backendExpiresAt": "2026-08-05T01:03:30Z",
        "backendReason": "BackendTURNPathReady",
        "frontendState": "degraded",
        "frontendAcceptedAt": "2026-08-05T01:02:03Z",
        "frontendExpiresAt": "2026-08-05T01:03:33Z",
        "frontendReason": "FrontendTURNPathNotReady",
        "frontendErrorCode": "FRONTEND_TURN_PATH_NOT_READY",
        "acceptedAt": "2026-08-05T01:02:03Z",
        "expiresAt": "2026-08-05T01:03:33Z",
        "reason": "FrontendTURNPathNotReady",
        "errorCode": "FRONTEND_TURN_PATH_NOT_READY",
    }
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = resource

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            sample_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.browser_connectivity_state == "degraded"
    assert sample_workspace.browser_connectivity_admission == "allowed"
    assert sample_workspace.browser_connectivity_browser_generation == (
        "browser-generation-1"
    )
    assert sample_workspace.browser_connectivity_profile_revision == "profile-7"
    assert sample_workspace.browser_connectivity_credential_revision == "credential-9"
    assert sample_workspace.browser_connectivity_backend_state == "ready"
    assert sample_workspace.browser_connectivity_backend_accepted_at.isoformat() == (
        "2026-08-05T01:02:00+00:00"
    )
    assert sample_workspace.browser_connectivity_frontend_state == "degraded"
    assert sample_workspace.browser_connectivity_frontend_expires_at.isoformat() == (
        "2026-08-05T01:03:33+00:00"
    )
    assert sample_workspace.browser_connectivity_frontend_error_code == (
        "FRONTEND_TURN_PATH_NOT_READY"
    )
    assert sample_workspace.browser_connectivity_accepted_at.isoformat() == (
        "2026-08-05T01:02:03+00:00"
    )
    assert sample_workspace.browser_connectivity_expires_at.isoformat() == (
        "2026-08-05T01:03:33+00:00"
    )
    assert sample_workspace.browser_connectivity_reason == "FrontendTURNPathNotReady"
    assert sample_workspace.browser_connectivity_error_code == (
        "FRONTEND_TURN_PATH_NOT_READY"
    )


@pytest.mark.unit
@pytest.mark.workspace
def test_browser_connectivity_projection_rejects_inconsistent_admission(
    sample_workspace,
):
    sample_workspace.browser_connectivity_state = "ready"
    sample_workspace.browser_connectivity_admission = "allowed"

    WorkspaceCustomResourceService._apply_browser_connectivity_status(
        sample_workspace,
        {
            "contractVersion": "browser-connectivity/v1",
            "state": "pending",
            "admission": "allowed",
        },
    )

    assert sample_workspace.browser_connectivity_state == "unavailable"
    assert sample_workspace.browser_connectivity_admission == "denied"
    assert (
        sample_workspace.browser_connectivity_error_code
        == "BROWSER_CONNECTIVITY_CONTRACT_REJECTED"
    )


@pytest.mark.unit
@pytest.mark.workspace
@pytest.mark.parametrize(
    "durable_status",
    ["starting", "stopping", "restarting", "deleting", "error"],
)
def test_reconcile_workspace_status_preserves_durable_lifecycle_status(
    custom_resource_service,
    sample_workspace,
    durable_status,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = durable_status
    sample_workspace.runtime_internal_url = None
    sample_workspace.runtime_internal_port = None
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
            }
        },
    )

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            sample_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.runtime_status == durable_status
    assert sample_workspace.runtime_internal_url == (
        "http://runtime-workspace-123.workspace-system.svc.cluster.local:3002"
    )
    custom_resource_service.db.commit.assert_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_allows_stable_failure_convergence(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.runtime_internal_url = None
    sample_workspace.runtime_internal_port = None
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = _current_custom_resource(
        sample_workspace,
        phase="Failed",
        components={
            "runtime": {
                "phase": "Failed",
            }
        },
    )

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            sample_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.runtime_status == "error"
    custom_resource_service.db.commit.assert_called()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_heals_unowned_restarting_runtime(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    custom_resource_service.db.scalar.return_value = None
    sample_workspace.runtime_status = "restarting"
    sample_workspace.runtime_internal_url = None
    sample_workspace.runtime_internal_port = None
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["status"]["components"]["runtime"][
        "mountObservedRevision"
    ] = sample_workspace.knowledge_base_mount_observed_revision
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.runtime_status == "running"
    custom_resource_service.db.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_maps_degraded_firewall_to_stable_error(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["spec"]["firewall"] = {
        "revision": sample_workspace.firewall_revision,
    }
    custom_resource["metadata"]["annotations"] = {
        "platform.aileron.io/firewall-delivery-id": "delivery-8",
    }
    custom_resource["status"]["firewall"] = {
        "observedRevision": sample_workspace.firewall_revision,
        "phase": "Degraded",
        "errorCode": "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT",
        "targetDeliveryId": "delivery-8",
    }
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.firewall_sync_status == "error"
    assert sample_workspace.firewall_observed_revision == 3
    assert sample_workspace.firewall_error_code == "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT"
    custom_resource_service.db.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_ignores_stale_firewall_delivery_status(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["metadata"]["annotations"] = {
        "platform.aileron.io/firewall-delivery-id": "delivery-8",
    }
    custom_resource["spec"]["firewall"] = {
        "revision": sample_workspace.firewall_revision,
    }
    custom_resource["status"]["firewall"] = {
        "observedRevision": sample_workspace.firewall_revision,
        "phase": "Degraded",
        "errorCode": "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT",
        "targetDeliveryId": "delivery-7",
    }
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.firewall_sync_status == "applying"
    assert sample_workspace.firewall_observed_revision == 3
    assert sample_workspace.firewall_error_code is None


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_ignores_previous_delivery_after_retry_enqueue(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    sample_workspace.firewall_target_delivery_id = "delivery-B"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["metadata"]["annotations"] = {
        "platform.aileron.io/firewall-delivery-id": "delivery-A",
    }
    custom_resource["spec"]["firewall"] = {
        "revision": sample_workspace.firewall_revision,
    }
    custom_resource["status"]["firewall"] = {
        "observedRevision": sample_workspace.firewall_revision,
        "phase": "Degraded",
        "errorCode": "FIREWALL_POLICY_ENFORCEMENT_TIMEOUT",
        "targetDeliveryId": "delivery-A",
    }
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.firewall_sync_status == "applying"
    assert sample_workspace.firewall_observed_revision == 3
    assert sample_workspace.firewall_error_code is None


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_applies_matching_firewall_delivery(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["metadata"]["annotations"] = {
        "platform.aileron.io/firewall-delivery-id": "delivery-8",
    }
    custom_resource["spec"]["firewall"] = {
        "revision": sample_workspace.firewall_revision,
    }
    custom_resource["status"]["firewall"] = {
        "observedRevision": sample_workspace.firewall_revision,
        "phase": "Applied",
        "targetDeliveryId": "delivery-8",
    }
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.firewall_sync_status == "applied"
    assert sample_workspace.firewall_observed_revision == 4
    assert sample_workspace.firewall_error_code is None


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_ignores_firewall_before_command_delivery(
    custom_resource_service,
    sample_workspace,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.browser_status = "running"
    sample_workspace.canvas_status = "running"
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
                "ready": True,
                "terminalReady": True,
            }
        },
    )
    custom_resource["spec"]["firewall"] = {
        "revision": sample_workspace.firewall_revision,
    }
    custom_resource["status"]["firewall"] = {
        "observedRevision": sample_workspace.firewall_revision,
        "phase": "Applied",
    }
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource=custom_resource,
    )

    changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert sample_workspace.firewall_sync_status == "applying"
    assert sample_workspace.firewall_observed_revision == 3
    assert sample_workspace.firewall_error_code is None


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_refreshes_stale_orm_before_phase_guard(
    custom_resource_service,
    sample_workspace,
):
    stale_workspace = Mock(
        id=sample_workspace.id,
        provisioner="kubernetes",
        runtime_status="running",
        runtime_internal_url="http://stale-runtime:3002",
    )
    sample_workspace.runtime_status = "restarting"
    sample_workspace.runtime_internal_url = "http://current-runtime:3002"
    sample_workspace.runtime_internal_port = 3002
    events: list[str] = []

    def load_current(*_args, **_kwargs):
        events.append("row_lock")
        return sample_workspace

    custom_resource_service.db.get.side_effect = load_current
    mock_api = MagicMock()

    def load_status(**_kwargs):
        events.append("cr_status")
        return _current_custom_resource(
            sample_workspace,
            phase="Running",
            components={
                "runtime": {
                    "phase": "Running",
                }
            },
        )

    mock_api.get_namespaced_custom_object.side_effect = load_status
    with (
        patch(
            "app.modules.workspace.custom_resources.try_acquire_workspace_transaction_lock",
            return_value=True,
        ) as try_acquire_lock,
        patch.object(
            custom_resource_service, "_get_custom_objects_api", return_value=mock_api
        ),
    ):
        try_acquire_lock.side_effect = lambda *_args: (
            events.append("advisory_lock") or True
        )
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            stale_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert events == ["cr_status", "advisory_lock", "row_lock"]
    custom_resource_service.db.get.assert_called_once_with(
        db_models.Workspace,
        sample_workspace.id,
        populate_existing=True,
        with_for_update=True,
    )
    assert sample_workspace.runtime_status == "restarting"
    assert sample_workspace.runtime_internal_url == (
        "http://runtime-workspace-123.workspace-system.svc.cluster.local:3002"
    )
    assert stale_workspace.runtime_status == "running"
    assert stale_workspace.runtime_internal_url == "http://stale-runtime:3002"
    custom_resource_service.db.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
@pytest.mark.parametrize(
    ("stale_field", "stale_value"),
    [
        ("observed_generation", 4),
        ("runtime_instance_id", NEXT_RUNTIME_INSTANCE_ID),
    ],
)
def test_reconcile_workspace_status_ignores_stale_execution_status(
    custom_resource_service,
    sample_workspace,
    stale_field,
    stale_value,
):
    custom_resource_service.db.get.return_value = sample_workspace
    sample_workspace.runtime_status = "running"
    sample_workspace.runtime_internal_url = "http://current-runtime:3002"
    sample_workspace.runtime_internal_port = 3002
    original_updated_at = sample_workspace.updated_at
    custom_resource = _current_custom_resource(
        sample_workspace,
        phase="Failed",
        components={
            "runtime": {
                "phase": "Failed",
            }
        },
    )
    if stale_field == "observed_generation":
        custom_resource["status"]["observedGeneration"] = stale_value
    else:
        custom_resource["spec"]["runtime"]["instanceId"] = stale_value
    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = custom_resource

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(
            sample_workspace.id
        )
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is False
    assert sample_workspace.runtime_status == "running"
    assert sample_workspace.runtime_internal_url == "http://current-runtime:3002"
    assert sample_workspace.updated_at == original_updated_at
    custom_resource_service.db.commit.assert_not_called()
    custom_resource_service.db.rollback.assert_called_once()


@pytest.mark.unit
@pytest.mark.workspace
def test_reconcile_workspace_status_derives_namespace_qualified_service_dns(
    custom_resource_service,
):
    workspace = Mock()
    workspace.id = "workspace-example"
    workspace.owner_id = "workspace-owner-id"
    workspace.name = "Example Workspace"
    workspace.provisioner = "kubernetes"
    workspace.target_namespace = "workspace-system"
    workspace.runtime_status = "starting"
    workspace.bootstrap_revision = 1
    workspace.bootstrap_observed_revision = 0
    workspace.bootstrap_status = "pending"
    workspace.bootstrap_error_code = None
    workspace.bootstrap_last_transition_at = None
    workspace.runtime_desired_revision = 1
    workspace.runtime_observed_revision = 0
    workspace.runtime_reason = None
    workspace.runtime_error_code = None
    workspace.runtime_last_transition_at = None
    workspace.runtime_instance_id = RUNTIME_INSTANCE_ID
    workspace.knowledge_base_mount_desired_revision = 0
    workspace.runtime_access_revision = 0
    workspace.runtime_internal_url = None
    workspace.runtime_internal_port = 3002
    workspace.browser_status = "starting"
    workspace.browser_desired_revision = 1
    workspace.browser_observed_revision = 0
    workspace.browser_reason = None
    workspace.browser_error_code = None
    workspace.browser_last_transition_at = None
    workspace.browser_webrtc_internal_url = None
    workspace.browser_webrtc_internal_port = 6080
    workspace.canvas_status = "starting"
    workspace.canvas_desired_revision = 1
    workspace.canvas_observed_revision = 0
    workspace.canvas_reason = None
    workspace.canvas_error_code = None
    workspace.canvas_last_transition_at = None
    workspace.canvas_internal_url = None
    workspace.canvas_internal_port = 3003
    workspace.updated_at = datetime.utcnow()
    custom_resource_service.db.get.return_value = workspace

    mock_api = MagicMock()
    mock_api.get_namespaced_custom_object.return_value = _current_custom_resource(
        workspace,
        phase="Running",
        components={
            "runtime": {
                "phase": "Running",
            },
            "browser": {
                "phase": "Running",
            },
            "canvas": {
                "phase": "Running",
            },
        },
    )

    with patch.object(
        custom_resource_service, "_get_custom_objects_api", return_value=mock_api
    ):
        snapshot = custom_resource_service.fetch_workspace_status_snapshot(workspace.id)
        assert snapshot is not None
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is True
    assert workspace.runtime_internal_url == (
        "http://runtime-workspace-example.workspace-system.svc.cluster.local:3002"
    )
    assert workspace.browser_webrtc_internal_url == (
        "http://browser-workspace-example.workspace-system.svc.cluster.local:6080"
    )
    assert workspace.canvas_internal_url == (
        "http://canvas-workspace-example.workspace-system.svc.cluster.local:3003"
    )


@pytest.mark.unit
@pytest.mark.workspace
def test_apply_workspace_status_snapshot_skips_when_lifecycle_owns_lock(
    custom_resource_service,
    sample_workspace,
):
    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=sample_workspace.id,
        resource_name=f"workspace-{sample_workspace.id}",
        namespace="workspace-system",
        custom_resource={},
    )

    with patch(
        "app.modules.workspace.custom_resources.try_acquire_workspace_transaction_lock",
        return_value=False,
    ):
        changed = custom_resource_service.apply_workspace_status_snapshot(snapshot)

    assert changed is False
    custom_resource_service.db.get.assert_not_called()
    custom_resource_service.db.commit.assert_not_called()
    custom_resource_service.db.rollback.assert_called_once()
