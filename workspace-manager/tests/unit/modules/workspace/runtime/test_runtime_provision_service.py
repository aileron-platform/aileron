"""RuntimeProvisionService UnitTest"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlsplit
from uuid import UUID

import pytest

from app.db import models as db_models
from app.modules.container_images.catalog import get_container_image_service
from app.modules.workspace.browser_credentials import BrowserCredentialService
from app.modules.workspace.environment import WorkspaceEnvironmentError
from app.modules.workspace.orchestrator.base import (
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from app.modules.workspace.orchestrator.models import (
    ExecutionPlaneInfo,
    RuntimeContext,
    RuntimeInfo,
)
from app.modules.workspace.runtime.database import RuntimeDatabaseCredential
from app.modules.workspace.runtime.provisioning import (
    KnowledgeBaseMountSourceError,
    RuntimeProvisionService,
)

_REPOSITORY_ROOT = (
    Path("/repo-root")
    if Path("/repo-root").is_dir()
    else Path(__file__).resolve().parents[6]
)
RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT = (
    _REPOSITORY_ROOT
    / "contracts"
    / "platform-configuration"
    / "runtime-platform-environment.json"
)


def _assert_runtime_platform_environment(environment: dict[str, str]) -> None:
    contract = json.loads(
        RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT.read_text(encoding="utf-8")
    )
    assert contract["schemaVersion"] == 1
    required = {item["name"]: item for item in contract["required"]}
    assert len(required) == len(contract["required"])
    observed = {
        name: value
        for name, value in environment.items()
        if name.startswith("AILERON_")
    }
    assert set(observed) == set(required)
    for name, item in required.items():
        assert re.fullmatch(
            item["valuePattern"], observed[name]
        ), f"{name} does not satisfy {item['valueKind']}"
        port_contract = item.get("port")
        if port_contract is None:
            continue
        parsed = urlsplit(observed[name])
        try:
            port = parsed.port
        except ValueError as exc:
            raise AssertionError(f"{name} has an invalid port") from exc
        if port_contract["required"]:
            assert port is not None, f"{name} requires an explicit port"
        if port is not None:
            assert (
                port_contract["minimum"] <= port <= port_contract["maximum"]
            ), f"{name} port is outside the allowed range"


# ============================================================================
# Fixtures
# ============================================================================


def _mount_snapshot_entry(
    *,
    attachment_id: str,
    knowledge_base_id: str,
    mount_alias: str,
) -> dict[str, str]:
    return {
        "attachmentId": attachment_id,
        "knowledgeBaseId": knowledge_base_id,
        "mountAlias": mount_alias,
        "attachedById": "user-123",
    }


@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.flush = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=None)
    return session


@pytest.fixture
def mock_settings():
    """Mock Settings"""
    settings = MagicMock()
    settings.RUNTIME_PROVISIONER = "docker"
    settings.RUNTIME_SCRIPT_ROOT = "/tmp/workspace-scripts"
    settings.HOST_PROJECT_ROOT = ""
    settings.HOST_WORKSPACE_RUNTIME_DIR = ""
    settings.HOST_WORKSPACES_DIR = "/tmp/workspaces"
    settings.HOST_WORKSPACE_SCRIPTS_DIR = "/tmp/workspace-scripts-host"
    settings.HOST_RUNTIME_HOME_DIR = "/tmp/runtime-home"
    settings.HOST_KNOWLEDGE_BASES_DIR = "/tmp/knowledge-bases"
    settings.HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE = (
        "/tmp/runtime-assertions/jwks.json"
    )
    settings.HOST_PLATFORM_DATABASE_CA_CERT_FILE = ""
    settings.MANAGER_WORKSPACES_DIR = "/mnt/workspaces"
    settings.MANAGER_WORKSPACE_SCRIPTS_DIR = "/mnt/workspace-scripts"
    settings.MANAGER_RUNTIME_HOME_DIR = "/mnt/runtime-home"
    settings.MANAGER_KNOWLEDGE_BASES_DIR = "/mnt/knowledge-bases"
    settings.DOCKER_NETWORK = "workspace-network"
    settings.AILERON_INSTALLATION_ID = "test-installation"
    settings.ENV = "testing"
    settings.PORT = 8000
    settings.PLATFORM_PUBLIC_ORIGIN = "https://aileron.example.test"
    settings.RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE = (
        "/run/secrets/aileron/runtime-assertion-jwks.json"
    )
    settings.RUNTIME_ASSERTION_ISSUER = "workspace-manager"
    settings.RUNTIME_ASSERTION_PRIVATE_KEY_FILE = (
        "/run/secrets/aileron/runtime-assertion-private.pem"
    )
    settings.TURN_REACHABILITY_PROFILE_FILE = ""
    settings.TURN_REST_SHARED_SECRET_FILE = ""
    settings.TURN_BACKEND_ICE_SERVERS_JSON_FILE = ""
    settings.OIDC_SERVER_URL = "http://localhost:8080"
    settings.OIDC_REALM = "aileron"
    settings.OIDC_CLIENT_ID = "aileron-web"
    return settings


@pytest.fixture
def mock_template_engine():
    """Mock ScriptTemplateEngine"""
    engine = MagicMock()
    engine.render_to_file.return_value = Path("/tmp/startup.sh")
    return engine


@pytest.fixture
def sample_workspace():
    """Example Workspace"""
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-123"
    workspace.owner_id = "user-123"
    workspace.name = "Test Workspace"
    workspace.git_url = "https://github.com/test/repo.git"
    workspace.branch = "main"
    workspace.runtime = "python:3.9"
    workspace.provisioner = "docker"
    workspace.runtime_instance_id = None
    workspace.browser_instance_id = None
    workspace.canvas_instance_id = None
    workspace.runtime_control_instance_id = None
    workspace.runtime_control_token_hash = None
    workspace.runtime_container_id = None
    workspace.browser_container_id = None
    workspace.canvas_container_id = None
    workspace.knowledge_base_mount_desired_revision = 0
    workspace.knowledge_base_mount_observed_revision = 0
    workspace.knowledge_base_mount_sync_status = "ready"
    workspace.knowledge_base_mount_active_snapshot = []
    workspace.knowledge_base_mount_candidate_snapshot = None
    workspace.runtime_access_revision = 0
    workspace.runtime_internal_port = 3002
    workspace.browser_webrtc_internal_port = 6080
    workspace.canvas_internal_port = 3003
    workspace.runtime_status = "pending"
    workspace.env_vars = [{"key": "CUSTOM_VALUE", "value": "production"}]
    workspace.setup_script = "#!/bin/bash\necho 'Setup complete'"
    workspace.worktree_subdir = ".worktrees"
    return workspace


@pytest.fixture
def provision_service(mock_db_session, mock_settings, mock_template_engine):
    """RuntimeProvisionService Instance"""
    with patch(
        "app.modules.workspace.runtime.provisioning.get_settings",
        return_value=mock_settings,
    ):
        with patch(
            "app.modules.workspace.runtime.provisioning.ScriptTemplateEngine",
            return_value=mock_template_engine,
        ):
            database_service = MagicMock()
            database_service.prepare.return_value = RuntimeDatabaseCredential(
                workspace_id="workspace-123",
                runtime_instance_id="11111111-1111-4111-8111-111111111111",
                schema_name="ws_test",
                role_name="wsr_test_generation",
                role_prefix="wsr_test_",
                password="scoped-password",
                database_url="postgresql://wsr_test_generation:scoped-password@postgres/test",
                secret_name="workspace-generation-0123456789abcdef",
            )
            service = RuntimeProvisionService(
                mock_db_session,
                runtime_database_service=database_service,
            )
            service.template_engine = mock_template_engine
            return service


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.unit
class TestRuntimeProvisionService:
    def test_prepare_execution_plane_rotates_scoped_control_token_hash(
        self,
        provision_service,
        sample_workspace,
    ):
        runtime_context = MagicMock(spec=RuntimeContext)
        with (
            patch.object(
                provision_service,
                "_build_runtime_context",
                return_value=runtime_context,
            ) as build_runtime,
            patch.object(
                provision_service,
                "_build_browser_runtime_context",
                return_value=MagicMock(spec=RuntimeContext),
            ),
            patch.object(
                provision_service,
                "_build_canvas_runtime_context",
                return_value=MagicMock(spec=RuntimeContext),
            ),
        ):
            plan = provision_service._prepare_generation(
                sample_workspace,
                runtime_instance_id="11111111-1111-4111-8111-111111111111",
            )

        assert sample_workspace.runtime_control_instance_id == plan.runtime_instance_id
        assert len(sample_workspace.runtime_control_token_hash) == 64
        assert (
            plan.runtime_control_token
            not in sample_workspace.runtime_control_token_hash
        )
        assert plan.workspace.runtime_internal_port == 3002
        assert plan.workspace.browser_webrtc_internal_port == 6080
        assert plan.workspace.canvas_internal_port == 3003
        build_runtime.assert_called_once_with(
            sample_workspace,
            plan.runtime_instance_id,
            database_url=plan.database_credential.database_url,
            runtime_control_token=plan.runtime_control_token,
        )

    def test_deployment_images_reach_docker_orchestrator_boundary(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ) -> None:
        runtime_image = "ailerondocker/workspace-runtime:git-test"
        browser_image = "ailerondocker/workspace-chrome:git-test"
        canvas_image = "ailerondocker/workspace-canvas:git-test"
        image_settings = MagicMock()
        image_settings.WORKSPACE_RUNTIME_IMAGE = runtime_image
        image_settings.WORKSPACE_BROWSER_IMAGE = browser_image
        image_settings.WORKSPACE_CANVAS_IMAGE = canvas_image
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        sample_workspace.browser_credential_revision = 1
        sample_workspace.browser_credential_key_id = "test-browser-key"
        sample_workspace.browser_credential_algorithm = "hkdf-sha256-v1"
        credential_service = MagicMock()
        credential_service.derive.return_value = MagicMock(
            user_password="test-user-password",
            admin_password="test-admin-password",
        )
        orchestrator = MagicMock()
        orchestrator.recreate_workspace_execution_plane.return_value = MagicMock()
        assert_claim = MagicMock()

        get_container_image_service.cache_clear()
        try:
            with (
                patch(
                    "app.modules.container_images.catalog.get_settings",
                    return_value=image_settings,
                ),
                patch.object(
                    provision_service,
                    "_build_environment",
                    return_value={},
                ),
                patch.object(provision_service, "_build_volumes", return_value=[]),
                patch.object(
                    provision_service,
                    "_build_browser_connectivity_probe_context",
                    return_value=None,
                ),
                patch.object(
                    provision_service,
                    "_write_browser_credential_files",
                    return_value=[],
                ),
                patch.object(
                    BrowserCredentialService,
                    "from_settings",
                    return_value=credential_service,
                ),
                patch(
                    "app.modules.workspace.runtime.provisioning."
                    "OrchestratorFactory.get_orchestrator",
                    return_value=orchestrator,
                ),
                patch.object(provision_service, "_wait_for_execution_plane_ready"),
            ):
                plan = provision_service._prepare_generation(
                    sample_workspace,
                    runtime_instance_id="11111111-1111-4111-8111-111111111111",
                )
                provision_service._apply_generation(
                    plan,
                    assert_claim=assert_claim,
                    timeout_seconds=300,
                )
        finally:
            get_container_image_service.cache_clear()

        call = orchestrator.recreate_workspace_execution_plane.call_args.kwargs
        assert call["runtime_context"].labels["image"] == runtime_image
        assert call["browser_context"].labels["image"] == browser_image
        assert call["canvas_context"].labels["image"] == canvas_image

    def test_apply_execution_plane_keeps_ready_generation_active(
        self,
        provision_service,
    ):
        plan = MagicMock()
        plan.workspace.provisioner = "docker"
        plan.workspace.id = "workspace-123"
        plan.runtime_instance_id = "11111111-1111-4111-8111-111111111111"
        execution_plane = MagicMock()
        orchestrator = MagicMock()
        orchestrator.recreate_workspace_execution_plane.return_value = execution_plane
        assert_claim = MagicMock()

        with (
            patch(
                "app.modules.workspace.runtime.provisioning."
                "OrchestratorFactory.get_orchestrator",
                return_value=orchestrator,
            ),
            patch.object(
                provision_service,
                "_wait_for_execution_plane_ready",
            ) as wait_for_ready,
        ):
            result = provision_service._apply_generation(
                plan,
                assert_claim=assert_claim,
                timeout_seconds=300,
            )

        assert result is execution_plane
        wait_for_ready.assert_called_once_with(
            execution_plane,
            assert_claim=assert_claim,
            timeout_seconds=300,
        )
        orchestrator.terminate_execution_plane.assert_not_called()
        provision_service.runtime_database_service.deactivate.assert_not_called()

    def test_apply_execution_plane_result_activates_each_component_generation(
        self,
        provision_service,
        sample_workspace,
    ):
        instance_id = "11111111-1111-4111-8111-111111111111"
        sample_workspace.runtime_instance_id = instance_id
        sample_workspace.runtime_control_instance_id = instance_id
        sample_workspace.runtime_control_token_hash = "a" * 64
        sample_workspace.runtime_desired_revision = 2
        sample_workspace.browser_desired_revision = 3
        sample_workspace.canvas_desired_revision = 4
        sample_workspace.bootstrap_revision = 1

        result = ExecutionPlaneInfo(
            runtime_instance_id=instance_id,
            runtime=RuntimeInfo(
                identifier="runtime-container",
                internal_url="http://runtime:3002",
            ),
            browser=RuntimeInfo(
                identifier="browser-container",
                internal_url="http://browser:6080",
            ),
            canvas=RuntimeInfo(
                identifier="canvas-container",
                internal_url="http://canvas:3003",
            ),
        )

        provision_service._stage_generation(sample_workspace, result)

        assert (
            sample_workspace.runtime_instance_id,
            sample_workspace.browser_instance_id,
            sample_workspace.canvas_instance_id,
        ) == (instance_id, instance_id, instance_id)

    def test_restart_browser_activates_an_independent_component_generation(
        self,
        provision_service,
        sample_workspace,
    ):
        sample_workspace.runtime_instance_id = "11111111-1111-4111-8111-111111111111"
        sample_workspace.browser_instance_id = "22222222-2222-4222-8222-222222222222"
        sample_workspace.canvas_instance_id = "33333333-3333-4333-8333-333333333333"
        next_browser_instance_id = "44444444-4444-4444-8444-444444444444"
        browser_context = MagicMock(spec=RuntimeContext)
        browser_probe_context = MagicMock(spec=RuntimeContext)
        browser_result = RuntimeInfo(
            identifier="browser-new",
            internal_url="http://browser:6080",
        )
        orchestrator = MagicMock()
        orchestrator.replace_workspace_component.return_value = browser_result
        assert_claim = MagicMock()

        with (
            patch(
                "app.modules.workspace.runtime.provisioning.uuid4",
                return_value=UUID(next_browser_instance_id),
                create=True,
            ),
            patch(
                "app.modules.workspace.runtime.provisioning."
                "OrchestratorFactory.get_orchestrator",
                return_value=orchestrator,
            ),
            patch.object(
                provision_service,
                "_build_browser_runtime_context",
                return_value=browser_context,
            ) as build_browser,
            patch.object(
                provision_service,
                "_build_browser_connectivity_probe_context",
                return_value=browser_probe_context,
            ) as build_browser_probe,
        ):
            provision_service.restart_sibling_component(
                sample_workspace,
                component="browser",
                assert_claim=assert_claim,
            )

        build_browser.assert_called_once_with(
            sample_workspace,
            next_browser_instance_id,
        )
        build_browser_probe.assert_called_once_with(
            sample_workspace,
            next_browser_instance_id,
        )
        orchestrator.replace_workspace_component.assert_called_once_with(
            workspace=sample_workspace,
            component="browser",
            context=browser_context,
            assert_claim=assert_claim,
            browser_probe_context=browser_probe_context,
        )
        assert (
            sample_workspace.runtime_instance_id,
            sample_workspace.browser_instance_id,
            sample_workspace.canvas_instance_id,
        ) == (
            "11111111-1111-4111-8111-111111111111",
            next_browser_instance_id,
            "33333333-3333-4333-8333-333333333333",
        )

    def test_browser_probe_runs_as_bind_mount_owner(
        self,
        provision_service,
        sample_workspace,
        tmp_path,
    ):
        profile = tmp_path / "turn-reachability-profile.json"
        secret = tmp_path / "turn-rest-shared-secret"
        backend_ice = tmp_path / "turn-backend-ice-servers.json"
        profile.write_text("{}", encoding="utf-8")
        secret.write_text("secret", encoding="utf-8")
        backend_ice.write_text('[{"urls":["turn:coturn:3478"]}]', encoding="utf-8")
        provision_service.settings.BROWSER_CONNECTIVITY_PROBE_IMAGE = (
            "ailerondocker/workspace-operator:dev"
        )
        provision_service.settings.HOST_TURN_REACHABILITY_PROFILE_FILE = str(profile)
        provision_service.settings.HOST_TURN_REST_SHARED_SECRET_FILE = str(secret)
        provision_service.settings.HOST_TURN_BACKEND_ICE_SERVERS_JSON_FILE = str(
            backend_ice
        )
        provision_service.settings.TURN_REACHABILITY_PROFILE_FILE = str(profile)
        provision_service.settings.TURN_REST_SHARED_SECRET_FILE = str(secret)
        provision_service.settings.TURN_BACKEND_ICE_SERVERS_JSON_FILE = str(backend_ice)

        context = provision_service._build_browser_connectivity_probe_context(
            sample_workspace,
            "44444444-4444-4444-8444-444444444444",
        )

        assert context is not None
        owner = profile.stat()
        assert context.labels["user"] == f"{owner.st_uid}:{owner.st_gid}"

    def test_browser_probe_validates_manager_paths_and_mounts_host_paths(
        self,
        provision_service,
        sample_workspace,
        tmp_path,
    ):
        host_profile = tmp_path / "host" / "turn-reachability-profile.json"
        host_secret = tmp_path / "host" / "turn-rest-shared-secret"
        host_backend_ice = tmp_path / "host" / "turn-backend-ice-servers.json"
        manager_profile = tmp_path / "manager" / "turn-reachability-profile.json"
        manager_secret = tmp_path / "manager" / "turn-rest-shared-secret"
        manager_backend_ice = tmp_path / "manager" / "turn-backend-ice-servers.json"
        provision_service.settings.BROWSER_CONNECTIVITY_PROBE_IMAGE = (
            "ailerondocker/workspace-operator:dev"
        )
        provision_service.settings.HOST_TURN_REACHABILITY_PROFILE_FILE = str(
            host_profile
        )
        provision_service.settings.HOST_TURN_REST_SHARED_SECRET_FILE = str(host_secret)
        provision_service.settings.HOST_TURN_BACKEND_ICE_SERVERS_JSON_FILE = str(
            host_backend_ice
        )
        provision_service.settings.TURN_REACHABILITY_PROFILE_FILE = str(manager_profile)
        provision_service.settings.TURN_REST_SHARED_SECRET_FILE = str(manager_secret)
        provision_service.settings.TURN_BACKEND_ICE_SERVERS_JSON_FILE = str(
            manager_backend_ice
        )

        with patch("app.modules.workspace.runtime.provisioning.os.stat") as stat:
            stat.side_effect = [
                Mock(st_uid=501, st_gid=20),
                Mock(st_uid=501, st_gid=20),
                Mock(st_uid=501, st_gid=20),
            ]
            context = provision_service._build_browser_connectivity_probe_context(
                sample_workspace,
                "55555555-5555-4555-8555-555555555555",
            )

        assert context is not None
        assert [call.args[0] for call in stat.call_args_list] == [
            str(manager_profile),
            str(manager_secret),
            str(manager_backend_ice),
        ]
        assert [mount.source for mount in context.volumes] == [
            str(host_profile),
            str(host_secret),
            str(host_backend_ice),
        ]
        assert context.environment["TURN_BACKEND_ICE_SERVERS_JSON_FILE"] == (
            "/run/secrets/turn/backend-ice-servers.json"
        )
        assert context.labels["user"] == "501:20"

    def test_apply_execution_plane_removes_unready_generation(
        self,
        provision_service,
    ):
        plan = MagicMock()
        plan.workspace.provisioner = "docker"
        plan.workspace.id = "workspace-123"
        plan.runtime_instance_id = "11111111-1111-4111-8111-111111111111"
        execution_plane = MagicMock()
        orchestrator = MagicMock()
        orchestrator.recreate_workspace_execution_plane.return_value = execution_plane

        with (
            patch(
                "app.modules.workspace.runtime.provisioning."
                "OrchestratorFactory.get_orchestrator",
                return_value=orchestrator,
            ),
            patch.object(
                provision_service,
                "_wait_for_execution_plane_ready",
                side_effect=RuntimeError("not ready"),
            ),
            pytest.raises(RuntimeError, match="not ready"),
        ):
            provision_service._apply_generation(
                plan,
                assert_claim=MagicMock(),
                timeout_seconds=1,
            )

        orchestrator.terminate_execution_plane.assert_called_once()
        cleanup_assertion = orchestrator.terminate_execution_plane.call_args.kwargs[
            "assert_claim"
        ]
        cleanup_assertion()
        provision_service.runtime_database_service.deactivate.assert_called_once_with(
            plan.database_credential
        )

    def test_apply_execution_plane_reports_unconfirmed_cleanup(
        self,
        provision_service,
    ):
        plan = MagicMock()
        plan.workspace.provisioner = "docker"
        plan.runtime_instance_id = "11111111-1111-4111-8111-111111111111"
        execution_plane = MagicMock()
        orchestrator = MagicMock()
        orchestrator.recreate_workspace_execution_plane.return_value = execution_plane
        orchestrator.terminate_execution_plane.side_effect = (
            WorkspaceRuntimeTerminationUnconfirmedError("not fenced")
        )

        with (
            patch(
                "app.modules.workspace.runtime.provisioning."
                "OrchestratorFactory.get_orchestrator",
                return_value=orchestrator,
            ),
            patch.object(
                provision_service,
                "_wait_for_execution_plane_ready",
                side_effect=RuntimeError("not ready"),
            ),
            pytest.raises(
                WorkspaceRuntimeTerminationUnconfirmedError,
                match="not fenced",
            ),
        ):
            provision_service._apply_generation(
                plan,
                assert_claim=MagicMock(),
                timeout_seconds=1,
            )

        provision_service.runtime_database_service.deactivate.assert_called_once_with(
            plan.database_credential
        )

    def test_terminate_execution_plane_deactivates_database_after_cleanup_failure(
        self,
        provision_service,
    ):
        plan = MagicMock()
        plan.workspace.provisioner = "docker"
        execution_plane = MagicMock()
        orchestrator = MagicMock()
        orchestrator.terminate_execution_plane.side_effect = RuntimeError(
            "cleanup failed"
        )

        with (
            patch(
                "app.modules.workspace.runtime.provisioning."
                "OrchestratorFactory.get_orchestrator",
                return_value=orchestrator,
            ),
            pytest.raises(RuntimeError, match="cleanup failed"),
        ):
            provision_service._discard_generation(
                plan,
                execution_plane,
                assert_claim=MagicMock(),
            )

        provision_service.runtime_database_service.deactivate.assert_called_once_with(
            plan.database_credential
        )

    def test_wait_for_execution_plane_ready_uses_component_health_endpoints(
        self,
        provision_service,
    ):
        execution_plane = MagicMock()
        execution_plane.runtime.internal_url = "http://runtime:3002"
        execution_plane.browser.internal_url = "http://browser:6080"
        execution_plane.browser_probe = None
        execution_plane.canvas.extra_info = {"container_name": "canvas"}
        client = MagicMock()
        client_class = MagicMock()
        client_class.return_value.__enter__.return_value = client

        with patch(
            "app.modules.workspace.runtime.provisioning.httpx.Client",
            client_class,
        ):
            provision_service._wait_for_execution_plane_ready(
                execution_plane,
                assert_claim=MagicMock(),
                timeout_seconds=1,
            )

        assert [call.args[0] for call in client.get.call_args_list] == [
            "http://runtime:3002/health",
            "http://runtime:3004/health",
            "http://browser:6080/health",
            "http://canvas:3013/health",
        ]

    def test_build_runtime_context(
        self, provision_service, sample_workspace, mock_template_engine
    ):
        """Test: Build RuntimeContext"""
        # Arrange
        with patch(
            "app.modules.container_images.catalog.get_container_image_service"
        ) as mock_image_service_getter:
            mock_image_service = MagicMock()
            mock_image_service.get_docker_image_name.return_value = (
                "workspace-image:latest"
            )
            mock_image_service_getter.return_value = mock_image_service

            # Act
            runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
            context = provision_service._build_runtime_context(
                sample_workspace,
                runtime_instance_id,
                database_url="postgresql://scoped@postgres/test",
                runtime_control_token="scoped-control-token",
            )

            # Assert
            assert isinstance(context, RuntimeContext)
            assert context.labels["image"] == "workspace-image:latest"

            # Environment
            assert context.environment["AILERON_WORKSPACE_ID"] == "workspace-123"
            assert context.environment["CUSTOM_VALUE"] == "production"
            assert (
                context.environment["AILERON_RUNTIME_INSTANCE_ID"]
                == runtime_instance_id
            )
            assert context.environment["AILERON_KB_MOUNT_REVISION"] == "0"
            assert context.environment[
                "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE"
            ] == ("/run/secrets/aileron/runtime-assertion-jwks.json")
            assert context.environment["AILERON_RUNTIME_ASSERTION_ISSUER"] == (
                "workspace-manager"
            )
            for startup_owned_name in (
                "HOME",
                "CODEX_HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "MARKETPLACE_OPERATION_JOURNAL_DIR",
            ):
                assert startup_owned_name not in context.environment
            assert "RUNTIME_ASSERTION_PRIVATE_KEY_FILE" not in context.environment
            assert context.environment["AILERON_RUNTIME_CONTROL_TOKEN_FILE"] == (
                "/run/secrets/aileron/runtime-control-token"
            )
            assert "RUNTIME_CONTROL_TOKEN" not in context.environment
            assert "INTERNAL_API_TOKEN" not in context.environment
            assert "REDIS_URL" not in context.environment
            assert "DATABASE_URL" not in context.environment
            assert "GIT_REPO_URL" not in context.environment
            assert "GIT_BRANCH" not in context.environment
            assert not any(name.startswith("OIDC_") for name in context.environment)
            assert (
                context.container_labels["aileron.component_instance_id"]
                == runtime_instance_id
            )

            # Volumes
            assert len(context.volumes) >= 3  # workspace, scripts, docker.sock
            assert any(v.target == "/workspace" for v in context.volumes)
            assert any(
                v.source == "/tmp/runtime-assertions/jwks.json"
                and v.target == "/run/secrets/aileron/runtime-assertion-jwks.json"
                and v.read_only
                for v in context.volumes
            )
            assert all(
                "runtime-assertion-private" not in v.source
                and "runtime-assertion-private" not in v.target
                for v in context.volumes
            )

            assert not hasattr(context, "ports")

            # Template rendered
            mock_template_engine.render_to_file.assert_called_once()

    def test_build_runtime_context_emits_only_canonical_platform_environment_and_secret_file_mounts(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "host-workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "host-scripts")
        mock_settings.HOST_RUNTIME_HOME_DIR = str(tmp_path / "host-runtime-home")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "host-kbs")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "manager-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "manager-scripts")
        mock_settings.MANAGER_RUNTIME_HOME_DIR = str(tmp_path / "manager-runtime-home")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path / "manager-kbs")
        sample_workspace.runtime_access_revision = 7
        sample_workspace.browser_webrtc_internal_url = None
        sample_workspace.canvas_internal_url = None

        with patch(
            "app.modules.container_images.catalog.get_container_image_service"
        ) as image_service_getter:
            image_service_getter.return_value.get_docker_image_name.return_value = (
                "workspace-image:latest"
            )
            context = provision_service._build_runtime_context(
                sample_workspace,
                "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                database_url="postgresql://scoped@postgres/test",
                runtime_control_token="scoped-control-token",
            )

        assert context.environment == {
            "AILERON_WORKSPACE_ID": "workspace-123",
            "AILERON_WORKSPACE_PATH": "/workspace",
            "AILERON_RUNTIME_INSTANCE_ID": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
            "AILERON_RUNTIME_ACCESS_REVISION": "7",
            "AILERON_KB_MOUNT_REVISION": "0",
            "AILERON_WORKTREE_SUBDIR": ".worktrees",
            "AILERON_RUNTIME_DATABASE_CONNECTION_FILE": (
                "/run/secrets/aileron/runtime-database-connection"
            ),
            "AILERON_RUNTIME_CONTROL_TOKEN_FILE": (
                "/run/secrets/aileron/runtime-control-token"
            ),
            "AILERON_MANAGER_INTERNAL_URL": "http://workspace-manager:8000",
            "AILERON_PLATFORM_PUBLIC_ORIGIN": "https://aileron.example.test",
            "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": (
                "/run/secrets/aileron/runtime-assertion-jwks.json"
            ),
            "AILERON_RUNTIME_ASSERTION_ISSUER": "workspace-manager",
            "AILERON_BROWSER_SERVICE_NAME": "workspace-browser-workspace-123",
            "AILERON_BROWSER_WEBRTC_INTERNAL_URL": (
                "http://workspace-browser-workspace-123:6080"
            ),
            "AILERON_BROWSER_CDP_URL": "http://workspace-browser-workspace-123:9223",
            "AILERON_CANVAS_SERVICE_NAME": "workspace-canvas-workspace-123",
            "AILERON_CANVAS_INTERNAL_URL": (
                "http://workspace-canvas-workspace-123:3003"
            ),
            "AILERON_CANVAS_API_URL": "http://workspace-canvas-workspace-123:3013",
            "CUSTOM_VALUE": "production",
        }
        _assert_runtime_platform_environment(context.environment)
        secret_mounts = {
            mount.target: (mount.source, mount.read_only)
            for mount in context.volumes
            if mount.target.startswith("/run/secrets/aileron/runtime-")
        }
        assert secret_mounts == {
            "/run/secrets/aileron/runtime-assertion-jwks.json": (
                "/tmp/runtime-assertions/jwks.json",
                True,
            ),
            "/run/secrets/aileron/runtime-database-connection": (
                str(
                    tmp_path
                    / "host-runtime-home"
                    / "workspace_123"
                    / ".aileron"
                    / "secrets"
                    / "runtime-database-connection"
                ),
                True,
            ),
            "/run/secrets/aileron/runtime-control-token": (
                str(
                    tmp_path
                    / "host-runtime-home"
                    / "workspace_123"
                    / ".aileron"
                    / "secrets"
                    / "runtime-control-token"
                ),
                True,
            ),
        }
        manager_secret_root = (
            tmp_path / "manager-runtime-home" / "workspace_123" / ".aileron" / "secrets"
        )
        assert (manager_secret_root / "runtime-database-connection").read_text(
            encoding="utf-8"
        ) == "postgresql://scoped@postgres/test"
        assert (manager_secret_root / "runtime-control-token").read_text(
            encoding="utf-8"
        ) == "scoped-control-token"
        assert (
            manager_secret_root / "runtime-database-connection"
        ).stat().st_mode & 0o777 == 0o400
        assert (
            manager_secret_root / "runtime-control-token"
        ).stat().st_mode & 0o777 == 0o400

    def test_runtime_platform_environment_contract_rejects_empty_worktree_and_invalid_url_ports(
        self,
    ) -> None:
        contract = json.loads(
            RUNTIME_PLATFORM_ENVIRONMENT_CONTRACT.read_text(encoding="utf-8")
        )
        values_by_kind = {
            "non-empty-string": "workspace-123",
            "absolute-path": "/workspace",
            "canonical-uuid": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
            "non-negative-integer": "1",
            "safe-relative-path": ".worktrees",
            "secret-file-path": "/run/secrets/credential",
            "internal-http-url": "http://service:3001",
            "public-origin": "https://aileron.example.test",
            "file-path": "/run/config/jwks.json",
            "bounded-non-empty-string": "workspace-manager",
            "dns-service-name": "workspace-runtime",
        }
        environment = {
            item["name"]: values_by_kind[item["valueKind"]]
            for item in contract["required"]
        }
        _assert_runtime_platform_environment(environment)

        invalid_worktree = dict(environment)
        invalid_worktree["AILERON_WORKTREE_SUBDIR"] = ""
        with pytest.raises(AssertionError, match="safe-relative-path"):
            _assert_runtime_platform_environment(invalid_worktree)

        for item in contract["required"]:
            if item.get("port") is None:
                continue
            for port in (0, 65536):
                invalid_port = dict(environment)
                scheme = "https" if item["valueKind"] == "public-origin" else "http"
                invalid_port[item["name"]] = f"{scheme}://service:{port}"
                with pytest.raises(AssertionError, match="invalid port|allowed range"):
                    _assert_runtime_platform_environment(invalid_port)

    @pytest.mark.parametrize(
        "env_vars",
        [
            [{"key": "AILERON_PUBLISH_GITLAB_TOKEN", "value": "attacker-token"}],
            [{"key": "XDG_STATE_HOME", "value": "/tmp/attacker"}],
            [
                {"key": "CUSTOM_VALUE", "value": "first"},
                {"key": "CUSTOM_VALUE", "value": "second"},
            ],
        ],
    )
    def test_build_environment_rejects_unsafe_persisted_env_vars(
        self,
        provision_service,
        sample_workspace,
        env_vars,
    ):
        sample_workspace.env_vars = env_vars

        with pytest.raises(WorkspaceEnvironmentError):
            provision_service._build_environment(
                sample_workspace,
                "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                database_url="postgresql://scoped@postgres/test",
                runtime_control_token="scoped-control-token",
            )

    def test_build_environment_rejects_all_aileron_prefixed_user_environment(
        self,
        provision_service,
        sample_workspace,
    ):
        sample_workspace.runtime_access_revision = 7
        sample_workspace.env_vars = [
            {"key": "AILERON_PUBLISH_GITLAB_TOKEN", "value": "gitlab-token"},
            {"key": "AILERON_PUBLISH_ARGOCD_TOKEN", "value": "argocd-token"},
            {"key": "AILERON_PUBLISH_OCI_PUSH_PASSWORD", "value": "registry-token"},
        ]

        with pytest.raises(WorkspaceEnvironmentError):
            provision_service._build_environment(
                sample_workspace,
                "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                database_url="postgresql://scoped@postgres/test",
                runtime_control_token="scoped-control-token",
            )

    def test_build_volumes_uses_workspace_scripts_and_persistent_home(
        self, provision_service, sample_workspace, mock_settings, tmp_path: Path
    ):
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "workspace-scripts")
        mock_settings.HOST_RUNTIME_HOME_DIR = str(tmp_path / "runtime-home")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "knowledge-bases")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(
            tmp_path / "mounted-workspace-scripts"
        )
        mock_settings.MANAGER_RUNTIME_HOME_DIR = str(tmp_path / "mounted-runtime-home")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(
            tmp_path / "mounted-knowledge-bases"
        )

        volumes = provision_service._build_volumes(sample_workspace)

        sources = {volume.target: volume.source for volume in volumes}
        assert sources["/workspace"] == str(tmp_path / "workspaces" / "workspace_123")
        assert sources["/scripts"] == str(
            tmp_path / "workspace-scripts" / "workspace_123"
        )
        assert sources["/home/developer"] == str(
            tmp_path / "runtime-home" / "workspace_123"
        )
        custom_setup = (
            tmp_path / "mounted-workspace-scripts" / "workspace_123" / "custom-setup.sh"
        )
        assert custom_setup.read_text(encoding="utf-8") == sample_workspace.setup_script
        assert custom_setup.stat().st_mode & 0o777 == 0o444
        assert (tmp_path / "mounted-runtime-home" / "workspace_123").is_dir()
        codex_config_path = (
            tmp_path
            / "mounted-runtime-home"
            / "workspace_123"
            / ".codex"
            / "config.toml"
        )
        assert codex_config_path.read_text(encoding="utf-8") == (
            "# Aileron-managed Codex defaults.\n"
            "# Runtime-specific sandbox and approval policy are passed by workspace-runtime.\n"
            "\n"
            'model_reasoning_effort = "medium"\n'
            "model_auto_compact_token_limit = 128000\n"
            "tool_output_token_limit = 12000\n"
            "\n"
            "[features]\n"
            "shell_snapshot = true\n"
            "multi_agent = true\n"
        )
        assert codex_config_path.stat().st_mode & 0o777 == 0o600

    def test_build_volumes_mounts_platform_database_ca_at_the_fixed_runtime_path(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "workspace-scripts")
        mock_settings.HOST_RUNTIME_HOME_DIR = str(tmp_path / "runtime-home")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "knowledge-bases")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(
            tmp_path / "mounted-workspace-scripts"
        )
        mock_settings.MANAGER_RUNTIME_HOME_DIR = str(tmp_path / "mounted-runtime-home")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(
            tmp_path / "mounted-knowledge-bases"
        )
        ca_file = tmp_path / "platform-database-ca.crt"
        ca_file.write_text("test-ca", encoding="utf-8")
        mock_settings.HOST_PLATFORM_DATABASE_CA_CERT_FILE = str(ca_file)

        volumes = provision_service._build_volumes(sample_workspace)

        ca_mounts = [
            volume
            for volume in volumes
            if volume.target == "/etc/aileron/data-service-ca/platform-database/ca.crt"
        ]
        assert len(ca_mounts) == 1
        assert ca_mounts[0].source == str(ca_file)
        assert ca_mounts[0].read_only is True

    def test_write_codex_default_config_preserves_existing_user_config(
        self, provision_service, tmp_path: Path
    ):
        runtime_home = tmp_path / "runtime-home"
        config_path = runtime_home / ".codex" / "config.toml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('model = "user-selected"\n', encoding="utf-8")

        provision_service._write_codex_default_config(runtime_home)

        assert config_path.read_text(encoding="utf-8") == 'model = "user-selected"\n'

    def test_build_volumes_resolves_relative_host_mount_paths(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        mock_settings.HOST_WORKSPACES_DIR = "data/workspace-data"
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = "data/workspace-scripts"
        mock_settings.HOST_RUNTIME_HOME_DIR = "data/runtime-home"
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = "data/knowledge-bases"
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(
            tmp_path / "mounted-workspace-scripts"
        )
        mock_settings.MANAGER_RUNTIME_HOME_DIR = str(tmp_path / "mounted-runtime-home")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(
            tmp_path / "mounted-knowledge-bases"
        )
        mock_settings.HOST_PROJECT_ROOT = str(tmp_path / "project-root")

        volumes = provision_service._build_volumes(sample_workspace)

        sources = {volume.target: volume.source for volume in volumes}
        assert sources["/workspace"] == str(
            tmp_path / "project-root" / "data" / "workspace-data" / "workspace_123"
        )
        assert sources["/scripts"] == str(
            tmp_path / "project-root" / "data" / "workspace-scripts" / "workspace_123"
        )
        assert sources["/home/developer"] == str(
            tmp_path / "project-root" / "data" / "runtime-home" / "workspace_123"
        )

    def test_build_volumes_rejects_relative_host_paths_without_absolute_project_root(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        mock_settings.HOST_WORKSPACES_DIR = "data/workspace-data"
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.HOST_PROJECT_ROOT = "."

        with pytest.raises(
            ValueError, match="HOST_PROJECT_ROOT must be an absolute path"
        ):
            provision_service._build_volumes(sample_workspace)

    def test_build_volumes_mounts_runtime_import_in_development(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        mock_settings.ENV = "development"
        mock_settings.HOST_WORKSPACE_RUNTIME_DIR = str(tmp_path / "workspace-runtime")
        mock_settings.HOST_PROJECT_ROOT = str(tmp_path / "project-root")

        volumes = provision_service._build_volumes(sample_workspace)

        sources = {volume.target: volume.source for volume in volumes}
        read_only = {volume.target: volume.read_only for volume in volumes}
        assert sources["/workspace-runtime/app"] == str(
            tmp_path / "workspace-runtime" / "app"
        )
        assert sources["/workspace-runtime/scripts"] == str(
            tmp_path / "workspace-runtime" / "scripts"
        )
        assert sources["/workspace-runtime/tests"] == str(
            tmp_path / "workspace-runtime" / "tests"
        )
        assert sources["/workspace-runtime/vendor"] == str(
            tmp_path / "workspace-runtime" / "import"
        )
        assert sources["/workspace-runtime/pyproject.toml"] == str(
            tmp_path / "workspace-runtime" / "pyproject.toml"
        )
        assert sources["/workspace-runtime/uv.lock"] == str(
            tmp_path / "workspace-runtime" / "uv.lock"
        )
        assert sources["/start_services.sh"] == str(
            tmp_path / "workspace-runtime" / "start_services.sh"
        )
        assert sources["/packages"] == str(tmp_path / "project-root" / "packages")
        assert read_only["/packages"] is True

    def test_build_volumes_adds_knowledge_base_mounts(
        self, provision_service, sample_workspace, mock_settings, tmp_path: Path
    ):
        kb_one_id = "11111111-1111-4111-8111-111111111111"
        kb_two_id = "22222222-2222-4222-8222-222222222222"
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "workspace-scripts")
        mock_settings.HOST_RUNTIME_HOME_DIR = str(tmp_path / "runtime-home")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "knowledge-bases")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(
            tmp_path / "mounted-workspace-scripts"
        )
        mock_settings.MANAGER_RUNTIME_HOME_DIR = str(tmp_path / "mounted-runtime-home")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(
            tmp_path / "mounted-knowledge-bases"
        )
        manager_root = tmp_path / "mounted-knowledge-bases"
        (manager_root / kb_one_id).mkdir(parents=True)
        (manager_root / kb_two_id).mkdir()
        sample_workspace.setup_script = None
        sample_workspace.knowledge_base_mount_active_snapshot = [
            _mount_snapshot_entry(
                attachment_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                knowledge_base_id=kb_one_id,
                mount_alias="docs",
            ),
            _mount_snapshot_entry(
                attachment_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                knowledge_base_id=kb_two_id,
                mount_alias="readonly-docs",
            ),
        ]

        volumes = provision_service._build_volumes(sample_workspace)

        kb_mounts = {
            volume.target: volume
            for volume in volumes
            if volume.target.startswith("/knowledge/")
        }
        assert kb_mounts["/knowledge/docs"].source == str(
            tmp_path / "knowledge-bases" / kb_one_id
        )
        assert kb_mounts["/knowledge/docs"].read_only is True
        assert kb_mounts["/knowledge/docs"].source_identity is not None
        assert kb_mounts["/knowledge/docs"].source_identity.validation_path == str(
            manager_root / kb_one_id
        )
        assert kb_mounts["/knowledge/readonly-docs"].source == str(
            tmp_path / "knowledge-bases" / kb_two_id
        )
        assert kb_mounts["/knowledge/readonly-docs"].read_only is True

    @pytest.mark.parametrize(
        "kb_id",
        (
            "11111111-1111-4111-8111-11111111111A",
            "../11111111-1111-4111-8111-111111111111",
            "11111111-1111-4111-8111-111111111111/child",
            "not-a-uuid",
        ),
    )
    def test_build_volumes_rejects_noncanonical_knowledge_base_ids(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
        kb_id: str,
    ):
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path / "kb-root")
        (tmp_path / "kb-root").mkdir()
        sample_workspace.knowledge_base_mount_active_snapshot = [
            _mount_snapshot_entry(
                attachment_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                knowledge_base_id=kb_id,
                mount_alias="docs",
            )
        ]

        with pytest.raises(KnowledgeBaseMountSourceError) as exc_info:
            provision_service._build_volumes(sample_workspace)

        assert exc_info.value.code == "KB_MOUNT_SOURCE_INVALID"

    @pytest.mark.parametrize("source_kind", ("missing", "file", "symlink"))
    def test_build_volumes_rejects_unsafe_knowledge_base_sources(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
        source_kind: str,
    ):
        kb_id = "11111111-1111-4111-8111-111111111111"
        manager_root = tmp_path / "kb-root"
        manager_root.mkdir()
        source = manager_root / kb_id
        if source_kind == "file":
            source.write_text("not a directory", encoding="utf-8")
        elif source_kind == "symlink":
            target = tmp_path / "outside"
            target.mkdir()
            source.symlink_to(target, target_is_directory=True)
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(manager_root)
        sample_workspace.knowledge_base_mount_active_snapshot = [
            _mount_snapshot_entry(
                attachment_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                knowledge_base_id=kb_id,
                mount_alias="docs",
            )
        ]

        with pytest.raises(KnowledgeBaseMountSourceError) as exc_info:
            provision_service._build_volumes(sample_workspace)

        assert exc_info.value.code == "KB_MOUNT_SOURCE_INVALID"

    def test_build_volumes_rejects_nested_mount_source(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        kb_id = "11111111-1111-4111-8111-111111111111"
        manager_root = tmp_path / "kb-root"
        (manager_root / kb_id).mkdir(parents=True)
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(manager_root)
        sample_workspace.knowledge_base_mount_active_snapshot = [
            _mount_snapshot_entry(
                attachment_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                knowledge_base_id=kb_id,
                mount_alias="docs",
            )
        ]
        monkeypatch.setattr(
            provision_service, "_contains_nested_mount", lambda _p: True
        )

        with pytest.raises(KnowledgeBaseMountSourceError) as exc_info:
            provision_service._build_volumes(sample_workspace)

        assert exc_info.value.code == "KB_MOUNT_SOURCE_INVALID"

    def test_build_browser_runtime_context_uses_read_only_secret_files(
        self,
        provision_service,
        sample_workspace,
        mock_settings,
        tmp_path: Path,
    ):
        keyring_path = tmp_path / "browser-credential-keyring.json"
        keyring_path.write_text(
            json.dumps(
                {
                    "algorithm": "hkdf-sha256-v1",
                    "activeKeyId": "test-browser-key",
                    "keys": {
                        "test-browser-key": base64.urlsafe_b64encode(b"b" * 32)
                        .rstrip(b"=")
                        .decode("ascii")
                    },
                }
            ),
            encoding="utf-8",
        )
        keyring_path.chmod(0o600)
        browser_credentials = BrowserCredentialService(keyring_path)
        sample_workspace.id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.browser_credential_revision = 1
        sample_workspace.browser_credential_key_id = "test-browser-key"
        sample_workspace.browser_credential_algorithm = "hkdf-sha256-v1"
        manager_secret_root = tmp_path / "manager-browser-credentials"
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(manager_secret_root)
        mock_settings.HOST_BROWSER_CREDENTIALS_DIR = "/host/browser-credentials"

        with (
            patch(
                "app.modules.container_images.catalog.get_container_image_service"
            ) as mock_image_service_getter,
            patch.object(
                BrowserCredentialService,
                "from_settings",
                return_value=browser_credentials,
            ),
        ):
            mock_image_service = MagicMock()
            mock_image_service.get_browser_image_name.return_value = (
                "workspace-browser:latest"
            )
            mock_image_service_getter.return_value = mock_image_service
            runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
            context = provision_service._build_browser_runtime_context(
                sample_workspace,
                runtime_instance_id,
            )

        expected_user_password = browser_credentials.derive(
            workspace_id=sample_workspace.id,
            revision=sample_workspace.browser_credential_revision,
            key_id=sample_workspace.browser_credential_key_id,
            algorithm=sample_workspace.browser_credential_algorithm,
        ).user_password
        expected_admin_password = browser_credentials.derive(
            workspace_id=sample_workspace.id,
            revision=sample_workspace.browser_credential_revision,
            key_id=sample_workspace.browser_credential_key_id,
            algorithm=sample_workspace.browser_credential_algorithm,
        ).admin_password
        credential_directory = manager_secret_root / runtime_instance_id
        user_password_file = credential_directory / "user-password"
        admin_password_file = credential_directory / "admin-password"

        assert user_password_file.read_text(encoding="utf-8") == expected_user_password
        assert (
            admin_password_file.read_text(encoding="utf-8") == expected_admin_password
        )
        assert credential_directory.stat().st_mode & 0o777 == 0o700
        assert user_password_file.stat().st_mode & 0o777 == 0o600
        assert admin_password_file.stat().st_mode & 0o777 == 0o600
        assert (
            context.environment["NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE"]
            == "/run/secrets/browser-credentials/user-password"
        )
        assert (
            context.environment["NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE"]
            == "/run/secrets/browser-credentials/admin-password"
        )
        assert "NEKO_MEMBER_MULTIUSER_USER_PASSWORD" not in context.environment
        assert "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD" not in context.environment
        assert expected_user_password not in context.environment.values()
        assert expected_admin_password not in context.environment.values()
        secret_mounts = {
            mount.target: mount
            for mount in context.volumes
            if mount.target.startswith("/run/secrets/browser-credentials/")
        }
        assert set(secret_mounts) == {
            "/run/secrets/browser-credentials/user-password",
            "/run/secrets/browser-credentials/admin-password",
        }
        assert all(mount.read_only for mount in secret_mounts.values())
        assert {mount.source for mount in secret_mounts.values()} == {
            f"/host/browser-credentials/{runtime_instance_id}/user-password",
            f"/host/browser-credentials/{runtime_instance_id}/admin-password",
        }
        assert "NEKO_WEBRTC_ICELITE" not in context.environment
        assert "NEKO_WEBRTC_UDPMUX" not in context.environment
        assert "NEKO_WEBRTC_NAT1TO1" not in context.environment
        assert context.environment["AILERON_RUNTIME_INSTANCE_ID"] == runtime_instance_id
        assert "AILERON_KB_MOUNT_REVISION" not in context.environment
        assert "RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE" not in context.environment
        assert not hasattr(context, "ports")

    def test_update_browser_runtime_marks_credential_as_observed(
        self, provision_service, sample_workspace
    ) -> None:
        sample_workspace.browser_credential_revision = 1
        sample_workspace.browser_credential_key_id = "test-browser-key"
        sample_workspace.browser_credential_algorithm = "hkdf-sha256-v1"
        sample_workspace.browser_credential_observed_revision = 0
        sample_workspace.browser_credential_observed_key_id = None
        sample_workspace.browser_credential_observed_algorithm = None

        provision_service._update_browser_runtime(
            sample_workspace,
            RuntimeInfo(
                identifier="browser-container-id",
                internal_url="http://browser:6080",
            ),
        )

        assert sample_workspace.browser_status == "running"
        assert sample_workspace.browser_credential_observed_revision == 1
        assert sample_workspace.browser_credential_observed_key_id == "test-browser-key"
        assert (
            sample_workspace.browser_credential_observed_algorithm == "hkdf-sha256-v1"
        )

    def test_update_browser_runtime_observes_rotated_credential(
        self, provision_service, sample_workspace
    ) -> None:
        sample_workspace.browser_credential_revision = 3
        sample_workspace.browser_credential_key_id = "rotated-browser-key"
        sample_workspace.browser_credential_algorithm = "hkdf-sha256-v1"
        sample_workspace.browser_credential_observed_revision = 2
        sample_workspace.browser_credential_observed_key_id = "test-browser-key"
        sample_workspace.browser_credential_observed_algorithm = "hkdf-sha256-v1"

        provision_service._update_browser_runtime(
            sample_workspace,
            RuntimeInfo(
                identifier="browser-container-id",
                internal_url="http://browser:6080",
            ),
        )

        assert sample_workspace.browser_credential_observed_revision == 3
        assert (
            sample_workspace.browser_credential_observed_key_id == "rotated-browser-key"
        )

    def test_update_workspace_runtime(
        self, provision_service, sample_workspace, mock_db_session
    ):
        """Test: update workspace runtime info"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        info = RuntimeInfo(
            identifier="c-123",
            internal_url="http://internal:3002",
            extra_info={"container_name": "ws-123"},
        )

        # Act
        provision_service._update_workspace_runtime(sample_workspace, info)

        # Assert
        assert sample_workspace.runtime_container_id == "c-123"
        assert sample_workspace.runtime_internal_url == "http://internal:3002"
        assert sample_workspace.terminal_internal_url == "http://internal:3004"
