"""Workspace runtime provisioning service and strategy implementation"""

from __future__ import annotations

import logging
import os
import stat
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.knowledge_base.mount_contract import validate_mount_alias
from app.modules.knowledge_base.mount_snapshot import canonical_mount_snapshot
from app.modules.knowledge_base.mount_topology import contains_nested_mount
from app.modules.workspace.browser_credentials import BrowserCredentialService
from app.modules.workspace.environment import (
    WorkspaceEnvironmentError,
    ensure_unique_workspace_env_key,
    validate_workspace_env_key,
)
from app.modules.workspace.orchestrator.factory import OrchestratorFactory
from app.modules.workspace.orchestrator.models import (
    ExecutionPlaneInfo,
    NetworkConfig,
    RuntimeContext,
    RuntimeInfo,
    VolumeMount,
    VolumeSourceIdentity,
)
from app.modules.workspace.runtime.control_token import issue_runtime_control_token
from app.modules.workspace.runtime.database import (
    RuntimeDatabaseCredential,
    WorkspaceRuntimeDatabaseService,
)
from app.modules.workspace.templates import ScriptTemplateEngine

logger = logging.getLogger(__name__)

WORKSPACE_RESOURCES = Path(__file__).resolve().parent.parent / "resources"
TEMPLATE_ROOT = WORKSPACE_RESOURCES / "runtime_templates"
CODEX_DEFAULT_CONFIG_PATH = WORKSPACE_RESOURCES / "codex" / "config.toml"
RUNTIME_USER_HOME = Path("/home/developer")
RUNTIME_PLATFORM_DATABASE_CA_FILE = (
    "/etc/aileron/data-service-ca/platform-database/ca.crt"
)


class KnowledgeBaseMountSourceError(RuntimeError):
    """Canonical knowledge base source failed closed validation."""

    code = "KB_MOUNT_SOURCE_INVALID"


@dataclass(frozen=True)
class WorkspaceExecutionPlaneIdentity:
    """Immutable database snapshot used at the destructive boundary."""

    id: str
    provisioner: str
    runtime_instance_id: str | None
    runtime_container_id: str | None
    browser_container_id: str | None
    canvas_container_id: str | None
    runtime_internal_url: str | None
    terminal_internal_url: str | None
    runtime_internal_port: int | None = 3002
    browser_webrtc_internal_port: int | None = 6080
    canvas_internal_port: int | None = 3003
    target_namespace: str | None = None
    browser_instance_id: str | None = None
    canvas_instance_id: str | None = None


@dataclass(frozen=True)
class WorkspaceExecutionPlanePlan:
    """Prepared contexts for one new execution-plane generation."""

    workspace: WorkspaceExecutionPlaneIdentity
    runtime_instance_id: str
    mount_revision: int
    observed_mount_revision: int
    access_revision: int
    database_credential: RuntimeDatabaseCredential
    runtime_control_token: str
    runtime_context: RuntimeContext
    browser_context: RuntimeContext
    canvas_context: RuntimeContext
    browser_probe_context: RuntimeContext | None = None


