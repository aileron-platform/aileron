"""Workspace lifecycle management service"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

import docker
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models

logger = logging.getLogger(__name__)


class WorkspaceLifecycleService:
    """Responsible for workspace deletion and restart operations"""

    def __init__(self, db: Session) -> None:
        self.db = db
        # Dynamically get settings to ensure correct configuration in test environment
        self.settings = get_settings()

    def delete_workspace_task(self, workspace_id: str) -> None:
        """Background task: Delete workspace
        
        Steps:
        1. Read workspace Data
        2. Stop and delete container
        3. Delete mounted data directory
        4. DeleteDatabaseRecord
        5. Record log
        
        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"BeginDelete workspace: {workspace_id}")
        
        try:
            # 1. Read workspace Data
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} does not exist")
                return

            if workspace.provisioner == "kubernetes":
                self._delete_kubernetes_workspace(workspace)
                return
            
            # Record deletion log
            self._log_event(workspace_id, "deleting", "BeginDelete workspace")
            
            # 2. Stop and delete containers
            if workspace.runtime_container_id:
                self._stop_and_remove_container(workspace.runtime_container_id, workspace_id)
            else:
                logger.warning(f"Workspace {workspace_id} no associated runtime container")

            # Delete Canvas Container
            if workspace.canvas_container_id:
                self._stop_and_remove_container(workspace.canvas_container_id, workspace_id)

            # 3. Delete mounted data directories
            self._cleanup_workspace_volumes(workspace_id)
            
            # 4. Delete database record (cascade delete will automatically delete related data)
            self.db.delete(workspace)
            self.db.commit()
            
            logger.info(f"SuccessDelete workspace: {workspace_id}")
            
        except Exception as e:
            logger.exception(f"Delete workspace {workspace_id} Failed: {e}")
            self.db.rollback()
            
            # Try to update status to error (if workspace still exists)
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.runtime_status = "error"
                    self._log_event(workspace_id, "error", f"DeleteFailed: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"UpdateErrorStatusFailed: {update_error}")

    def restart_workspace_task(self, workspace_id: str) -> None:
        """Background task: Rebuild workspace container (using latest image)

        Steps:
        1. Read workspace Data
        2. rebuild container (stop old container → create new container with same configuration)
        3. update status and container ID

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"Begin rebuilding workspace container: {workspace_id}")

        try:
            # 1. Read workspace Data
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} does not exist")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_workspace(workspace)
                return

            # Record restart log
            self._log_event(workspace_id, "restarting", "Begin rebuilding workspace container")
            if workspace.runtime_container_id:
                from app.services.runtime_provision_service import RuntimeProvisionService

                RuntimeProvisionService(self.db).execute_runtime_provision(workspace_id)
                logger.info(f"Successfully rebuilt workspace container: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} no associated container")
                self._log_event(workspace_id, "error", "no associated container")

        except Exception as e:
            logger.exception(f"Rebuild workspace container {workspace_id} failed: {e}")
            self.db.rollback()

            # Update status to error
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.runtime_status = "error"
                    self._log_event(workspace_id, "error", f"rebuild failed: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"UpdateErrorStatusFailed: {update_error}")

    def restart_browser_task(self, workspace_id: str) -> None:
        """Background task: Rebuild browser container (using latest image)

        Steps:
        1. Read workspace Data
        2. Get browser_container_id
        3. Rebuild container
        4. Update browser_status and container ID

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"Begin rebuilding browser container: {workspace_id}")

        try:
            # 1. Read workspace Data
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} does not exist")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_browser(workspace)
                return

            # Record restart log
            self._log_event(workspace_id, "browser_restarting", "Begin rebuilding browser container")

            # 2. Rebuild container
            if workspace.browser_container_id:
                new_id = self._recreate_container(
                    workspace.browser_container_id, workspace_id
                )

                # Update container ID and browser status
                if new_id:
                    workspace.browser_container_id = new_id
                workspace.browser_status = "running"
                self._log_event(workspace_id, "browser_running", "Browser container rebuild succeeded")
                self.db.commit()

                logger.info(f"Successfully rebuilt browser container: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} No associated browser container")
                self._log_event(workspace_id, "browser_error", "No associated browser container")

        except Exception as e:
            logger.exception(f"Rebuild browser container {workspace_id} failed: {e}")
            self.db.rollback()

            # Update browser status to error
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.browser_status = "error"
                    self._log_event(workspace_id, "browser_error", f"rebuild failed: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"Update Browser ErrorStatusFailed: {update_error}")

    def restart_canvas_task(self, workspace_id: str) -> None:
        """Background task: Rebuild canvas container (using latest image)

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"Begin rebuilding canvas container: {workspace_id}")

        try:
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} does not exist")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_canvas(workspace)
                return

            self._log_event(workspace_id, "canvas_restarting", "Begin rebuilding canvas container")

            if workspace.canvas_container_id:
                new_id = self._recreate_container(
                    workspace.canvas_container_id, workspace_id
                )

                if new_id:
                    workspace.canvas_container_id = new_id
                workspace.canvas_status = "running"
                self._log_event(workspace_id, "canvas_running", "Canvas container rebuild succeeded")
                self.db.commit()

                logger.info(f"Successfully rebuilt canvas container: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} No associated canvas container")
                self._log_event(workspace_id, "canvas_error", "No associated canvas container")

        except Exception as e:
            logger.exception(f"Rebuild canvas container {workspace_id} failed: {e}")
            self.db.rollback()

            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.canvas_status = "error"
                    self._log_event(workspace_id, "canvas_error", f"rebuild failed: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"Update Canvas ErrorStatusFailed: {update_error}")

    def _build_fresh_environment(self, workspace: db_models.Workspace) -> list[str]:
        """Build latest environment variables from database for container rebuild.

        Use RuntimeProvisionService logic to build complete environment variables,
        ensuring the rebuild uses the latest settings from the database.

        Returns:
            Docker format environment variable list ["KEY=VALUE", ...]
        """
        from app.services.runtime_provision_service import RuntimeProvisionService
        provision_service = RuntimeProvisionService(self.db)
        env_dict = provision_service._build_environment(workspace)
        return [f"{k}={v}" for k, v in env_dict.items()]

    def _delete_kubernetes_workspace(self, workspace: db_models.Workspace) -> None:
        """Delete Kubernetes workspace.

        Delete the manifest and corresponding data through the workspace custom
        resource service.
        """
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        deleted = service.delete_workspace_custom_resource(workspace.id)
        if not deleted:
            raise ValueError(f"Workspace {workspace.id} DeleteFailed")

    def _restart_kubernetes_workspace(self, workspace: db_models.Workspace) -> None:
        """Restart Kubernetes runtime workload."""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_workspace_restart(workspace.id)

    def _restart_kubernetes_browser(self, workspace: db_models.Workspace) -> None:
        """Restart Kubernetes browser workload."""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_browser_restart(workspace.id)

    def _restart_kubernetes_canvas(self, workspace: db_models.Workspace) -> None:
        """Restart Kubernetes canvas workload."""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_canvas_restart(workspace.id)

    def _recreate_container(self, container_id: str, workspace_id: str, *, env_override: list[str] | None = None) -> Optional[str]:
        """Recreate docker container (use latest image)

        Stop and remove old container, then create a new container with the same
        configuration while ensuring the latest image layers are used.

        Args:
            container_id: Container ID
            workspace_id: Workspace ID (for logging)
            env_override: Environment variable override list (Docker format ["KEY=VALUE", ...])

        Returns:
            New container ID, or None if failed
        """
        try:
            client = docker.from_env()

            try:
                container = client.containers.get(container_id)
            except docker.errors.NotFound:
                logger.error(f"Container {container_id} does not exist")
                self._log_event(workspace_id, "container_not_found", f"Container {container_id} does not exist")
                raise ValueError(f"Container {container_id} does not exist")

            name = container.name
            attrs = container.attrs
            config = attrs["Config"]
            host_config = attrs["HostConfig"]
            image = config["Image"]

            logger.info(f"Recreating container {name} ({container_id[:12]}) with image {image}")
            self._log_event(workspace_id, "container_recreating",
                            f"Rebuilding container {name}, use latest image: {image}")

            # GetNetworkConfiguration
            networks = attrs.get("NetworkSettings", {}).get("Networks", {})
            network_name = next(iter(networks), None)

            # Stop and remove old container
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Old container {container_id[:12]} removed")

            # Create host_config (preserve original configuration)
            log_cfg = host_config.get("LogConfig", {})
            restart_pol = host_config.get("RestartPolicy", {})

            hc_kwargs = {
                "port_bindings": host_config.get("PortBindings"),
                "binds": host_config.get("Binds"),
                "cap_add": host_config.get("CapAdd"),
                "log_config": docker.types.LogConfig(
                    type=log_cfg.get("Type", "json-file"),
                    config=log_cfg.get("Config", {}),
                ),
            }
            if restart_pol.get("Name"):
                hc_kwargs["restart_policy"] = restart_pol
            shm_size = host_config.get("ShmSize")
            if shm_size:
                hc_kwargs["shm_size"] = shm_size

            new_host_config = client.api.create_host_config(**hc_kwargs)

            # CreateNetworkConfiguration
            networking_config = None
            if network_name:
                networking_config = client.api.create_networking_config({
                    network_name: client.api.create_endpoint_config()
                })

            # Parse exposed ports to docker-py format
            exposed = config.get("ExposedPorts") or {}
            ports_list = []
            for port_key in exposed:
                parts = port_key.split("/")
                ports_list.append((int(parts[0]), parts[1] if len(parts) > 1 else "tcp"))

            # Create new container (preserve original configuration)
            volumes_list = list((config.get("Volumes") or {}).keys()) or None

            container_dict = client.api.create_container(
                image=image,
                name=name,
                command=config.get("Cmd"),
                environment=env_override if env_override is not None else config.get("Env"),
                working_dir=config.get("WorkingDir") or None,
                labels=config.get("Labels") or None,
                volumes=volumes_list,
                ports=ports_list or None,
                host_config=new_host_config,
                networking_config=networking_config,
            )

            # Start new container
            new_id = container_dict["Id"]
            client.api.start(new_id)

            logger.info(f"New container {new_id[:12]} created and started for workspace {workspace_id}")
            self._log_event(workspace_id, "container_recreated",
                            f"New container created: {new_id[:12]}")

            return new_id

        except docker.errors.APIError as e:
            logger.error(f"Docker API Error: {e}")
            self._log_event(workspace_id, "container_error", f"Docker API Error: {str(e)}")
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Recreate container Failed: {e}")
            self._log_event(workspace_id, "container_error", f"Recreate container Failed: {str(e)}")
            raise

    def _stop_and_remove_container(self, container_id: str, workspace_id: str) -> None:
        """Stop and delete Docker container

        Args:
            container_id: Container ID
            workspace_id: Workspace ID (for logging)
        """
        try:
            client = docker.from_env()

            try:
                container = client.containers.get(container_id)
                logger.debug(f"Stop container {container_id}")

                # Stop container (give 10 seconds graceful shutdown time)
                container.stop(timeout=10)
                logger.debug(f"Container {container_id} stopped")

                # Delete container
                container.remove(force=True)
                logger.info(f"Container {container_id} deleted")

                self._log_event(workspace_id, "container_removed", f"Deleted container: {container_id}")

            except docker.errors.NotFound:
                logger.warning(f"Container {container_id} does not exist, it may have been deleted")
                self._log_event(workspace_id, "container_not_found", f"Container {container_id} does not exist")

            except docker.errors.APIError as e:
                logger.error(f"Docker API Error: {e}")
                self._log_event(workspace_id, "container_error", f"Docker API Error: {str(e)}")
                # Do not raise exception, continue executing subsequent steps

        except Exception as e:
            logger.error(f"Stop/Delete container Failed: {e}")
            self._log_event(workspace_id, "container_error", f"Stop/Delete container Failed: {str(e)}")
            # Do not raise exception, continue executing subsequent steps

    def _cleanup_workspace_volumes(self, workspace_id: str) -> None:
        """Clean up workspace mounted data directories
        
        Args:
            workspace_id: Workspace ID
        """
        # Replace hyphens in UUID with underscores
        safe_workspace_id = workspace_id.replace('-', '_')

        # Define directories to delete
        directories_to_remove = [
            Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_CLAUDE_DATA_DIR) / safe_workspace_id,
        ]
        
        for directory in directories_to_remove:
            try:
                if directory.exists():
                    logger.debug(f"DeleteDirectory: {directory}")
                    shutil.rmtree(directory)
                    logger.debug(f"SuccessDeleteDirectory: {directory}")
                    self._log_event(workspace_id, "volume_removed", f"Deleted directory: {directory}")
                else:
                    logger.debug(f"Directorydoes not exist: {directory}")
                    
            except Exception as e:
                logger.error(f"DeleteDirectory {directory} Failed: {e}")
                self._log_event(workspace_id, "volume_error", f"DeleteDirectoryFailed: {directory} - {str(e)}")
                # Do not raise exception, continue deleting other directories

    def _log_event(self, workspace_id: str, stage: str, message: str, metadata: Optional[dict] = None) -> None:
        """Record workspace operation log

        Args:
            workspace_id: Workspace ID
            stage: OperationPhase
            message: Log message
            metadata: Additional metadata
        """
        try:
            log_entry = db_models.WorkspaceRuntimeLog(
                id=str(uuid4()),
                workspace_id=workspace_id,
                stage=stage,
                message=message,
                log_metadata=metadata or {},
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            logger.error(f"Record logFailed: {e}")
            self.db.rollback()
            # Don't raise exception to avoid affecting main process


def run_delete_workspace_task(workspace_id: str) -> None:
    """Background task entry: Delete workspace
    
    Args:
        workspace_id: Workspace ID
    """
    from app.db.database import SessionLocal
    
    db = SessionLocal()
    try:
        service = WorkspaceLifecycleService(db)
        service.delete_workspace_task(workspace_id)
    finally:
        db.close()


def run_restart_workspace_task(workspace_id: str) -> None:
    """Background task entry: Restart workspace container

    Args:
        workspace_id: Workspace ID
    """
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        service = WorkspaceLifecycleService(db)
        service.restart_workspace_task(workspace_id)
    finally:
        db.close()


def run_restart_browser_task(workspace_id: str) -> None:
    """Background task entry: Restart browser container

    Args:
        workspace_id: Workspace ID
    """
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        service = WorkspaceLifecycleService(db)
        service.restart_browser_task(workspace_id)
    finally:
        db.close()


def run_restart_canvas_task(workspace_id: str) -> None:
    """Background task entry: Restart canvas container

    Args:
        workspace_id: Workspace ID
    """
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        service = WorkspaceLifecycleService(db)
        service.restart_canvas_task(workspace_id)
    finally:
        db.close()


__all__ = [
    "WorkspaceLifecycleService",
    "run_delete_workspace_task",
    "run_restart_workspace_task",
    "run_restart_browser_task",
    "run_restart_canvas_task",
]
