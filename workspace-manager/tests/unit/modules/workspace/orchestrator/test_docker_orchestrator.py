from unittest.mock import MagicMock, patch

import docker
import pytest

from app.modules.workspace.orchestrator.base import (
    ContainerCreationError,
    VolumeSourceValidationError,
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from app.modules.workspace.orchestrator.docker_orchestrator import DockerOrchestrator
from app.modules.workspace.orchestrator.models import (
    ExecutionPlaneInfo,
    NetworkConfig,
    RuntimeContext,
    RuntimeInfo,
    VolumeMount,
    VolumeSourceIdentity,
)


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.DOCKER_NETWORK = "test-network"
    settings.MANAGER_BROWSER_CREDENTIALS_DIR = (
        "/tmp/aileron-test-browser-credentials-not-present"
    )
    return settings


@pytest.fixture
def docker_orchestrator(mock_settings):
    with patch("docker.from_env"):
        yield DockerOrchestrator(mock_settings)


@pytest.fixture
def sample_workspace():
    workspace = MagicMock()
    workspace.id = "test-ws-123"
    workspace.runtime_instance_id = None
    workspace.browser_instance_id = None
    workspace.canvas_instance_id = None
    workspace.runtime_internal_port = 3002
    workspace.browser_webrtc_internal_port = 6080
    workspace.canvas_internal_port = 3003
    return workspace


@pytest.fixture
def sample_context():
    return RuntimeContext(
        environment={"KEY": "VALUE"},
        volumes=[VolumeMount(source="/host/path", target="/container/path")],
        network=NetworkConfig(network_name="test-net"),
        labels={"image": "test-image"},
        container_labels={
            "aileron.component_instance_id": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
        },
        restart_policy="always",
    )


class TestDockerOrchestrator:
    @staticmethod
    def _execution_plane(instance_id: str) -> ExecutionPlaneInfo:
        return ExecutionPlaneInfo(
            runtime_instance_id=instance_id,
            runtime=RuntimeInfo("runtime", "http://runtime"),
            browser=RuntimeInfo("browser", "http://browser"),
            canvas=RuntimeInfo("canvas", "http://canvas"),
        )

    def test_terminate_execution_plane_removes_browser_credential_generation(
        self,
        docker_orchestrator,
        mock_settings,
        tmp_path,
        monkeypatch,
    ):
        instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        credential_root = tmp_path / "browser-credentials"
        generation_directory = credential_root / instance_id
        generation_directory.mkdir(parents=True, mode=0o700)
        for filename in ("user-password", "admin-password"):
            credential_file = generation_directory / filename
            credential_file.write_text("secret", encoding="utf-8")
            credential_file.chmod(0o600)
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(credential_root)
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            MagicMock(),
        )

        docker_orchestrator.terminate_execution_plane(
            self._execution_plane(instance_id),
            assert_claim=lambda: None,
        )

        assert not generation_directory.exists()
        assert credential_root.is_dir()

    def test_terminate_execution_plane_rejects_symlinked_browser_credential_generation(
        self,
        docker_orchestrator,
        mock_settings,
        tmp_path,
        monkeypatch,
    ):
        instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        credential_root = tmp_path / "browser-credentials"
        credential_root.mkdir(mode=0o700)
        external_directory = tmp_path / "external"
        external_directory.mkdir()
        external_secret = external_directory / "user-password"
        external_secret.write_text("must-remain", encoding="utf-8")
        (credential_root / instance_id).symlink_to(
            external_directory,
            target_is_directory=True,
        )
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(credential_root)
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            MagicMock(),
        )

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.terminate_execution_plane(
                self._execution_plane(instance_id),
                assert_claim=lambda: None,
            )

        assert external_secret.read_text(encoding="utf-8") == "must-remain"

    def test_terminate_execution_plane_rejects_browser_credential_path_escape(
        self,
        docker_orchestrator,
        mock_settings,
        tmp_path,
        monkeypatch,
    ):
        credential_root = tmp_path / "browser-credentials"
        credential_root.mkdir(mode=0o700)
        external_secret = tmp_path / "must-remain"
        external_secret.write_text("must-remain", encoding="utf-8")
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(credential_root)
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            MagicMock(),
        )

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.terminate_execution_plane(
                self._execution_plane("../../must-remain"),
                assert_claim=lambda: None,
            )

        assert external_secret.read_text(encoding="utf-8") == "must-remain"

    def test_replace_browser_removes_only_previous_credential_generation(
        self,
        docker_orchestrator,
        mock_settings,
        sample_workspace,
        sample_context,
        tmp_path,
        monkeypatch,
    ):
        previous_instance_id = "a1e4b143-628e-46e2-8ab0-df8687eb163c"
        next_instance_id = "b1e4b143-628e-46e2-8ab0-df8687eb163c"
        credential_root = tmp_path / "browser-credentials"
        for instance_id in (previous_instance_id, next_instance_id):
            generation_directory = credential_root / instance_id
            generation_directory.mkdir(parents=True, mode=0o700)
            for filename in ("user-password", "admin-password"):
                credential_file = generation_directory / filename
                credential_file.write_text(instance_id, encoding="utf-8")
                credential_file.chmod(0o600)
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(credential_root)
        sample_workspace.browser_instance_id = previous_instance_id
        sample_workspace.browser_container_id = "old-browser"
        sample_context.container_labels["aileron.component_instance_id"] = (
            next_instance_id
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_chrome_runtime",
            MagicMock(return_value=RuntimeInfo("browser", "http://browser")),
        )

        docker_orchestrator.replace_workspace_component(
            workspace=sample_workspace,
            component="browser",
            context=sample_context,
            assert_claim=lambda: None,
        )

        assert not (credential_root / previous_instance_id).exists()
        assert (credential_root / next_instance_id).is_dir()

    def test_terminate_workspace_without_runtime_identity_cleans_browser_credentials_after_absence_proof(
        self,
        docker_orchestrator,
        mock_settings,
        sample_workspace,
        tmp_path,
        monkeypatch,
    ):
        browser_instance_id = "a1e4b143-628e-46e2-8ab0-df8687eb163c"
        credential_root = tmp_path / "browser-credentials"
        generation_directory = credential_root / browser_instance_id
        generation_directory.mkdir(parents=True, mode=0o700)
        for filename in ("user-password", "admin-password"):
            credential_file = generation_directory / filename
            credential_file.write_text("secret", encoding="utf-8")
            credential_file.chmod(0o600)
        mock_settings.MANAGER_BROWSER_CREDENTIALS_DIR = str(credential_root)
        sample_workspace.runtime_instance_id = None
        sample_workspace.browser_instance_id = browser_instance_id
        prove_absent = MagicMock()
        monkeypatch.setattr(
            docker_orchestrator,
            "prove_workspace_execution_plane_absent",
            prove_absent,
        )

        docker_orchestrator.terminate_workspace_execution_plane(
            sample_workspace,
            assert_claim=lambda: None,
        )

        prove_absent.assert_called_once()
        assert not generation_directory.exists()

    def test_create_chrome_runtime_rejects_plaintext_browser_credentials(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        sample_context.environment.update(
            {
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD": "plaintext-user-secret",
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD": "plaintext-admin-secret",
            }
        )

        with pytest.raises(ContainerCreationError):
            docker_orchestrator.create_chrome_runtime(
                sample_workspace,
                sample_context,
            )

        docker_orchestrator.client.containers.run.assert_not_called()

    def test_create_chrome_runtime_requires_read_only_browser_credential_mounts(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        sample_context.environment.update(
            {
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE": (
                    "/run/secrets/browser-credentials/user-password"
                ),
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": (
                    "/run/secrets/browser-credentials/admin-password"
                ),
            }
        )

        with pytest.raises(ContainerCreationError):
            docker_orchestrator.create_chrome_runtime(
                sample_workspace,
                sample_context,
            )

        docker_orchestrator.client.containers.run.assert_not_called()

    def test_create_chrome_runtime_passes_only_secret_file_paths_to_docker(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        user_target = "/run/secrets/browser-credentials/user-password"
        admin_target = "/run/secrets/browser-credentials/admin-password"
        sample_context.environment.update(
            {
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE": user_target,
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": admin_target,
            }
        )
        sample_context.volumes.extend(
            [
                VolumeMount(
                    source="/host/browser-credentials/generation/user-password",
                    target=user_target,
                    read_only=True,
                ),
                VolumeMount(
                    source="/host/browser-credentials/generation/admin-password",
                    target=admin_target,
                    read_only=True,
                ),
            ]
        )
        container = MagicMock(id="browser-container")
        docker_orchestrator.client.containers.run.return_value = container
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        result = docker_orchestrator.create_chrome_runtime(
            sample_workspace,
            sample_context,
        )

        assert result.identifier == "browser-container"
        call_args = docker_orchestrator.client.containers.run.call_args.kwargs
        assert call_args["environment"] == sample_context.environment
        assert "NEKO_MEMBER_MULTIUSER_USER_PASSWORD" not in call_args["environment"]
        assert "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD" not in call_args["environment"]
        assert call_args["volumes"][
            "/host/browser-credentials/generation/user-password"
        ] == {"bind": user_target, "mode": "ro"}
        assert call_args["volumes"][
            "/host/browser-credentials/generation/admin-password"
        ] == {"bind": admin_target, "mode": "ro"}

    def test_create_workspace_runtime_success(
        self, docker_orchestrator, sample_workspace, sample_context
    ):
        # Arrange
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.attrs = {"Created": "2023-01-01T00:00:00Z"}
        docker_orchestrator.client.containers.run.return_value = mock_container
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        # Act
        info = docker_orchestrator.create_workspace_runtime(
            sample_workspace, sample_context
        )

        # Assert
        assert info.identifier == "container-123"
        assert info.internal_url == "http://workspace-runtime-test-ws-123:3002"
        assert info.extra_info == {"container_name": "workspace-runtime-test-ws-123"}

        docker_orchestrator.client.containers.run.assert_called_once()
        call_args = docker_orchestrator.client.containers.run.call_args[1]
        assert call_args["image"] == "test-image"
        assert call_args["environment"] == {"KEY": "VALUE"}
        assert call_args["network"] == "test-net"
        assert "ports" not in call_args
        assert call_args["security_opt"] == ["seccomp=unconfined"]
        assert call_args["tmpfs"] == {
            "/home/developer/.codex/tmp": "rw,exec,nosuid,size=16m,mode=1777"
        }
        assert call_args["restart_policy"] == {"Name": "always"}
        assert call_args["labels"] == sample_context.container_labels

    def test_create_workspace_runtime_removes_container_when_metadata_fails(
        self, docker_orchestrator, sample_workspace, sample_context
    ):
        partial_container = MagicMock()
        partial_container.id = "partial-runtime-container"
        partial_container.reload.side_effect = RuntimeError("metadata failed")
        docker_orchestrator.client.containers.run.return_value = partial_container
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        with pytest.raises(ContainerCreationError, match="metadata failed"):
            docker_orchestrator.create_workspace_runtime(
                sample_workspace,
                sample_context,
                _replace_existing=False,
            )

        partial_container.remove.assert_called_once_with(force=True)

    def test_create_browser_connectivity_probe_shares_browser_namespace(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        probe_context = RuntimeContext(
            environment={"TURN_PROBE_IDENTITY": "backend:workspace:generation"},
            volumes=[
                VolumeMount(
                    source="/host/profile.json",
                    target="/run/secrets/turn/profile.json",
                    read_only=True,
                )
            ],
            labels={
                "image": "operator:test",
                "command": "--mode=browser-connectivity-probe",
                "working_dir": "/app",
            },
            container_labels={
                "aileron.component_instance_id": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                "aileron.workload": "browser-connectivity-probe",
            },
            restart_policy="always",
        )
        probe = MagicMock()
        probe.id = "probe-container"
        docker_orchestrator.client.containers.run.return_value = probe

        result = docker_orchestrator.create_browser_connectivity_probe(
            sample_workspace,
            probe_context,
            browser_container_id="browser-container",
        )

        assert result.identifier == "probe-container"
        assert result.internal_url == ("http://workspace-browser-test-ws-123:8082")
        call_args = docker_orchestrator.client.containers.run.call_args.kwargs
        assert call_args["network_mode"] == "container:browser-container"
        assert "ports" not in call_args
        assert call_args["read_only"] is True
        assert call_args["cap_drop"] == ["ALL"]
        assert call_args["security_opt"] == ["no-new-privileges:true"]
        assert call_args["labels"] == probe_context.container_labels

    def test_recreate_execution_plane_rejects_orphaned_container_ids_without_a_generation(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        # No generation was ever recorded, yet a container id is present -
        # this combination shouldn't occur from normal writes, so treat it
        # as corrupted state rather than guessing what to do with it.
        sample_workspace.runtime_instance_id = None
        sample_workspace.runtime_container_id = "runtime-old"
        sample_workspace.browser_container_id = None
        sample_workspace.canvas_container_id = None

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.recreate_workspace_execution_plane(
                workspace=sample_workspace,
                runtime_instance_id=("f1e4b143-628e-46e2-8ab0-df8687eb163c"),
                runtime_context=sample_context,
                browser_context=sample_context,
                canvas_context=sample_context,
                assert_claim=lambda: None,
            )

        docker_orchestrator.client.containers.get.assert_not_called()
        docker_orchestrator.client.containers.run.assert_not_called()

    def test_recreate_execution_plane_falls_back_to_deterministic_name_for_missing_component_id(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        monkeypatch,
    ):
        # The runtime component never confirmed its container id (e.g. it
        # crash-looped on startup before the id could be persisted), while
        # browser/canvas did. Recreate must still be able to fence the prior
        # generation instead of refusing outright, the same way delete does.
        sample_workspace.runtime_instance_id = "a1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = "browser-old"
        sample_workspace.canvas_container_id = "canvas-old"

        terminate = MagicMock()
        monkeypatch.setattr(
            docker_orchestrator, "_terminate_exact_container", terminate
        )
        monkeypatch.setattr(
            docker_orchestrator, "_require_container_absent", MagicMock()
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_workspace_runtime",
            MagicMock(return_value=MagicMock(identifier="runtime-new")),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_chrome_runtime",
            MagicMock(return_value=MagicMock(identifier="browser-new")),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_canvas_runtime",
            MagicMock(return_value=MagicMock(identifier="canvas-new")),
        )

        result = docker_orchestrator.recreate_workspace_execution_plane(
            workspace=sample_workspace,
            runtime_instance_id="f1e4b143-628e-46e2-8ab0-df8687eb163c",
            runtime_context=sample_context,
            browser_context=sample_context,
            canvas_context=sample_context,
            assert_claim=lambda: None,
        )

        terminated_ids = [call.args[0] for call in terminate.call_args_list]
        assert terminated_ids == [
            "workspace-runtime-test-ws-123",
            "browser-old",
            "workspace-browser-connectivity-probe-test-ws-123",
            "canvas-old",
        ]
        assert result.runtime.identifier == "runtime-new"

    def test_recreate_execution_plane_fences_each_component_generation(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        monkeypatch,
    ):
        sample_workspace.runtime_instance_id = "a1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.browser_instance_id = "b1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.canvas_instance_id = "c1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = "runtime-old"
        sample_workspace.browser_container_id = "browser-old"
        sample_workspace.canvas_container_id = "canvas-old"

        terminate = MagicMock()
        monkeypatch.setattr(
            docker_orchestrator, "_terminate_exact_container", terminate
        )
        monkeypatch.setattr(
            docker_orchestrator, "_require_container_absent", MagicMock()
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_workspace_runtime",
            MagicMock(return_value=MagicMock(identifier="runtime-new")),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_chrome_runtime",
            MagicMock(return_value=MagicMock(identifier="browser-new")),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_canvas_runtime",
            MagicMock(return_value=MagicMock(identifier="canvas-new")),
        )

        docker_orchestrator.recreate_workspace_execution_plane(
            workspace=sample_workspace,
            runtime_instance_id="f1e4b143-628e-46e2-8ab0-df8687eb163c",
            runtime_context=sample_context,
            browser_context=sample_context,
            canvas_context=sample_context,
            assert_claim=lambda: None,
        )

        assert [
            (
                call.args[0],
                call.kwargs["expected_component_instance_id"],
            )
            for call in terminate.call_args_list
        ] == [
            (
                "runtime-old",
                "a1e4b143-628e-46e2-8ab0-df8687eb163c",
            ),
            (
                "browser-old",
                "b1e4b143-628e-46e2-8ab0-df8687eb163c",
            ),
            (
                "workspace-browser-connectivity-probe-test-ws-123",
                "b1e4b143-628e-46e2-8ab0-df8687eb163c",
            ),
            (
                "canvas-old",
                "c1e4b143-628e-46e2-8ab0-df8687eb163c",
            ),
        ]

    def test_replace_browser_fences_only_persisted_browser_generation(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        monkeypatch,
    ):
        sample_workspace.browser_instance_id = "b1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.browser_container_id = "browser-old"
        terminate = MagicMock()
        require_absent = MagicMock()
        create_browser = MagicMock(return_value=MagicMock(identifier="browser-new"))
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            terminate,
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            require_absent,
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_chrome_runtime",
            create_browser,
        )

        result = docker_orchestrator.replace_workspace_component(
            workspace=sample_workspace,
            component="browser",
            context=sample_context,
            assert_claim=lambda: None,
        )

        assert [(call.args, call.kwargs) for call in terminate.call_args_list] == [
            (
                ("workspace-browser-connectivity-probe-test-ws-123",),
                {
                    "expected_component_instance_id": sample_workspace.browser_instance_id,
                },
            ),
            (
                ("browser-old",),
                {
                    "expected_component_instance_id": sample_workspace.browser_instance_id,
                },
            ),
        ]
        assert [(call.args, call.kwargs) for call in require_absent.call_args_list] == [
            (("workspace-browser-connectivity-probe-test-ws-123",), {}),
            (("browser-old",), {}),
        ]
        create_browser.assert_called_once_with(
            sample_workspace,
            sample_context,
            _replace_existing=False,
        )
        assert result.identifier == "browser-new"

    def test_recreate_execution_plane_requires_absence_proof_before_create(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        monkeypatch,
    ):
        sample_workspace.runtime_instance_id = "a1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = "runtime-old"
        sample_workspace.browser_container_id = "browser-old"
        sample_workspace.canvas_container_id = "canvas-old"
        monkeypatch.setattr(
            docker_orchestrator,
            "_terminate_exact_container",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_require_container_absent",
            MagicMock(
                side_effect=WorkspaceRuntimeTerminationUnconfirmedError(
                    "absence not proven"
                )
            ),
        )
        create_runtime = MagicMock()
        monkeypatch.setattr(
            docker_orchestrator,
            "create_workspace_runtime",
            create_runtime,
        )

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.recreate_workspace_execution_plane(
                workspace=sample_workspace,
                runtime_instance_id=("f1e4b143-628e-46e2-8ab0-df8687eb163c"),
                runtime_context=sample_context,
                browser_context=sample_context,
                canvas_context=sample_context,
                assert_claim=lambda: None,
            )

        create_runtime.assert_not_called()

    def test_recreate_execution_plane_proves_deterministic_names_absent_without_persisted_identity(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
    ):
        sample_workspace.runtime_instance_id = None
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = None
        sample_workspace.canvas_container_id = None
        docker_orchestrator.client.containers.get.return_value = MagicMock()

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.recreate_workspace_execution_plane(
                workspace=sample_workspace,
                runtime_instance_id=("f1e4b143-628e-46e2-8ab0-df8687eb163c"),
                runtime_context=sample_context,
                browser_context=sample_context,
                canvas_context=sample_context,
                assert_claim=lambda: None,
            )

        docker_orchestrator.client.containers.get.assert_called_once_with(
            "workspace-runtime-test-ws-123"
        )
        docker_orchestrator.client.containers.run.assert_not_called()

    def test_recreate_execution_plane_cleans_container_created_before_runtime_info(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        monkeypatch,
    ):
        sample_workspace.runtime_instance_id = None
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = None
        sample_workspace.canvas_container_id = None
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        terminate = MagicMock()
        require_absent = MagicMock()
        monkeypatch.setattr(
            docker_orchestrator, "_terminate_exact_container", terminate
        )
        monkeypatch.setattr(
            docker_orchestrator, "_require_container_absent", require_absent
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "_remove_browser_credential_generation",
            MagicMock(),
        )
        monkeypatch.setattr(
            docker_orchestrator,
            "create_workspace_runtime",
            MagicMock(side_effect=ContainerCreationError("runtime metadata failed")),
        )

        with pytest.raises(ContainerCreationError, match="runtime metadata failed"):
            docker_orchestrator.recreate_workspace_execution_plane(
                workspace=sample_workspace,
                runtime_instance_id="f1e4b143-628e-46e2-8ab0-df8687eb163c",
                runtime_context=sample_context,
                browser_context=sample_context,
                canvas_context=sample_context,
                assert_claim=lambda: None,
            )

        terminate.assert_called_once_with(
            "workspace-runtime-test-ws-123",
            expected_component_instance_id="f1e4b143-628e-46e2-8ab0-df8687eb163c",
        )
        require_absent.assert_called_once_with("workspace-runtime-test-ws-123")

    def test_terminate_workspace_execution_plane_falls_back_to_deterministic_name(
        self,
        docker_orchestrator,
        sample_workspace,
    ):
        # The runtime component failed before its container ID could be
        # persisted (e.g. it crash-looped on startup), so runtime_container_id
        # is None even though the generation's instance ID was recorded and
        # the browser/canvas components came up fine.
        sample_workspace.runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = "browser-container"
        sample_workspace.canvas_container_id = "canvas-container"

        containers_by_id = {
            "workspace-runtime-test-ws-123": MagicMock(
                status="running",
                attrs={
                    "Config": {
                        "Labels": {
                            "aileron.component_instance_id": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                        },
                    },
                },
            ),
            "browser-container": MagicMock(
                status="running",
                attrs={
                    "Config": {
                        "Labels": {
                            "aileron.component_instance_id": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                        },
                    },
                },
            ),
            "canvas-container": MagicMock(
                status="running",
                attrs={
                    "Config": {
                        "Labels": {
                            "aileron.component_instance_id": "f1e4b143-628e-46e2-8ab0-df8687eb163c",
                        },
                    },
                },
            ),
        }

        original_containers = dict(containers_by_id)
        removed_ids: set[str] = set()

        def get_container(identifier):
            if identifier in removed_ids:
                raise docker.errors.NotFound("Not found")
            container = containers_by_id.get(identifier)
            if container is None:
                raise docker.errors.NotFound("Not found")
            return container

        def make_reload_after_stop(container):
            # First reload (before stop()) leaves it running; the second
            # (after stop()) reports it exited - matching real Docker
            # behavior where stop() is what actually changes the status.
            def reload():
                if container.stop.called:
                    container.status = "exited"

            return reload

        def remove_container(identifier):
            removed_ids.add(identifier)

        for identifier, container in containers_by_id.items():
            container.reload.side_effect = make_reload_after_stop(container)
            container.remove.side_effect = lambda i=identifier: remove_container(i)

        docker_orchestrator.client.containers.get.side_effect = get_container

        docker_orchestrator.terminate_workspace_execution_plane(
            sample_workspace,
            assert_claim=lambda: None,
        )

        get_calls = [
            call.args[0]
            for call in docker_orchestrator.client.containers.get.call_args_list
        ]
        assert "workspace-runtime-test-ws-123" in get_calls
        assert "browser-container" in get_calls
        assert "canvas-container" in get_calls
        for container in original_containers.values():
            container.stop.assert_called_once_with(timeout=120)
            container.remove.assert_called_once()

    def test_terminate_workspace_execution_plane_tolerates_missing_container_never_created(
        self,
        docker_orchestrator,
        sample_workspace,
    ):
        # No container was ever created under the deterministic name (the
        # component failed before Docker even created it), so terminate must
        # treat this as already-absent rather than raising.
        sample_workspace.runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = "browser-container"
        sample_workspace.canvas_container_id = "canvas-container"

        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        docker_orchestrator.terminate_workspace_execution_plane(
            sample_workspace,
            assert_claim=lambda: None,
        )

    def test_current_execution_plane_requires_all_matching_running_containers(
        self,
        docker_orchestrator,
        sample_workspace,
    ):
        runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_instance_id = runtime_instance_id
        sample_workspace.browser_instance_id = runtime_instance_id
        sample_workspace.canvas_instance_id = runtime_instance_id
        sample_workspace.runtime_container_id = "runtime-container"
        sample_workspace.browser_container_id = "browser-container"
        sample_workspace.canvas_container_id = "canvas-container"
        containers = {}
        for workload in ("runtime", "browser", "canvas"):
            container = MagicMock(
                status="running",
                attrs={
                    "Config": {
                        "Labels": {
                            "aileron.workspace_id": sample_workspace.id,
                            "aileron.workload": workload,
                            "aileron.component_instance_id": runtime_instance_id,
                        }
                    }
                },
            )
            containers[f"{workload}-container"] = container
        docker_orchestrator.client.containers.get.side_effect = containers.__getitem__

        assert (
            docker_orchestrator.is_workspace_execution_plane_current(sample_workspace)
            is True
        )

        containers["browser-container"].attrs["Config"]["Labels"][
            "aileron.component_instance_id"
        ] = "22222222-2222-4222-8222-222222222222"
        assert (
            docker_orchestrator.is_workspace_execution_plane_current(sample_workspace)
            is False
        )

    def test_current_execution_plane_reports_missing_container_as_drift(
        self,
        docker_orchestrator,
        sample_workspace,
    ):
        sample_workspace.runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound(
            "Not found"
        )

        assert (
            docker_orchestrator.is_workspace_execution_plane_current(sample_workspace)
            is False
        )

    def test_terminate_exact_container_stops_restarting_container(
        self,
        docker_orchestrator,
    ):
        runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        container = MagicMock(
            status="restarting",
            attrs={
                "Config": {
                    "Labels": {
                        "aileron.component_instance_id": runtime_instance_id,
                    },
                },
            },
        )

        def reload_container():
            if container.stop.called:
                container.status = "exited"

        container.reload.side_effect = reload_container
        docker_orchestrator.client.containers.get.return_value = container

        docker_orchestrator._terminate_exact_container(
            "runtime-container",
            expected_component_instance_id=runtime_instance_id,
        )

        container.stop.assert_called_once_with(timeout=120)
        container.remove.assert_called_once()

    def test_terminate_workspace_execution_plane_rejects_deterministic_name_identity_mismatch(
        self,
        docker_orchestrator,
        sample_workspace,
    ):
        # A container exists under the deterministic name, but it belongs to
        # a different generation - never terminate it on a guess.
        sample_workspace.runtime_instance_id = "f1e4b143-628e-46e2-8ab0-df8687eb163c"
        sample_workspace.runtime_container_id = None
        sample_workspace.browser_container_id = "browser-container"
        sample_workspace.canvas_container_id = "canvas-container"

        mismatched = MagicMock(
            attrs={
                "Config": {
                    "Labels": {
                        "aileron.component_instance_id": "some-other-generation"
                    },
                },
            },
        )
        docker_orchestrator.client.containers.get.return_value = mismatched

        with pytest.raises(WorkspaceRuntimeTerminationUnconfirmedError):
            docker_orchestrator.terminate_workspace_execution_plane(
                sample_workspace,
                assert_claim=lambda: None,
            )

        mismatched.stop.assert_not_called()
        mismatched.remove.assert_not_called()

    def test_create_workspace_runtime_stops_and_inspects_before_replacement(
        self, docker_orchestrator, sample_workspace, sample_context
    ):
        events = []
        mock_existing = MagicMock()
        mock_existing.status = "running"
        mock_container = MagicMock()
        mock_container.id = "replacement-container"

        def reload_existing():
            events.append("reload")
            if events.count("reload") == 2:
                mock_existing.status = "exited"

        mock_existing.reload.side_effect = reload_existing
        mock_existing.stop.side_effect = lambda **kwargs: events.append(
            ("stop", kwargs)
        )
        mock_existing.remove.side_effect = lambda **kwargs: events.append(
            ("remove", kwargs)
        )
        docker_orchestrator.client.containers.get.return_value = mock_existing
        docker_orchestrator.client.containers.run.return_value = mock_container
        docker_orchestrator.client.containers.run.side_effect = lambda **kwargs: (
            events.append("run") or mock_container
        )

        docker_orchestrator.create_workspace_runtime(sample_workspace, sample_context)

        assert events == [
            "reload",
            ("stop", {"timeout": 120}),
            "reload",
            ("remove", {}),
            "run",
        ]

    def test_create_workspace_runtime_does_not_run_when_stop_times_out(
        self, docker_orchestrator, sample_workspace, sample_context
    ):
        mock_existing = MagicMock()
        mock_existing.status = "running"
        mock_existing.stop.side_effect = docker.errors.APIError("stop timed out")
        docker_orchestrator.client.containers.get.return_value = mock_existing

        with pytest.raises(ContainerCreationError):
            docker_orchestrator.create_workspace_runtime(
                sample_workspace, sample_context
            )

        docker_orchestrator.client.containers.run.assert_not_called()
        mock_existing.remove.assert_not_called()

    def test_create_workspace_runtime_does_not_run_when_container_remains_running(
        self, docker_orchestrator, sample_workspace, sample_context
    ):
        mock_existing = MagicMock()
        mock_existing.status = "running"
        docker_orchestrator.client.containers.get.return_value = mock_existing

        with pytest.raises(ContainerCreationError):
            docker_orchestrator.create_workspace_runtime(
                sample_workspace, sample_context
            )

        assert mock_existing.reload.call_count == 2
        mock_existing.stop.assert_called_once_with(timeout=120)
        mock_existing.remove.assert_not_called()
        docker_orchestrator.client.containers.run.assert_not_called()

    def test_create_workspace_runtime_rejects_missing_fenced_source_before_stop(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        tmp_path,
    ):
        source = tmp_path / "knowledge-base"
        source.mkdir()
        source_stat = source.stat()
        sample_context.volumes = [
            VolumeMount(
                source="/host/knowledge-base",
                target="/knowledge/docs",
                read_only=True,
                source_identity=VolumeSourceIdentity(
                    validation_path=str(source),
                    device=source_stat.st_dev,
                    inode=source_stat.st_ino,
                ),
            )
        ]
        source.rmdir()

        with pytest.raises(VolumeSourceValidationError) as exc_info:
            docker_orchestrator.create_workspace_runtime(
                sample_workspace,
                sample_context,
            )

        assert exc_info.value.code == "KB_MOUNT_SOURCE_INVALID"
        docker_orchestrator.client.containers.get.assert_not_called()
        docker_orchestrator.client.containers.run.assert_not_called()

    def test_create_workspace_runtime_revalidates_source_after_old_runtime_stop(
        self,
        docker_orchestrator,
        sample_workspace,
        sample_context,
        tmp_path,
        monkeypatch,
    ):
        source = tmp_path / "knowledge-base"
        source.mkdir()
        source_stat = source.stat()
        sample_context.volumes = [
            VolumeMount(
                source="/host/knowledge-base",
                target="/knowledge/docs",
                read_only=True,
                source_identity=VolumeSourceIdentity(
                    validation_path=str(source),
                    device=source_stat.st_dev,
                    inode=source_stat.st_ino,
                ),
            )
        ]

        def replace_source(_container_name):
            source.rename(tmp_path / "old-knowledge-base")
            source.mkdir()

        monkeypatch.setattr(
            docker_orchestrator,
            "_stop_and_remove_existing_runtime",
            replace_source,
        )

        with pytest.raises(VolumeSourceValidationError) as exc_info:
            docker_orchestrator.create_workspace_runtime(
                sample_workspace,
                sample_context,
            )

        assert exc_info.value.code == "KB_MOUNT_SOURCE_INVALID"
        docker_orchestrator.client.containers.run.assert_not_called()
