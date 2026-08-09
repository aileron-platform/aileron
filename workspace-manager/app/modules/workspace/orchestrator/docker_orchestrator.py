import logging
import os
import stat
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import docker

from app.modules.knowledge_base.mount_topology import contains_nested_mount

from .base import (
    ContainerCreationError,
    ContainerOrchestrator,
    OrchestratorException,
    VolumeSourceValidationError,
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from .models import (
    ExecutionPlaneInfo,
    RuntimeContext,
    RuntimeInfo,
)

logger = logging.getLogger(__name__)

_BROWSER_CREDENTIAL_FILE_TARGETS = {
    "NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE": (
        "/run/secrets/browser-credentials/user-password"
    ),
    "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE": (
        "/run/secrets/browser-credentials/admin-password"
    ),
}
_BROWSER_PLAINTEXT_CREDENTIAL_NAMES = {
    "NEKO_MEMBER_MULTIUSER_USER_PASSWORD",
    "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD",
}


class DockerOrchestrator(ContainerOrchestrator):
    """Docker container orchestrator"""

    def __init__(self, settings):
        self.settings = settings
        try:
            # Docker client configuration is sourced entirely from the OS-level
            # DOCKER_HOST environment variable, not from application settings.
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise OrchestratorException(f"Failed to initialize Docker client: {e}")

    def _stop_and_remove_existing_runtime(self, container_name: str) -> None:
        try:
            container = self.client.containers.get(container_name)
        except docker.errors.NotFound:
            return

        container.reload()
        logger.info("Stopping existing runtime container %s", container_name)
        container.stop(timeout=120)
        container.reload()
        if container.status == "running":
            raise ContainerCreationError(
                f"Runtime container {container_name} is still running after stop"
            )

        logger.info("Removing stopped runtime container %s", container_name)
        container.remove()

    @staticmethod
    def _contains_nested_mount(source_path: str) -> bool:
        return contains_nested_mount(
            source_path,
            error_factory=VolumeSourceValidationError,
            read_error_message="Canonical mount topology could not be verified",
            invalid_error_message="Canonical mount topology is invalid",
        )

    @staticmethod
    def _validate_volume_source_identities(context: RuntimeContext) -> None:
        for volume in context.volumes:
            identity = volume.source_identity
            if identity is None:
                continue
            try:
                current = os.lstat(identity.validation_path)
            except OSError as exc:
                raise VolumeSourceValidationError(
                    "A canonical volume source is unavailable"
                ) from exc
            if (
                not stat.S_ISDIR(current.st_mode)
                or stat.S_ISLNK(current.st_mode)
                or current.st_dev != identity.device
                or current.st_ino != identity.inode
                or DockerOrchestrator._contains_nested_mount(identity.validation_path)
            ):
                raise VolumeSourceValidationError(
                    "A canonical volume source identity changed"
                )

    @staticmethod
    def _validate_browser_credential_mounts(context: RuntimeContext) -> None:
        if _BROWSER_PLAINTEXT_CREDENTIAL_NAMES.intersection(context.environment):
            raise ContainerCreationError(
                "Browser credentials must be provided through mounted files"
            )

        mounts_by_target = {volume.target: volume for volume in context.volumes}
        for (
            environment_name,
            expected_target,
        ) in _BROWSER_CREDENTIAL_FILE_TARGETS.items():
            if context.environment.get(environment_name) != expected_target:
                raise ContainerCreationError(
                    "Browser credential file paths are incomplete"
                )
            volume = mounts_by_target.get(expected_target)
            if (
                volume is None
                or not volume.read_only
                or not os.path.isabs(volume.source)
            ):
                raise ContainerCreationError(
                    "Browser credential files must use absolute read-only mounts"
                )

    def _remove_browser_credential_generation(self, generation_id: str) -> None:
        try:
            parsed_generation_id = UUID(generation_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Browser credential generation identity is invalid"
            ) from exc
        if str(parsed_generation_id) != generation_id:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Browser credential generation identity is invalid"
            )

        configured_root = self.settings.MANAGER_BROWSER_CREDENTIALS_DIR
        if (
            not isinstance(configured_root, str)
            or configured_root != configured_root.strip()
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Browser credential root is invalid"
            )
        credential_root = Path(configured_root)
        if not credential_root.is_absolute():
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Browser credential root is invalid"
            )

        current = Path(credential_root.anchor)
        for part in credential_root.parts[1:]:
            current /= part
            try:
                current_stat = current.lstat()
            except FileNotFoundError:
                return
            if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(
                current_stat.st_mode
            ):
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Browser credential root is not canonical"
                )

        generation_directory = credential_root / generation_id
        try:
            generation_stat = generation_directory.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(generation_stat.st_mode) or not stat.S_ISDIR(
            generation_stat.st_mode
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Browser credential generation directory is not canonical"
            )

        allowed_files = {"user-password", "admin-password"}
        entries = list(generation_directory.iterdir())
        for entry in entries:
            entry_stat = entry.lstat()
            if (
                entry.name not in allowed_files
                or stat.S_ISLNK(entry_stat.st_mode)
                or not stat.S_ISREG(entry_stat.st_mode)
            ):
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Browser credential generation contains an invalid entry"
                )
        for entry in entries:
            entry.unlink()
        generation_directory.rmdir()

    def create_workspace_runtime(
        self,
        workspace: Any,
        context: RuntimeContext,
        *,
        _replace_existing: bool = True,
    ) -> RuntimeInfo:
        container_name = f"workspace-runtime-{workspace.id}"
        container = None
        try:
            # Fail before terminating the current generation when a canonical
            # knowledge base source is already invalid.
            self._validate_volume_source_identities(context)

            # 1. Prepare volume configuration
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "ro" if volume.read_only else "rw",
                }

            # 2. Prepare environment variables
            environment = context.environment.copy()

            # 3. Network configuration
            network = context.network.network_name if context.network else None

            # 4. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={"max-size": "10m", "max-file": "3"},
            )

            # 5. Stop and remove the old container before replacement.
            if _replace_existing:
                self._stop_and_remove_existing_runtime(container_name)

            # Revalidate after the destructive boundary and immediately before
            # submitting the bind sources to the Docker daemon.
            self._validate_volume_source_identities(context)

            # 6. Start container
            logger.info(
                f"Starting container {container_name} with image {context.labels.get('image', 'unknown')}"
            )

            image = context.labels.get("image")
            if not image:
                raise ContainerCreationError("Image not specified in context labels")

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                volumes=volumes_config,
                environment=environment,
                network=network,
                log_config=log_config,
                cap_add=["NET_ADMIN"],
                security_opt=["seccomp=unconfined"],
                tmpfs={
                    "/home/developer/.codex/tmp": ("rw,exec,nosuid,size=16m,mode=1777")
                },
                command=context.labels.get("command"),  # Optional command override
                working_dir=context.labels.get("working_dir"),
                restart_policy={"Name": context.restart_policy},
                labels=context.container_labels,
            )

            # 7. Get runtime information
            container.reload()

            default_port = workspace.runtime_internal_port or 3002
            internal_url = f"http://{container_name}:{default_port}"

            return RuntimeInfo(
                identifier=container.id,
                internal_url=internal_url,
                extra_info={"container_name": container_name},
            )

        except VolumeSourceValidationError:
            raise
        except docker.errors.APIError as e:
            self._cleanup_failed_container(container, container_name, "runtime")
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            self._cleanup_failed_container(container, container_name, "runtime")
            logger.error(f"Unexpected error creating container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def create_chrome_runtime(
        self,
        workspace: Any,
        context: RuntimeContext,
        *,
        _replace_existing: bool = True,
    ) -> RuntimeInfo:
        """Create Browser Container"""
        container_name = f"workspace-browser-{workspace.id}"
        container = None
        try:
            self._validate_browser_credential_mounts(context)

            # 1. Prepare volume configuration
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "rw" if not volume.read_only else "ro",
                }

            # 3. Prepare environment variables
            environment = context.environment.copy()

            # 4. Network configuration
            network = context.network.network_name if context.network else None

            # 5. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={"max-size": "10m", "max-file": "3"},
            )

            # 6. Clean up old container
            if _replace_existing:
                try:
                    old_container = self.client.containers.get(container_name)
                    logger.info(f"Removing existing Browser container {container_name}")
                    old_labels = (
                        old_container.attrs.get("Config", {}).get("Labels", {}) or {}
                    )
                    old_generation_id = old_labels.get("aileron.component_instance_id")
                    old_container.remove(force=True)
                    if old_generation_id:
                        self._remove_browser_credential_generation(old_generation_id)
                except docker.errors.NotFound:
                    pass

            # 7. Get image
            image = context.labels.get("image")
            if not image:
                raise ContainerCreationError(
                    "Browser image not specified in context labels"
                )

            # 8. StartContainer
            logger.info(
                f"Starting Browser container {container_name} with image {image}"
            )

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                volumes=volumes_config,
                environment=environment,
                network=network,
                log_config=log_config,
                shm_size="2147483648",  # 2GB, Chrome needs sufficient /dev/shm space
                labels=context.container_labels,
            )

            # 9. Get runtime information
            container.reload()

            default_port = workspace.browser_webrtc_internal_port or 6080
            internal_url = f"http://{container_name}:{default_port}"

            return RuntimeInfo(
                identifier=container.id,
                internal_url=internal_url,
                extra_info={"container_name": container_name},
            )

        except docker.errors.APIError as e:
            self._cleanup_failed_container(container, container_name, "Browser")
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            self._cleanup_failed_container(container, container_name, "Browser")
            logger.error(f"Unexpected error creating Browser container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def create_browser_connectivity_probe(
        self,
        workspace: Any,
        context: RuntimeContext,
        *,
        browser_container_id: str,
    ) -> RuntimeInfo:
        """Create a low-privilege probe in the Browser network namespace."""

        container_name = f"workspace-browser-connectivity-probe-{workspace.id}"
        volumes_config = {
            volume.source: {
                "bind": volume.target,
                "mode": "ro" if volume.read_only else "rw",
            }
            for volume in context.volumes
        }
        image = context.labels.get("image")
        if not image:
            raise ContainerCreationError(
                "Browser connectivity probe image is not specified"
            )
        log_config = docker.types.LogConfig(
            type=docker.types.LogConfig.types.JSON,
            config={"max-size": "10m", "max-file": "3"},
        )
        container = None
        try:
            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                volumes=volumes_config,
                environment=context.environment.copy(),
                network_mode=f"container:{browser_container_id}",
                log_config=log_config,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                tmpfs={"/tmp": "rw,noexec,nosuid,size=8m"},
                command=context.labels.get("command"),
                working_dir=context.labels.get("working_dir"),
                user=context.labels.get("user"),
                restart_policy={"Name": context.restart_policy},
                labels=context.container_labels,
            )
            container.reload()
            return RuntimeInfo(
                identifier=container.id,
                internal_url=f"http://workspace-browser-{workspace.id}:8082",
                extra_info={"container_name": container_name},
            )
        except docker.errors.APIError as exc:
            self._cleanup_failed_browser_probe(container, container_name)
            logger.error(f"Docker API error creating Browser connectivity probe: {exc}")
            raise ContainerCreationError(
                f"Docker API error creating Browser connectivity probe: {exc}"
            ) from exc
        except Exception as exc:
            self._cleanup_failed_browser_probe(container, container_name)
            logger.error(f"Unexpected error creating Browser connectivity probe: {exc}")
            raise ContainerCreationError(
                f"Unexpected error creating Browser connectivity probe: {exc}"
            ) from exc

    def _cleanup_failed_browser_probe(
        self,
        container: Any,
        container_name: str,
    ) -> None:
        if container is None:
            return
        try:
            container.remove(force=True)
            self._require_container_absent(container.id or container_name)
        except docker.errors.NotFound:
            return
        except Exception as exc:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Failed Browser connectivity probe cleanup could not be confirmed"
            ) from exc

    def _cleanup_failed_container(
        self,
        container: Any,
        container_name: str,
        component_name: str,
    ) -> None:
        if container is None:
            return
        try:
            container.remove(force=True)
            self._require_container_absent(container.id or container_name)
        except docker.errors.NotFound:
            return
        except Exception as exc:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                f"Failed {component_name} container cleanup could not be confirmed"
            ) from exc

    def create_canvas_runtime(
        self,
        workspace: Any,
        context: RuntimeContext,
        *,
        _replace_existing: bool = True,
    ) -> RuntimeInfo:
        """Create Canvas Container"""
        container_name = f"workspace-canvas-{workspace.id}"
        container = None
        try:
            # 1. Prepare volume configuration
            volumes_config = {}
            for volume in context.volumes:
                volumes_config[volume.source] = {
                    "bind": volume.target,
                    "mode": "rw" if not volume.read_only else "ro",
                }

            # 3. Prepare environment variables
            environment = context.environment.copy()

            # 4. Network configuration
            network = context.network.network_name if context.network else None

            # 5. Log Config
            log_config = docker.types.LogConfig(
                type=docker.types.LogConfig.types.JSON,
                config={"max-size": "10m", "max-file": "3"},
            )

            # 6. Clean up old container
            if _replace_existing:
                try:
                    old_container = self.client.containers.get(container_name)
                    logger.info(f"Removing existing Canvas container {container_name}")
                    old_container.remove(force=True)
                except docker.errors.NotFound:
                    pass

            # 7. Get image
            image = context.labels.get("image")
            if not image:
                raise ContainerCreationError(
                    "Canvas image not specified in context labels"
                )

            # 8. StartContainer
            logger.info(
                f"Starting Canvas container {container_name} with image {image}"
            )

            container = self.client.containers.run(
                image=image,
                name=container_name,
                detach=True,
                volumes=volumes_config,
                environment=environment,
                network=network,
                log_config=log_config,
                labels=context.container_labels,
            )

            # 9. Get runtime information
            container.reload()

            default_port = workspace.canvas_internal_port or 3003
            internal_url = f"http://{container_name}:{default_port}"

            return RuntimeInfo(
                identifier=container.id,
                internal_url=internal_url,
                extra_info={"container_name": container_name},
            )

        except docker.errors.APIError as e:
            self._cleanup_failed_container(container, container_name, "Canvas")
            logger.error(f"Docker API error: {e}")
            raise ContainerCreationError(f"Docker API error: {e}")
        except Exception as e:
            self._cleanup_failed_container(container, container_name, "Canvas")
            logger.error(f"Unexpected error creating Canvas container: {e}")
            raise ContainerCreationError(f"Unexpected error: {e}")

    def recreate_workspace_execution_plane(
        self,
        *,
        workspace: Any,
        runtime_instance_id: str,
        runtime_context: RuntimeContext,
        browser_context: RuntimeContext,
        canvas_context: RuntimeContext,
        assert_claim: Callable[[], None],
        browser_probe_context: RuntimeContext | None = None,
    ) -> ExecutionPlaneInfo:
        """Fence all old workloads before creating one complete generation."""

        contexts = (runtime_context, browser_context, canvas_context)
        if browser_probe_context is not None:
            contexts = contexts + (browser_probe_context,)
        if any(
            context.container_labels.get("aileron.component_instance_id")
            != runtime_instance_id
            for context in contexts
        ):
            raise ContainerCreationError(
                "Execution-plane contexts do not share one generation identity"
            )
        self._validate_volume_source_identities(runtime_context)

        previous_instance_id = workspace.runtime_instance_id
        previous_instance_ids = (
            previous_instance_id,
            workspace.browser_instance_id or previous_instance_id,
            workspace.browser_instance_id or previous_instance_id,
            workspace.canvas_instance_id or previous_instance_id,
        )
        previous_container_ids = (
            workspace.runtime_container_id,
            workspace.browser_container_id,
            None,
            workspace.canvas_container_id,
        )
        has_previous_ids = tuple(
            container_id is not None for container_id in previous_container_ids
        )
        if previous_instance_id is None and any(has_previous_ids):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Prior execution-plane workload identity is incomplete"
            )
        if previous_instance_id is not None:
            # A component that failed before its container id was persisted
            # (e.g. it crash-looped on startup) falls back to its
            # deterministic name - Docker resolves get() by id or name
            # either way, so the same lookup, generation-identity check,
            # stop, and remove still apply and this can't touch an
            # unrelated container.
            deterministic_names = (
                f"workspace-runtime-{workspace.id}",
                f"workspace-browser-{workspace.id}",
                f"workspace-browser-connectivity-probe-{workspace.id}",
                f"workspace-canvas-{workspace.id}",
            )
            container_ids = tuple(
                container_id or deterministic_name
                for container_id, deterministic_name in zip(
                    previous_container_ids, deterministic_names
                )
            )
            for container_id, component_instance_id in zip(
                container_ids,
                previous_instance_ids,
            ):
                assert_claim()
                self._terminate_exact_container(
                    container_id,
                    expected_component_instance_id=component_instance_id,
                )
            for container_id in container_ids:
                assert_claim()
                self._require_container_absent(container_id)
            self._remove_browser_credential_generation(
                workspace.browser_instance_id or previous_instance_id
            )
        else:
            self.prove_workspace_execution_plane_absent(
                workspace,
                assert_claim=assert_claim,
            )

        deterministic_names = (
            f"workspace-runtime-{workspace.id}",
            f"workspace-browser-{workspace.id}",
            f"workspace-browser-connectivity-probe-{workspace.id}",
            f"workspace-canvas-{workspace.id}",
        )
        created_ids: list[str] = []
        try:
            assert_claim()
            self._validate_volume_source_identities(runtime_context)
            created_ids.append(deterministic_names[0])
            runtime = self.create_workspace_runtime(
                workspace,
                runtime_context,
                _replace_existing=False,
            )
            created_ids[-1] = runtime.identifier
            assert_claim()
            created_ids.append(deterministic_names[1])
            browser = self.create_chrome_runtime(
                workspace,
                browser_context,
                _replace_existing=False,
            )
            created_ids[-1] = browser.identifier
            assert_claim()
            browser_probe = None
            if browser_probe_context is not None:
                created_ids.append(deterministic_names[2])
                browser_probe = self.create_browser_connectivity_probe(
                    workspace,
                    browser_probe_context,
                    browser_container_id=browser.identifier,
                )
                created_ids[-1] = browser_probe.identifier
                assert_claim()
            created_ids.append(deterministic_names[3])
            canvas = self.create_canvas_runtime(
                workspace,
                canvas_context,
                _replace_existing=False,
            )
            created_ids[-1] = canvas.identifier
            assert_claim()
            return ExecutionPlaneInfo(
                runtime_instance_id=runtime_instance_id,
                runtime=runtime,
                browser=browser,
                canvas=canvas,
                browser_probe=browser_probe,
            )
        except Exception:
            cleanup_confirmed = True
            for container_id in reversed(created_ids):
                try:
                    self._terminate_exact_container(
                        container_id,
                        expected_component_instance_id=runtime_instance_id,
                    )
                    self._require_container_absent(container_id)
                except Exception:
                    cleanup_confirmed = False
            if not cleanup_confirmed:
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Partial replacement generation could not be fenced"
                )
            self._remove_browser_credential_generation(runtime_instance_id)
            raise

    def _terminate_exact_container(
        self,
        container_id: str | None,
        *,
        expected_component_instance_id: str,
    ) -> None:
        if not container_id:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Workload identity is missing"
            )
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return
        labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
        if (
            labels.get("aileron.component_instance_id")
            != expected_component_instance_id
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Workload generation identity does not match"
            )
        container.reload()
        if container.status not in {"created", "exited", "dead"}:
            container.stop(timeout=120)
            container.reload()
        if container.status not in {"created", "exited", "dead"}:
            raise WorkspaceRuntimeTerminationUnconfirmedError("Workload did not stop")
        container.remove()

    def _require_container_absent(self, container_id: str | None) -> None:
        if not container_id:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Workload identity is missing"
            )
        try:
            self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return
        raise WorkspaceRuntimeTerminationUnconfirmedError(
            "Workload termination could not be confirmed"
        )

    def replace_workspace_component(
        self,
        *,
        workspace: Any,
        component: str,
        context: RuntimeContext,
        assert_claim: Callable[[], None],
        browser_probe_context: RuntimeContext | None = None,
    ) -> RuntimeInfo:
        """Fence one persisted component generation before replacement."""

        if component not in {"runtime", "browser", "canvas"}:
            raise ContainerCreationError("Workspace component is invalid")
        expected_instance_id = getattr(workspace, f"{component}_instance_id")
        if not isinstance(expected_instance_id, str) or not expected_instance_id:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Prior workload generation identity is missing"
            )
        container_id = getattr(workspace, f"{component}_container_id") or (
            f"workspace-{component}-{workspace.id}"
        )
        if component == "runtime":
            self._validate_volume_source_identities(context)
        if component == "browser":
            probe_name = f"workspace-browser-connectivity-probe-{workspace.id}"
            assert_claim()
            self._terminate_exact_container(
                probe_name,
                expected_component_instance_id=expected_instance_id,
            )
            assert_claim()
            self._require_container_absent(probe_name)
        assert_claim()
        self._terminate_exact_container(
            container_id,
            expected_component_instance_id=expected_instance_id,
        )
        assert_claim()
        self._require_container_absent(container_id)
        if component == "browser":
            self._remove_browser_credential_generation(expected_instance_id)
        assert_claim()
        if component == "runtime":
            return self.create_workspace_runtime(
                workspace,
                context,
                _replace_existing=False,
            )
        if component == "browser":
            browser = self.create_chrome_runtime(
                workspace,
                context,
                _replace_existing=False,
            )
            if browser_probe_context is None:
                return browser
            new_instance_id = context.container_labels.get(
                "aileron.component_instance_id"
            )
            if not new_instance_id:
                raise ContainerCreationError(
                    "Browser connectivity probe generation identity is missing"
                )
            try:
                probe = self.create_browser_connectivity_probe(
                    workspace,
                    browser_probe_context,
                    browser_container_id=browser.identifier,
                )
                browser.extra_info["connectivity_probe_container_id"] = probe.identifier
                return browser
            except Exception:
                self._terminate_exact_container(
                    browser.identifier,
                    expected_component_instance_id=new_instance_id,
                )
                self._require_container_absent(browser.identifier)
                raise
        return self.create_canvas_runtime(
            workspace,
            context,
            _replace_existing=False,
        )

    def terminate_execution_plane(
        self,
        execution_plane: ExecutionPlaneInfo,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        """Terminate the exact three container IDs of one generation."""

        container_ids = (
            execution_plane.runtime.identifier,
            execution_plane.browser.identifier,
            *(
                (execution_plane.browser_probe.identifier,)
                if execution_plane.browser_probe is not None
                else ()
            ),
            execution_plane.canvas.identifier,
        )
        for container_id in container_ids:
            assert_claim()
            self._terminate_exact_container(
                container_id,
                expected_component_instance_id=execution_plane.runtime_instance_id,
            )
        for container_id in container_ids:
            assert_claim()
            self._require_container_absent(container_id)
        self._remove_browser_credential_generation(execution_plane.runtime_instance_id)

    def terminate_workspace_execution_plane(
        self,
        workspace: Any,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        """Terminate each component's persisted container ID, falling back to
        its deterministic name when a component failed before its container
        ID could be persisted (Docker resolves get() by ID or name either
        way, so the same lookup, identity check, stop, and remove apply)."""

        if not workspace.runtime_instance_id:
            self.prove_workspace_execution_plane_absent(
                workspace,
                assert_claim=assert_claim,
            )
            browser_instance_id = getattr(workspace, "browser_instance_id", None)
            if browser_instance_id:
                self._remove_browser_credential_generation(browser_instance_id)
            return
        container_ids = (
            workspace.runtime_container_id or f"workspace-runtime-{workspace.id}",
            workspace.browser_container_id or f"workspace-browser-{workspace.id}",
            f"workspace-browser-connectivity-probe-{workspace.id}",
            workspace.canvas_container_id or f"workspace-canvas-{workspace.id}",
        )
        component_instance_ids = (
            workspace.runtime_instance_id,
            workspace.browser_instance_id or workspace.runtime_instance_id,
            workspace.browser_instance_id or workspace.runtime_instance_id,
            workspace.canvas_instance_id or workspace.runtime_instance_id,
        )
        for container_id, component_instance_id in zip(
            container_ids,
            component_instance_ids,
        ):
            assert_claim()
            self._terminate_exact_container(
                container_id,
                expected_component_instance_id=component_instance_id,
            )
        for container_id in container_ids:
            assert_claim()
            self._require_container_absent(container_id)
        self._remove_browser_credential_generation(
            workspace.browser_instance_id or workspace.runtime_instance_id
        )

    def prove_workspace_execution_plane_absent(
        self,
        workspace: Any,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        """Prove all known IDs and deterministic Docker names are absent."""

        for container_id in (
            workspace.runtime_container_id,
            workspace.browser_container_id,
            workspace.canvas_container_id,
        ):
            if container_id:
                assert_claim()
                self._require_container_absent(container_id)
        for container_name in (
            f"workspace-runtime-{workspace.id}",
            f"workspace-browser-{workspace.id}",
            f"workspace-browser-connectivity-probe-{workspace.id}",
            f"workspace-canvas-{workspace.id}",
        ):
            assert_claim()
            try:
                self.client.containers.get(container_name)
            except docker.errors.NotFound:
                continue
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "A deterministic Workspace workload still exists"
            )

    def is_workspace_execution_plane_current(self, workspace: Any) -> bool:
        """Observe all current-generation Docker workloads without mutation."""

        if (
            not isinstance(workspace.runtime_instance_id, str)
            or not workspace.runtime_instance_id
        ):
            return False
        components = (
            (
                "runtime",
                workspace.runtime_container_id or f"workspace-runtime-{workspace.id}",
                workspace.runtime_instance_id,
            ),
            (
                "browser",
                workspace.browser_container_id or f"workspace-browser-{workspace.id}",
                workspace.browser_instance_id or workspace.runtime_instance_id,
            ),
            (
                "canvas",
                workspace.canvas_container_id or f"workspace-canvas-{workspace.id}",
                workspace.canvas_instance_id or workspace.runtime_instance_id,
            ),
        )
        for workload, container_id, expected_instance_id in components:
            try:
                container = self.client.containers.get(container_id)
                container.reload()
            except docker.errors.NotFound:
                return False
            labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
            if (
                container.status != "running"
                or labels.get("aileron.workspace_id") != workspace.id
                or labels.get("aileron.workload") != workload
                or labels.get("aileron.component_instance_id") != expected_instance_id
            ):
                return False
        return True