class RuntimeProvisionService:
    """Service responsible for scheduling workspace runtime provisioning."""

    def __init__(
        self,
        db: Session,
        *,
        runtime_database_service: WorkspaceRuntimeDatabaseService | None = None,
    ) -> None:
        self.db = db
        self.template_engine = ScriptTemplateEngine(TEMPLATE_ROOT)
        # Dynamically get settings to ensure correct configuration in test environment
        self.settings = get_settings()
        self.script_output_root = Path(self.settings.RUNTIME_SCRIPT_ROOT)
        self.runtime_database_service = (
            runtime_database_service
            if runtime_database_service is not None
            else WorkspaceRuntimeDatabaseService()
        )

    def _prepare_generation(
        self,
        workspace: db_models.Workspace,
        *,
        runtime_instance_id: str,
    ) -> WorkspaceExecutionPlanePlan:
        """Prepare a generation without creating a durable job or committing."""

        canonical_instance_id = str(UUID(runtime_instance_id))
        if canonical_instance_id != runtime_instance_id:
            raise ValueError("Runtime instance identifier must be canonical")
        database_credential = self.runtime_database_service.prepare(
            workspace_id=workspace.id,
            runtime_instance_id=canonical_instance_id,
        )
        control_token = issue_runtime_control_token()
        workspace.runtime_control_instance_id = canonical_instance_id
        workspace.runtime_control_token_hash = control_token.digest
        runtime_context = self._build_runtime_context(
            workspace,
            canonical_instance_id,
            database_url=database_credential.database_url,
            runtime_control_token=control_token.value,
        )
        browser_context = self._build_browser_runtime_context(
            workspace,
            canonical_instance_id,
        )
        browser_probe_context = (
            self._build_browser_connectivity_probe_context(
                workspace,
                canonical_instance_id,
            )
            if workspace.provisioner == "docker"
            else None
        )
        canvas_context = self._build_canvas_runtime_context(
            workspace,
            canonical_instance_id,
        )
        return WorkspaceExecutionPlanePlan(
            workspace=WorkspaceExecutionPlaneIdentity(
                id=workspace.id,
                provisioner=workspace.provisioner,
                runtime_instance_id=workspace.runtime_instance_id,
                browser_instance_id=workspace.browser_instance_id,
                canvas_instance_id=workspace.canvas_instance_id,
                runtime_container_id=workspace.runtime_container_id,
                browser_container_id=workspace.browser_container_id,
                canvas_container_id=workspace.canvas_container_id,
                runtime_internal_url=workspace.runtime_internal_url,
                terminal_internal_url=workspace.terminal_internal_url,
                runtime_internal_port=workspace.runtime_internal_port,
                browser_webrtc_internal_port=workspace.browser_webrtc_internal_port,
                canvas_internal_port=workspace.canvas_internal_port,
                target_namespace=workspace.target_namespace,
            ),
            runtime_instance_id=canonical_instance_id,
            mount_revision=workspace.knowledge_base_mount_desired_revision,
            observed_mount_revision=(workspace.knowledge_base_mount_observed_revision),
            access_revision=workspace.runtime_access_revision,
            database_credential=database_credential,
            runtime_control_token=control_token.value,
            runtime_context=runtime_context,
            browser_context=browser_context,
            canvas_context=canvas_context,
            browser_probe_context=browser_probe_context,
        )

    def _apply_generation(
        self,
        plan: WorkspaceExecutionPlanePlan,
        *,
        assert_claim: Any,
        timeout_seconds: int,
    ) -> ExecutionPlaneInfo:
        """Create and verify one generation without database writes or commits."""

        orchestrator = OrchestratorFactory.get_orchestrator(plan.workspace.provisioner)
        self.runtime_database_service.activate(plan.database_credential)
        result: ExecutionPlaneInfo | None = None
        try:
            result = orchestrator.recreate_workspace_execution_plane(
                workspace=plan.workspace,
                runtime_instance_id=plan.runtime_instance_id,
                runtime_context=plan.runtime_context,
                browser_context=plan.browser_context,
                canvas_context=plan.canvas_context,
                assert_claim=assert_claim,
                browser_probe_context=plan.browser_probe_context,
            )
            self._wait_for_execution_plane_ready(
                result,
                assert_claim=assert_claim,
                timeout_seconds=timeout_seconds,
            )
            return result
        except Exception:
            try:
                if result is not None:
                    orchestrator.terminate_execution_plane(
                        result,
                        assert_claim=lambda: None,
                    )
            finally:
                self.runtime_database_service.deactivate(plan.database_credential)
            raise

    def _stage_generation(
        self,
        workspace: db_models.Workspace,
        result: ExecutionPlaneInfo,
    ) -> None:
        """Stage one complete generation on the caller-owned transaction."""

        if (
            workspace.runtime_instance_id != result.runtime_instance_id
            or workspace.runtime_control_instance_id != result.runtime_instance_id
            or not workspace.runtime_control_token_hash
        ):
            raise ValueError("Runtime control generation is not active")
        workspace.browser_instance_id = result.runtime_instance_id
        workspace.canvas_instance_id = result.runtime_instance_id
        self._update_workspace_runtime(workspace, result.runtime)
        self._update_browser_runtime(workspace, result.browser)
        self._update_canvas_runtime(workspace, result.canvas)
        workspace.runtime_observed_revision = workspace.runtime_desired_revision
        workspace.browser_observed_revision = workspace.browser_desired_revision
        workspace.canvas_observed_revision = workspace.canvas_desired_revision
        workspace.bootstrap_observed_revision = workspace.bootstrap_revision
        workspace.bootstrap_status = "succeeded"
        workspace.bootstrap_error_code = None
        workspace.bootstrap_last_transition_at = datetime.utcnow()

    def restart_sibling_component(
        self,
        workspace: db_models.Workspace,
        *,
        component: str,
        assert_claim: Any,
    ) -> RuntimeInfo:
        """Replace one non-Runtime Docker workload."""

        if workspace.provisioner != "docker":
            raise ValueError("Component restart requires the Docker provisioner")
        runtime_instance_id = workspace.runtime_instance_id
        if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
            raise ValueError("Workspace runtime instance is unavailable")
        component_instance_id = str(uuid4())
        orchestrator = OrchestratorFactory.get_orchestrator("docker")
        assert_claim()
        if component == "browser":
            context = self._build_browser_runtime_context(
                workspace,
                component_instance_id,
            )
            probe_context = self._build_browser_connectivity_probe_context(
                workspace,
                component_instance_id,
            )
            result = orchestrator.replace_workspace_component(
                workspace=workspace,
                component=component,
                context=context,
                assert_claim=assert_claim,
                browser_probe_context=probe_context,
            )
            result.component_instance_id = component_instance_id
            self._update_browser_runtime(workspace, result)
            workspace.browser_instance_id = component_instance_id
        elif component == "canvas":
            context = self._build_canvas_runtime_context(
                workspace,
                component_instance_id,
            )
            result = orchestrator.replace_workspace_component(
                workspace=workspace,
                component=component,
                context=context,
                assert_claim=assert_claim,
            )
            result.component_instance_id = component_instance_id
            self._update_canvas_runtime(workspace, result)
            workspace.canvas_instance_id = component_instance_id
        else:
            raise ValueError("Workspace sibling component is invalid")
        assert_claim()
        return result

    def apply_component_result(
        self,
        workspace: db_models.Workspace,
        *,
        component: str,
        result: RuntimeInfo,
    ) -> None:
        """Persist only the replaced Docker component result."""

        if component == "runtime":
            self._update_workspace_runtime(workspace, result)
        elif component == "browser":
            if not result.component_instance_id:
                raise ValueError("Browser component generation is missing")
            workspace.browser_instance_id = result.component_instance_id
            self._update_browser_runtime(workspace, result)
        elif component == "canvas":
            if not result.component_instance_id:
                raise ValueError("Canvas component generation is missing")
            workspace.canvas_instance_id = result.component_instance_id
            self._update_canvas_runtime(workspace, result)
        else:
            raise ValueError("Workspace component is invalid")

    def apply_prepared_runtime_component(
        self,
        plan: WorkspaceExecutionPlanePlan,
        *,
        assert_claim: Any,
    ) -> RuntimeInfo:
        """Apply only the Runtime workload from a prepared Docker plan."""

        orchestrator = OrchestratorFactory.get_orchestrator(plan.workspace.provisioner)
        self.runtime_database_service.activate(plan.database_credential)
        try:
            assert_claim()
            result = orchestrator.replace_workspace_component(
                workspace=plan.workspace,
                component="runtime",
                context=plan.runtime_context,
                assert_claim=assert_claim,
            )
            assert_claim()
            return result
        except Exception:
            self.runtime_database_service.deactivate(plan.database_credential)
            raise

    def _discard_generation(
        self,
        plan: WorkspaceExecutionPlanePlan,
        result: ExecutionPlaneInfo,
        *,
        assert_claim: Any,
    ) -> None:
        """Discard a completed but stale generation with exact identities."""

        orchestrator = OrchestratorFactory.get_orchestrator(plan.workspace.provisioner)
        try:
            orchestrator.terminate_execution_plane(
                result,
                assert_claim=assert_claim,
            )
        finally:
            self.runtime_database_service.deactivate(plan.database_credential)

    def _terminate_persisted_generation(
        self,
        workspace: WorkspaceExecutionPlaneIdentity,
        *,
        assert_claim: Any,
    ) -> None:
        """Terminate the exact generation persisted before a stop or delete."""

        orchestrator = OrchestratorFactory.get_orchestrator(workspace.provisioner)
        orchestrator.terminate_workspace_execution_plane(
            workspace,
            assert_claim=assert_claim,
        )
        if workspace.runtime_instance_id:
            self.runtime_database_service.deactivate(
                self.runtime_database_service.prepare(
                    workspace_id=workspace.id,
                    runtime_instance_id=workspace.runtime_instance_id,
                )
            )

    def _prove_generation_absent(
        self,
        workspace: WorkspaceExecutionPlaneIdentity,
        *,
        assert_claim: Any,
    ) -> None:
        """Prove stopped fast-path workloads are absent without DB writes."""

        orchestrator = OrchestratorFactory.get_orchestrator(workspace.provisioner)
        orchestrator.prove_workspace_execution_plane_absent(
            workspace,
            assert_claim=assert_claim,
        )

    def _wait_for_execution_plane_ready(
        self,
        result: ExecutionPlaneInfo,
        *,
        assert_claim: Any,
        timeout_seconds: int,
    ) -> None:
        """Require Runtime, Terminal, Browser, and Canvas readiness."""

        runtime_url = result.runtime.internal_url.rstrip("/") + "/health"
        terminal_url = (
            self._terminal_internal_url(result.runtime.internal_url) + "/health"
        )
        browser_url = result.browser.internal_url.rstrip("/") + "/health"
        canvas_container_name = result.canvas.extra_info.get("container_name")
        if not isinstance(canvas_container_name, str) or not canvas_container_name:
            raise RuntimeError("Canvas workload identity is invalid")
        canvas_url = f"http://{canvas_container_name}:3013/health"
        probe_evidence_url = (
            result.browser_probe.internal_url.rstrip("/") + "/v1/evidence"
            if result.browser_probe is not None
            else None
        )
        probe_urls = (runtime_url, terminal_url, browser_url, canvas_url)
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        with httpx.Client(timeout=2.0) as client:
            while time.monotonic() < deadline:
                assert_claim()
                try:
                    for probe_url in probe_urls:
                        assert_claim()
                        response = client.get(probe_url)
                        response.raise_for_status()
                    if probe_evidence_url is not None:
                        assert_claim()
                        response = client.get(probe_evidence_url)
                        response.raise_for_status()
                    assert_claim()
                    return
                except httpx.HTTPError as exc:
                    last_error = exc
                    time.sleep(1)
        raise RuntimeError(
            "Execution-plane readiness could not be verified"
        ) from last_error

    @staticmethod
    def _terminal_internal_url(runtime_internal_url: str) -> str:
        runtime_parts = urlsplit(runtime_internal_url)
        terminal_host = runtime_parts.hostname
        if not runtime_parts.scheme or not terminal_host:
            raise RuntimeError("Runtime internal URL is invalid")
        return urlunsplit(
            (
                runtime_parts.scheme,
                f"{terminal_host}:3004",
                "",
                "",
                "",
            )
        )

    def _build_runtime_context(
        self,
        workspace: db_models.Workspace,
        runtime_instance_id: str,
        *,
        database_url: str,
        runtime_control_token: str,
    ) -> RuntimeContext:
        """Build runtime context"""

        # 1. Prepare script (startup script)
        workspace_dir = self.script_output_root / workspace.id
        environment = self._build_environment(
            workspace,
            runtime_instance_id,
            database_url=database_url,
            runtime_control_token=runtime_control_token,
        )

        # Internal service ports used by the runtime startup script.
        ports_config = self._build_ports_config(workspace)

        # Render startup.sh
        self.template_engine.render_to_file(
            "docker/startup.sh.j2",
            workspace_dir / "startup.sh",
            {
                "workspace": {"id": workspace.id, "name": workspace.name},
                "environment": environment,
                "ports": ports_config,
            },
            executable=True,
        )

        # 2. Build volume mounts
        volumes = self._build_volumes(workspace)

        # 3. Build network configuration
        network = NetworkConfig(network_name=self.settings.DOCKER_NETWORK)

        # 4. Get Image
        from app.modules.container_images.catalog import get_container_image_service

        image_service = get_container_image_service()
        docker_image = image_service.get_docker_image_name(workspace.runtime)

        return RuntimeContext(
            environment=environment,
            volumes=volumes,
            network=network,
            labels={
                "image": docker_image,
                "command": "/start_services.sh",
                "working_dir": "/workspace-runtime",
            },
            container_labels=self._generation_labels(
                workspace,
                runtime_instance_id,
                workload="runtime",
            ),
        )

    def _build_environment(
        self,
        workspace: db_models.Workspace,
        runtime_instance_id: str,
        *,
        database_url: str,
        runtime_control_token: str,
    ) -> dict[str, str]:
        browser_container_name = f"workspace-browser-{workspace.id}"
        canvas_container_name = f"workspace-canvas-{workspace.id}"
        database_connection_file = self._write_runtime_secret_file(
            workspace.id,
            "runtime-database-connection",
            database_url,
        )
        control_token_file = self._write_runtime_secret_file(
            workspace.id,
            "runtime-control-token",
            runtime_control_token,
        )

        env = {
            "AILERON_WORKSPACE_ID": workspace.id,
            "AILERON_WORKSPACE_PATH": "/workspace",
            "AILERON_RUNTIME_INSTANCE_ID": runtime_instance_id,
            "AILERON_RUNTIME_ACCESS_REVISION": str(workspace.runtime_access_revision),
            "AILERON_KB_MOUNT_REVISION": str(
                workspace.knowledge_base_mount_desired_revision
            ),
            "AILERON_WORKTREE_SUBDIR": workspace.worktree_subdir,
            "AILERON_RUNTIME_DATABASE_CONNECTION_FILE": database_connection_file,
            "AILERON_RUNTIME_CONTROL_TOKEN_FILE": control_token_file,
            "AILERON_MANAGER_INTERNAL_URL": (
                f"http://workspace-manager:{self.settings.PORT}"
            ),
            "AILERON_PLATFORM_PUBLIC_ORIGIN": (self.settings.PLATFORM_PUBLIC_ORIGIN),
            "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": (
                self._runtime_assertion_public_key_set_file()
            ),
            "AILERON_RUNTIME_ASSERTION_ISSUER": (
                self.settings.RUNTIME_ASSERTION_ISSUER
            ),
            "AILERON_BROWSER_SERVICE_NAME": browser_container_name,
            "AILERON_BROWSER_WEBRTC_INTERNAL_URL": (
                workspace.browser_webrtc_internal_url
                or f"http://{browser_container_name}:6080"
            ),
            "AILERON_BROWSER_CDP_URL": f"http://{browser_container_name}:9223",
            "AILERON_CANVAS_SERVICE_NAME": canvas_container_name,
            "AILERON_CANVAS_INTERNAL_URL": (
                workspace.canvas_internal_url or f"http://{canvas_container_name}:3003"
            ),
            "AILERON_CANVAS_API_URL": f"http://{canvas_container_name}:3013",
        }

        try:
            # Get workspace owner's user settings
            user_settings = self.db.scalar(
                select(db_models.UserSetting).where(
                    db_models.UserSetting.user_id == workspace.owner_id
                )
            )

            if user_settings:
                if user_settings.ssh_private_key:
                    env["SSH_PRIVATE_KEY"] = user_settings.ssh_private_key
                if user_settings.ssh_public_key:
                    env["SSH_PUBLIC_KEY"] = user_settings.ssh_public_key
                if user_settings.git_user_name:
                    env["GIT_USER_NAME"] = user_settings.git_user_name
                if user_settings.git_user_email:
                    env["GIT_USER_EMAIL"] = user_settings.git_user_email
        except Exception as e:
            logger.warning(f"Cannot get user settings: {e}")

        seen_workspace_env_keys: set[str] = set()
        for item in workspace.env_vars or []:
            if not isinstance(item, dict):
                raise WorkspaceEnvironmentError(
                    "WORKSPACE_ENV_INVALID",
                    "workspace.env.invalid",
                    item,
                )
            key = validate_workspace_env_key(item.get("key"))
            ensure_unique_workspace_env_key(key, seen_workspace_env_keys)
            value = item.get("value")
            if not isinstance(value, str):
                raise WorkspaceEnvironmentError(
                    "WORKSPACE_ENV_VALUE_INVALID",
                    "workspace.env.value_invalid",
                    key,
                )
            env[key] = value
        return env

    def _write_runtime_secret_file(
        self,
        workspace_id: str,
        filename: str,
        value: str,
    ) -> str:
        safe_workspace_id = workspace_id.replace("-", "_")
        secret_root = (
            self._runtime_home_manager_root(safe_workspace_id) / ".aileron" / "secrets"
        )
        secret_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        secret_root.chmod(0o700)
        secret_path = secret_root / filename
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=secret_root,
                prefix=f".{filename}.",
                delete=False,
            ) as secret_file:
                secret_file.write(value)
                temporary_path = Path(secret_file.name)
            temporary_path.chmod(0o400)
            os.replace(temporary_path, secret_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return f"/run/secrets/aileron/{filename}"

    def _build_ports_config(self, workspace: db_models.Workspace) -> dict[str, Any]:
        """Build port configuration dictionary (for template rendering)"""
        default_port = workspace.runtime_internal_port or 3002
        canvas_port = workspace.canvas_internal_port or 3003
        terminal_port = 3004

        return {
            "default_internal_port": default_port,
            "canvas_internal_port": canvas_port,
            "terminal_internal_port": terminal_port,
            "mappings": [],
        }

    def _build_volumes(self, workspace: db_models.Workspace) -> list[VolumeMount]:
        safe_workspace_id = workspace.id.replace("-", "_")

        host_workspace = (
            self._resolve_host_mount_path(self.settings.HOST_WORKSPACES_DIR)
            / safe_workspace_id
        )
        host_scripts = (
            self._resolve_host_mount_path(self.settings.HOST_WORKSPACE_SCRIPTS_DIR)
            / safe_workspace_id
        )
        host_runtime_home = self._runtime_home_host_root(safe_workspace_id)
        manager_workspace = (
            Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id
        )
        manager_scripts = (
            Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id
        )
        manager_runtime_home = self._runtime_home_manager_root(safe_workspace_id)
        manager_workspace.mkdir(parents=True, exist_ok=True)
        manager_scripts.mkdir(parents=True, exist_ok=True)
        manager_runtime_home.mkdir(parents=True, exist_ok=True)
        self._write_codex_default_config(manager_runtime_home)

        custom_setup_file = manager_scripts / "custom-setup.sh"
        custom_setup_file.write_text(
            workspace.setup_script or "#!/bin/sh\nexit 0\n",
            encoding="utf-8",
        )
        custom_setup_file.chmod(0o444)

        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
            VolumeMount(source=str(host_scripts), target="/scripts"),
            VolumeMount(
                source=str(host_runtime_home),
                target=str(RUNTIME_USER_HOME),
            ),
            # Docker socket
            VolumeMount(source="/var/run/docker.sock", target="/var/run/docker.sock"),
            VolumeMount(
                source=str(
                    self._resolve_host_mount_path(
                        self.settings.HOST_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE
                    )
                ),
                target=self._runtime_assertion_public_key_set_file(),
                read_only=True,
            ),
        ]

        runtime_secret_root = host_runtime_home / ".aileron" / "secrets"
        for filename in (
            "runtime-database-connection",
            "runtime-control-token",
        ):
            volumes.append(
                VolumeMount(
                    source=str(runtime_secret_root / filename),
                    target=f"/run/secrets/aileron/{filename}",
                    read_only=True,
                )
            )

        if self.settings.HOST_PLATFORM_DATABASE_CA_CERT_FILE:
            volumes.append(
                VolumeMount(
                    source=str(
                        self._resolve_host_mount_path(
                            self.settings.HOST_PLATFORM_DATABASE_CA_CERT_FILE
                        )
                    ),
                    target=RUNTIME_PLATFORM_DATABASE_CA_FILE,
                    read_only=True,
                )
            )

        # Development mode volumes
        if self.settings.ENV.lower() in ["development", "dev"]:
            host_workspace_runtime_dir = self.settings.HOST_WORKSPACE_RUNTIME_DIR
            if host_workspace_runtime_dir:
                host_workspace_runtime = self._resolve_host_mount_path(
                    host_workspace_runtime_dir
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "app"),
                        target="/workspace-runtime/app",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "scripts"),
                        target="/workspace-runtime/scripts",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "tests"),
                        target="/workspace-runtime/tests",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "vendor"),
                        target="/workspace-runtime/vendor",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "pyproject.toml"),
                        target="/workspace-runtime/pyproject.toml",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "uv.lock"),
                        target="/workspace-runtime/uv.lock",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "supervisord.conf"),
                        target="/workspace-runtime/supervisord.conf",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "supervisord.dev.conf"),
                        target="/workspace-runtime/supervisord.dev.conf",
                    )
                )
                volumes.append(
                    VolumeMount(
                        source=str(host_workspace_runtime / "start_services.sh"),
                        target="/start_services.sh",
                    )
                )

                host_project_root = self.settings.HOST_PROJECT_ROOT
                if host_project_root:
                    host_project_root_path = self._resolve_host_mount_path(
                        host_project_root
                    )
                    volumes.append(
                        VolumeMount(
                            source=str(host_project_root_path / "packages"),
                            target="/packages",
                            read_only=True,
                        )
                    )
        volumes.extend(self.preflight_knowledge_base_mounts(workspace))
        return volumes

    def preflight_knowledge_base_mounts(
        self,
        workspace: db_models.Workspace,
    ) -> list[VolumeMount]:
        """Validate the selected mount snapshot without mutating runtime state."""

        raw_snapshot = (
            workspace.knowledge_base_mount_candidate_snapshot
            if workspace.knowledge_base_mount_sync_status
            in {"preflighting", "applying", "compensating"}
            else workspace.knowledge_base_mount_active_snapshot
        )
        try:
            mount_snapshot = canonical_mount_snapshot(raw_snapshot)
        except ValueError as exc:
            raise KnowledgeBaseMountSourceError(
                "Knowledge mount snapshot is invalid"
            ) from exc

        host_kb_root = self._resolve_host_mount_path(
            self.settings.HOST_KNOWLEDGE_BASES_DIR
        )
        manager_knowledge_bases = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        volumes: list[VolumeMount] = []
        for entry in mount_snapshot:
            kb_id = self._canonical_knowledge_base_id(entry["knowledgeBaseId"])
            mount_alias = validate_mount_alias(entry["mountAlias"])
            source_identity = self._validate_knowledge_base_source(
                manager_knowledge_bases,
                kb_id,
            )
            volumes.append(
                VolumeMount(
                    source=str(host_kb_root / kb_id),
                    target=f"/knowledge/{mount_alias}",
                    read_only=True,
                    source_identity=source_identity,
                )
            )

        return volumes

    def _runtime_assertion_public_key_set_file(self) -> str:
        value = self.settings.RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or not Path(value).is_absolute()
        ):
            raise RuntimeError(
                "Runtime assertion public key set file is not configured"
            )
        return value

    @staticmethod
    def _canonical_knowledge_base_id(value: object) -> str:
        if not isinstance(value, str):
            raise KnowledgeBaseMountSourceError("Knowledge base ID is invalid")
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise KnowledgeBaseMountSourceError("Knowledge base ID is invalid") from exc
        if str(parsed) != value:
            raise KnowledgeBaseMountSourceError("Knowledge base ID is not canonical")
        return value

    def _validate_knowledge_base_source(
        self,
        manager_root: Path,
        kb_id: str,
    ) -> VolumeSourceIdentity:
        try:
            absolute_root = manager_root.absolute()
            if manager_root.resolve(strict=True) != absolute_root:
                raise KnowledgeBaseMountSourceError(
                    "Canonical knowledge base root is unsafe"
                )
        except (OSError, RuntimeError) as exc:
            raise KnowledgeBaseMountSourceError(
                "Canonical knowledge base root is unavailable"
            ) from exc

        root_flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            root_flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            root_flags |= os.O_NOFOLLOW

        try:
            root_fd = os.open(manager_root, root_flags)
        except OSError as exc:
            raise KnowledgeBaseMountSourceError(
                "Canonical knowledge base root is unavailable"
            ) from exc

        try:
            try:
                source_fd = os.open(kb_id, root_flags, dir_fd=root_fd)
            except OSError as exc:
                raise KnowledgeBaseMountSourceError(
                    "Canonical knowledge base source is unavailable"
                ) from exc
            try:
                root_stat = os.fstat(root_fd)
                source_stat = os.fstat(source_fd)
                source_path = manager_root / kb_id
                source_lstat = source_path.lstat()
                if (
                    not stat.S_ISDIR(root_stat.st_mode)
                    or not stat.S_ISDIR(source_stat.st_mode)
                    or not stat.S_ISDIR(source_lstat.st_mode)
                    or source_lstat.st_dev != source_stat.st_dev
                    or source_lstat.st_ino != source_stat.st_ino
                    or source_path.is_symlink()
                    or self._contains_nested_mount(source_path)
                ):
                    raise KnowledgeBaseMountSourceError(
                        "Canonical knowledge base source is unsafe"
                    )
                return VolumeSourceIdentity(
                    validation_path=str(source_path),
                    device=source_stat.st_dev,
                    inode=source_stat.st_ino,
                )
            finally:
                os.close(source_fd)
        finally:
            os.close(root_fd)

    @staticmethod
    def _contains_nested_mount(source_path: Path) -> bool:
        return contains_nested_mount(
            source_path,
            error_factory=KnowledgeBaseMountSourceError,
            read_error_message="Mount topology could not be verified",
            invalid_error_message="Mount topology is invalid",
        )

    def _runtime_home_host_root(self, safe_workspace_id: str) -> Path:
        return (
            self._resolve_host_mount_path(self.settings.HOST_RUNTIME_HOME_DIR)
            / safe_workspace_id
        )

    def _runtime_home_manager_root(self, safe_workspace_id: str) -> Path:
        return Path(self.settings.MANAGER_RUNTIME_HOME_DIR) / safe_workspace_id

    def _write_codex_default_config(self, manager_runtime_home: Path) -> None:
        config_path = manager_runtime_home / ".codex" / "config.toml"
        if config_path.exists():
            return

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            CODEX_DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        config_path.chmod(0o600)

    def _resolve_host_mount_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path

        host_project_root = Path(self.settings.HOST_PROJECT_ROOT).expanduser()
        if not host_project_root.is_absolute():
            raise ValueError(
                "HOST_PROJECT_ROOT must be an absolute path when host mount paths are relative"
            )

        return host_project_root / path

    # -- QueryInterface --------------------------------------------------------
    def get_runtime_logs(
        self,
        workspace_id: str,
        *,
        limit: int = 100,
        stage: Optional[str] = None,
    ) -> list[db_models.WorkspaceRuntimeLog]:
        stmt: Select[tuple[db_models.WorkspaceRuntimeLog]] = select(
            db_models.WorkspaceRuntimeLog
        ).where(db_models.WorkspaceRuntimeLog.workspace_id == workspace_id)
        if stage:
            stmt = stmt.where(db_models.WorkspaceRuntimeLog.stage == stage)
        stmt = stmt.order_by(db_models.WorkspaceRuntimeLog.created_at.desc()).limit(
            limit
        )
        return list(self.db.execute(stmt).scalars().all())

    def _update_workspace_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        workspace.runtime_container_id = runtime_info.identifier
        workspace.runtime_internal_url = runtime_info.internal_url
        workspace.terminal_internal_url = self._terminal_internal_url(
            runtime_info.internal_url
        )

        workspace.runtime_status = "running"
        workspace.runtime_last_seen = datetime.utcnow()

    def _build_browser_runtime_context(
        self,
        workspace: db_models.Workspace,
        runtime_instance_id: str,
    ) -> RuntimeContext:
        """Build browser runtime context"""
        from app.modules.container_images.catalog import get_container_image_service

        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace("-", "_")
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # Ensure workspace directory exists
        host_workspace.mkdir(parents=True, exist_ok=True)

        # Browser container mounts the same workspace directory
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(network_name=self.settings.DOCKER_NETWORK)

        browser_credentials = BrowserCredentialService.from_settings().derive(
            workspace_id=workspace.id,
            revision=workspace.browser_credential_revision,
            key_id=workspace.browser_credential_key_id,
            algorithm=workspace.browser_credential_algorithm,
        )
        credential_mounts = self._write_browser_credential_files(
            runtime_instance_id=runtime_instance_id,
            user_password=browser_credentials.user_password,
            admin_password=browser_credentials.admin_password,
        )
        volumes.extend(credential_mounts)

        return RuntimeContext(
            environment={
                "AILERON_WORKSPACE_ID": workspace.id,
                "AILERON_RUNTIME_INSTANCE_ID": runtime_instance_id,
                # neko Settings
                "NEKO_SERVER_BIND": ":6080",
                "NEKO_DESKTOP_SCREEN": "1440x900@30",
                "NEKO_MEMBER_PROVIDER": "multiuser",
                "NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE": (
                    "/run/secrets/browser-credentials/user-password"
                ),
                "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": (
                    "/run/secrets/browser-credentials/admin-password"
                ),
                "NEKO_LOG_LEVEL": "warn",
                "NEKO_SESSION_IMPLICIT_HOSTING": "true",
            },
            volumes=volumes,
            network=network,
            labels={
                "image": image_service.get_browser_image_name(),
                "command": None,
                "working_dir": "/workspace",
            },
            container_labels=self._generation_labels(
                workspace,
                runtime_instance_id,
                workload="browser",
            ),
        )

    def _write_browser_credential_files(
        self,
        *,
        runtime_instance_id: str,
        user_password: str,
        admin_password: str,
    ) -> list[VolumeMount]:
        """Persist one Docker Browser generation's credentials as mounted files."""

        try:
            parsed_instance_id = UUID(runtime_instance_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise RuntimeError("Browser runtime instance ID is invalid") from exc
        if str(parsed_instance_id) != runtime_instance_id:
            raise RuntimeError("Browser runtime instance ID is invalid")

        manager_root = Path(self.settings.MANAGER_BROWSER_CREDENTIALS_DIR)
        host_root = Path(self.settings.HOST_BROWSER_CREDENTIALS_DIR)
        if not manager_root.is_absolute() or not host_root.is_absolute():
            raise RuntimeError("Browser credential directories must be absolute")

        manager_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        current = Path(manager_root.anchor)
        for part in manager_root.parts[1:]:
            current /= part
            current_stat = current.lstat()
            if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(
                current_stat.st_mode
            ):
                raise RuntimeError("Browser credential root is not canonical")
        credential_directory = manager_root / runtime_instance_id
        if credential_directory.exists():
            directory_stat = credential_directory.lstat()
            if not stat.S_ISDIR(directory_stat.st_mode):
                raise RuntimeError("Browser credential directory is invalid")
        else:
            credential_directory.mkdir(mode=0o700)
        credential_directory.chmod(0o700)

        credentials = {
            "user-password": user_password,
            "admin-password": admin_password,
        }
        for filename, secret_value in credentials.items():
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{filename}.",
                dir=credential_directory,
            )
            temporary_path = Path(temporary_name)
            try:
                os.fchmod(file_descriptor, 0o600)
                with os.fdopen(file_descriptor, "w", encoding="utf-8") as stream:
                    file_descriptor = -1
                    stream.write(secret_value)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_path, credential_directory / filename)
                (credential_directory / filename).chmod(0o600)
            finally:
                if file_descriptor >= 0:
                    os.close(file_descriptor)
                temporary_path.unlink(missing_ok=True)

        container_root = Path("/run/secrets/browser-credentials")
        host_directory = host_root / runtime_instance_id
        return [
            VolumeMount(
                source=str(host_directory / filename),
                target=str(container_root / filename),
                read_only=True,
            )
            for filename in credentials
        ]

    def _build_browser_connectivity_probe_context(
        self,
        workspace: db_models.Workspace,
        browser_instance_id: str,
    ) -> RuntimeContext | None:
        """Build the low-privilege probe that shares the Browser namespace."""

        image = getattr(self.settings, "BROWSER_CONNECTIVITY_PROBE_IMAGE", "")
        profile_source = getattr(
            self.settings,
            "HOST_TURN_REACHABILITY_PROFILE_FILE",
            "",
        )
        secret_source = getattr(
            self.settings,
            "HOST_TURN_REST_SHARED_SECRET_FILE",
            "",
        )
        backend_ice_source = getattr(
            self.settings,
            "HOST_TURN_BACKEND_ICE_SERVERS_JSON_FILE",
            "",
        )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                image,
                profile_source,
                secret_source,
                backend_ice_source,
            )
        ):
            return None
        installation_id = self.settings.AILERON_INSTALLATION_ID.strip()
        if not installation_id:
            raise RuntimeError(
                "Browser connectivity installation identity is unavailable"
            )
        profile_source = str(self._resolve_host_mount_path(profile_source))
        secret_source = str(self._resolve_host_mount_path(secret_source))
        backend_ice_source = str(self._resolve_host_mount_path(backend_ice_source))
        profile_validation_source = getattr(
            self.settings,
            "TURN_REACHABILITY_PROFILE_FILE",
            "",
        )
        secret_validation_source = getattr(
            self.settings,
            "TURN_REST_SHARED_SECRET_FILE",
            "",
        )
        backend_ice_validation_source = getattr(
            self.settings,
            "TURN_BACKEND_ICE_SERVERS_JSON_FILE",
            "",
        )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                profile_validation_source,
                secret_validation_source,
                backend_ice_validation_source,
            )
        ):
            raise RuntimeError(
                "Browser connectivity probe manager-mounted TURN sources are unavailable"
            )
        profile_validation_path = str(
            self._resolve_host_mount_path(profile_validation_source)
        )
        secret_validation_path = str(
            self._resolve_host_mount_path(secret_validation_source)
        )
        backend_ice_validation_path = str(
            self._resolve_host_mount_path(backend_ice_validation_source)
        )
        try:
            profile_owner = os.stat(profile_validation_path)
            secret_owner = os.stat(secret_validation_path)
            backend_ice_owner = os.stat(backend_ice_validation_path)
        except OSError as exc:
            raise RuntimeError(
                "Browser connectivity probe secret sources are unavailable"
            ) from exc
        if (profile_owner.st_uid, profile_owner.st_gid) != (
            secret_owner.st_uid,
            secret_owner.st_gid,
        ):
            raise RuntimeError(
                "Browser connectivity probe secret sources must share an owner"
            )
        if (profile_owner.st_uid, profile_owner.st_gid) != (
            backend_ice_owner.st_uid,
            backend_ice_owner.st_gid,
        ):
            raise RuntimeError(
                "Browser connectivity probe secret sources must share an owner"
            )

        return RuntimeContext(
            environment={
                "TURN_REACHABILITY_PROFILE_FILE": "/run/secrets/turn/profile.json",
                "TURN_CREDENTIAL_REVISION": str(
                    getattr(self.settings, "TURN_CREDENTIAL_REVISION", "")
                ),
                "TURN_REST_SHARED_SECRET_FILE": "/run/secrets/turn/rest-secret",
                "TURN_BACKEND_ICE_SERVERS_JSON_FILE": (
                    "/run/secrets/turn/backend-ice-servers.json"
                ),
                "TURN_PROBE_IDENTITY": f"backend:{workspace.id}:{browser_instance_id}",
                "AILERON_INSTALLATION_ID": installation_id,
            },
            volumes=[
                VolumeMount(
                    source=profile_source,
                    target="/run/secrets/turn/profile.json",
                    read_only=True,
                ),
                VolumeMount(
                    source=secret_source,
                    target="/run/secrets/turn/rest-secret",
                    read_only=True,
                ),
                VolumeMount(
                    source=backend_ice_source,
                    target="/run/secrets/turn/backend-ice-servers.json",
                    read_only=True,
                ),
            ],
            labels={
                "image": image,
                "command": (
                    "--mode=browser-connectivity-probe "
                    "--connectivity-probe-bind-address=:8082"
                ),
                "working_dir": "/app",
                "user": f"{profile_owner.st_uid}:{profile_owner.st_gid}",
            },
            container_labels=self._generation_labels(
                workspace,
                browser_instance_id,
                workload="browser-connectivity-probe",
            ),
        )

    def _update_browser_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        """Update Browser Runtime Status"""
        workspace.browser_container_id = runtime_info.identifier
        workspace.browser_webrtc_internal_url = runtime_info.internal_url
        workspace.browser_status = "running"
        workspace.browser_last_seen = datetime.utcnow()
        browser_generation = (
            runtime_info.component_instance_id or workspace.browser_instance_id
        )
        workspace.browser_connectivity_browser_generation = browser_generation
        workspace.browser_connectivity_state = "pending"
        workspace.browser_connectivity_contract_version = "browser-connectivity/v1"
        workspace.browser_connectivity_admission = "denied"
        workspace.browser_connectivity_profile_revision = None
        workspace.browser_connectivity_credential_revision = None
        workspace.browser_connectivity_accepted_at = None
        workspace.browser_connectivity_expires_at = None
        workspace.browser_connectivity_reason = "BrowserConnectivityPending"
        workspace.browser_connectivity_error_code = None
        workspace.browser_connectivity_last_transition_at = None
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
        # The container was just started with the current credential revision,
        # so the desired credential is now the observed one.
        workspace.browser_credential_observed_revision = (
            workspace.browser_credential_revision
        )
        workspace.browser_credential_observed_key_id = (
            workspace.browser_credential_key_id
        )
        workspace.browser_credential_observed_algorithm = (
            workspace.browser_credential_algorithm
        )

    def _build_canvas_runtime_context(
        self,
        workspace: db_models.Workspace,
        runtime_instance_id: str,
    ) -> RuntimeContext:
        """Build canvas runtime context"""
        from app.modules.container_images.catalog import get_container_image_service

        image_service = get_container_image_service()

        safe_workspace_id = workspace.id.replace("-", "_")
        host_workspace = Path(self.settings.HOST_WORKSPACES_DIR) / safe_workspace_id

        # Ensure workspace directory exists
        host_workspace.mkdir(parents=True, exist_ok=True)

        # Mount the same workspace directory
        volumes = [
            VolumeMount(source=str(host_workspace), target="/workspace"),
        ]

        network = NetworkConfig(network_name=self.settings.DOCKER_NETWORK)

        return RuntimeContext(
            environment={
                "AILERON_WORKSPACE_ID": workspace.id,
                "AILERON_WORKSPACE_PATH": "/workspace",
                "AILERON_RUNTIME_INSTANCE_ID": runtime_instance_id,
            },
            volumes=volumes,
            network=network,
            labels={
                "image": image_service.get_canvas_image_name(),
                "command": None,
                "working_dir": "/workspace",
            },
            container_labels=self._generation_labels(
                workspace,
                runtime_instance_id,
                workload="canvas",
            ),
        )

    @staticmethod
    def _generation_labels(
        workspace: db_models.Workspace,
        component_instance_id: str,
        *,
        workload: str,
    ) -> dict[str, str]:
        """Return immutable labels for one component generation."""

        canonical_instance_id = str(UUID(component_instance_id))
        if canonical_instance_id != component_instance_id:
            raise ValueError("Component instance identifier must be canonical")
        return {
            "aileron.workspace_id": workspace.id,
            "aileron.component_instance_id": canonical_instance_id,
            "aileron.workload": workload,
        }

    def _update_canvas_runtime(
        self, workspace: db_models.Workspace, runtime_info: RuntimeInfo
    ) -> None:
        """Update Canvas Runtime Status"""
        workspace.canvas_container_id = runtime_info.identifier
        workspace.canvas_internal_url = runtime_info.internal_url
        workspace.canvas_status = "running"
        workspace.canvas_last_seen = datetime.utcnow()
        workspace.canvas_created_at = datetime.utcnow()


__all__ = ["RuntimeProvisionService"]
