"""Workspace 生命週期管理服務"""

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
    """負責 Workspace 的刪除和重啟操作"""

    def __init__(self, db: Session) -> None:
        self.db = db
        # 動態獲取 settings，確保在測試環境中使用正確的配置
        self.settings = get_settings()

    def delete_workspace_task(self, workspace_id: str) -> None:
        """背景任務：刪除 workspace
        
        步驟：
        1. 讀取 workspace 資料
        2. 停止並刪除 container
        3. 刪除掛載的資料目錄
        4. 刪除資料庫記錄
        5. 記錄日誌
        
        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"開始刪除 workspace: {workspace_id}")
        
        try:
            # 1. 讀取 workspace 資料
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} 不存在")
                return

            if workspace.provisioner == "kubernetes":
                self._delete_kubernetes_workspace(workspace)
                return
            
            # 記錄刪除日誌
            self._log_event(workspace_id, "deleting", "開始刪除 workspace")
            
            # 2. 停止並刪除 containers
            if workspace.runtime_container_id:
                self._stop_and_remove_container(workspace.runtime_container_id, workspace_id)
            else:
                logger.warning(f"Workspace {workspace_id} 沒有關聯的 runtime container")

            # 刪除 Canvas 容器
            if workspace.canvas_container_id:
                self._stop_and_remove_container(workspace.canvas_container_id, workspace_id)

            # 3. 刪除掛載的資料目錄
            self._cleanup_workspace_volumes(workspace_id)
            
            # 4. 刪除資料庫記錄（cascade delete 會自動刪除關聯資料）
            self.db.delete(workspace)
            self.db.commit()
            
            logger.info(f"成功刪除 workspace: {workspace_id}")
            
        except Exception as e:
            logger.exception(f"刪除 workspace {workspace_id} 失敗: {e}")
            self.db.rollback()
            
            # 嘗試更新狀態為 error（如果 workspace 還存在）
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.runtime_status = "error"
                    self._log_event(workspace_id, "error", f"刪除失敗: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"更新錯誤狀態失敗: {update_error}")

    def restart_workspace_task(self, workspace_id: str) -> None:
        """背景任務：重建 workspace container（使用最新 image）

        步驟：
        1. 讀取 workspace 資料
        2. 重建 container（停止舊容器 → 以相同配置建立新容器）
        3. 更新狀態和 container ID

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"開始重建 workspace container: {workspace_id}")

        try:
            # 1. 讀取 workspace 資料
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} 不存在")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_workspace(workspace)
                return

            # 記錄重啟日誌
            self._log_event(workspace_id, "restarting", "開始重建 workspace container")
            if workspace.runtime_container_id:
                from app.services.runtime_provision_service import RuntimeProvisionService

                RuntimeProvisionService(self.db).execute_runtime_provision(workspace_id)
                logger.info(f"成功重建 workspace container: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} 沒有關聯的 container")
                self._log_event(workspace_id, "error", "沒有關聯的 container")

        except Exception as e:
            logger.exception(f"重建 workspace container {workspace_id} 失敗: {e}")
            self.db.rollback()

            # 更新狀態為 error
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.runtime_status = "error"
                    self._log_event(workspace_id, "error", f"重建失敗: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"更新錯誤狀態失敗: {update_error}")

    def restart_browser_task(self, workspace_id: str) -> None:
        """背景任務：重建 Browser 容器（使用最新 image）

        步驟：
        1. 讀取 workspace 資料
        2. 取得 browser_container_id
        3. 重建 container
        4. 更新 browser_status 和 container ID

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"開始重建 Browser 容器: {workspace_id}")

        try:
            # 1. 讀取 workspace 資料
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} 不存在")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_browser(workspace)
                return

            # 記錄重啟日誌
            self._log_event(workspace_id, "browser_restarting", "開始重建 Browser 容器")

            # 2. 重建 container
            if workspace.browser_container_id:
                new_id = self._recreate_container(
                    workspace.browser_container_id, workspace_id
                )

                # 更新 container ID 和 Browser 狀態
                if new_id:
                    workspace.browser_container_id = new_id
                workspace.browser_status = "running"
                self._log_event(workspace_id, "browser_running", "Browser 容器重建成功")
                self.db.commit()

                logger.info(f"成功重建 Browser 容器: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} 沒有關聯的 Browser 容器")
                self._log_event(workspace_id, "browser_error", "沒有關聯的 Browser 容器")

        except Exception as e:
            logger.exception(f"重建 Browser 容器 {workspace_id} 失敗: {e}")
            self.db.rollback()

            # 更新 Browser 狀態為 error
            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.browser_status = "error"
                    self._log_event(workspace_id, "browser_error", f"重建失敗: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"更新 Browser 錯誤狀態失敗: {update_error}")

    def restart_canvas_task(self, workspace_id: str) -> None:
        """背景任務：重建 Canvas 容器（使用最新 image）

        Args:
            workspace_id: Workspace ID
        """
        logger.info(f"開始重建 Canvas 容器: {workspace_id}")

        try:
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.error(f"Workspace {workspace_id} 不存在")
                return

            if workspace.provisioner == "kubernetes":
                self._restart_kubernetes_canvas(workspace)
                return

            self._log_event(workspace_id, "canvas_restarting", "開始重建 Canvas 容器")

            if workspace.canvas_container_id:
                new_id = self._recreate_container(
                    workspace.canvas_container_id, workspace_id
                )

                if new_id:
                    workspace.canvas_container_id = new_id
                workspace.canvas_status = "running"
                self._log_event(workspace_id, "canvas_running", "Canvas 容器重建成功")
                self.db.commit()

                logger.info(f"成功重建 Canvas 容器: {workspace_id}")
            else:
                logger.warning(f"Workspace {workspace_id} 沒有關聯的 Canvas 容器")
                self._log_event(workspace_id, "canvas_error", "沒有關聯的 Canvas 容器")

        except Exception as e:
            logger.exception(f"重建 Canvas 容器 {workspace_id} 失敗: {e}")
            self.db.rollback()

            try:
                workspace = self.db.get(db_models.Workspace, workspace_id)
                if workspace:
                    workspace.canvas_status = "error"
                    self._log_event(workspace_id, "canvas_error", f"重建失敗: {str(e)}")
                    self.db.commit()
            except Exception as update_error:
                logger.error(f"更新 Canvas 錯誤狀態失敗: {update_error}")

    def _build_fresh_environment(self, workspace: db_models.Workspace) -> list[str]:
        """從資料庫構建最新的環境變數（用於 container rebuild）

        使用 RuntimeProvisionService 的邏輯來構建完整的環境變數，
        確保 rebuild 時使用的是資料庫中最新的設定。

        Returns:
            Docker 格式的環境變數列表 ["KEY=VALUE", ...]
        """
        from app.services.runtime_provision_service import RuntimeProvisionService
        provision_service = RuntimeProvisionService(self.db)
        env_dict = provision_service._build_environment(workspace)
        return [f"{k}={v}" for k, v in env_dict.items()]

    def _delete_kubernetes_workspace(self, workspace: db_models.Workspace) -> None:
        """刪除 Kubernetes workspace。

        透過 Workspace 自訂資源服務刪除 manifest 與對應資料。
        """
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        deleted = service.delete_workspace_custom_resource(workspace.id)
        if not deleted:
            raise ValueError(f"Workspace {workspace.id} 刪除失敗")

    def _restart_kubernetes_workspace(self, workspace: db_models.Workspace) -> None:
        """重啟 Kubernetes runtime workload。"""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_workspace_restart(workspace.id)

    def _restart_kubernetes_browser(self, workspace: db_models.Workspace) -> None:
        """重啟 Kubernetes browser workload。"""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_browser_restart(workspace.id)

    def _restart_kubernetes_canvas(self, workspace: db_models.Workspace) -> None:
        """重啟 Kubernetes canvas workload。"""
        from app.services.workspace_custom_resource_service import WorkspaceCustomResourceService

        service = WorkspaceCustomResourceService(self.db)
        service.request_canvas_restart(workspace.id)

    def _recreate_container(self, container_id: str, workspace_id: str, *, env_override: list[str] | None = None) -> Optional[str]:
        """重新建立 Docker container（使用最新 image）

        停止並移除舊容器，以相同配置建立新容器，確保使用最新的 image 層。

        Args:
            container_id: Container ID
            workspace_id: Workspace ID (用於日誌)
            env_override: 環境變數覆蓋列表（Docker 格式 ["KEY=VALUE", ...]）

        Returns:
            新容器的 ID，若失敗則為 None
        """
        try:
            client = docker.from_env()

            try:
                container = client.containers.get(container_id)
            except docker.errors.NotFound:
                logger.error(f"Container {container_id} 不存在")
                self._log_event(workspace_id, "container_not_found", f"Container {container_id} 不存在")
                raise ValueError(f"Container {container_id} 不存在")

            name = container.name
            attrs = container.attrs
            config = attrs["Config"]
            host_config = attrs["HostConfig"]
            image = config["Image"]

            logger.info(f"Recreating container {name} ({container_id[:12]}) with image {image}")
            self._log_event(workspace_id, "container_recreating",
                            f"正在重建容器 {name}，使用最新 image: {image}")

            # 取得網路配置
            networks = attrs.get("NetworkSettings", {}).get("Networks", {})
            network_name = next(iter(networks), None)

            # 停止並移除舊容器
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Old container {container_id[:12]} removed")

            # 建立 host_config（保留原始配置）
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

            # 建立網路配置
            networking_config = None
            if network_name:
                networking_config = client.api.create_networking_config({
                    network_name: client.api.create_endpoint_config()
                })

            # 解析 ExposedPorts 為 docker-py 格式
            exposed = config.get("ExposedPorts") or {}
            ports_list = []
            for port_key in exposed:
                parts = port_key.split("/")
                ports_list.append((int(parts[0]), parts[1] if len(parts) > 1 else "tcp"))

            # 建立新容器（保留原始配置）
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

            # 啟動新容器
            new_id = container_dict["Id"]
            client.api.start(new_id)

            logger.info(f"New container {new_id[:12]} created and started for workspace {workspace_id}")
            self._log_event(workspace_id, "container_recreated",
                            f"新容器已建立: {new_id[:12]}")

            return new_id

        except docker.errors.APIError as e:
            logger.error(f"Docker API 錯誤: {e}")
            self._log_event(workspace_id, "container_error", f"Docker API 錯誤: {str(e)}")
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Recreate container 失敗: {e}")
            self._log_event(workspace_id, "container_error", f"Recreate container 失敗: {str(e)}")
            raise

    def _stop_and_remove_container(self, container_id: str, workspace_id: str) -> None:
        """停止並刪除 Docker container

        Args:
            container_id: Container ID
            workspace_id: Workspace ID (用於日誌)
        """
        try:
            client = docker.from_env()

            try:
                container = client.containers.get(container_id)
                logger.debug(f"停止 container {container_id}")

                # 停止 container（給予 10 秒優雅關閉時間）
                container.stop(timeout=10)
                logger.debug(f"Container {container_id} 已停止")

                # 刪除 container
                container.remove(force=True)
                logger.info(f"Container {container_id} 已刪除")

                self._log_event(workspace_id, "container_removed", f"已刪除 container: {container_id}")

            except docker.errors.NotFound:
                logger.warning(f"Container {container_id} 不存在，可能已被刪除")
                self._log_event(workspace_id, "container_not_found", f"Container {container_id} 不存在")

            except docker.errors.APIError as e:
                logger.error(f"Docker API 錯誤: {e}")
                self._log_event(workspace_id, "container_error", f"Docker API 錯誤: {str(e)}")
                # 不拋出異常，繼續執行後續步驟

        except Exception as e:
            logger.error(f"停止/刪除 container 失敗: {e}")
            self._log_event(workspace_id, "container_error", f"停止/刪除 container 失敗: {str(e)}")
            # 不拋出異常，繼續執行後續步驟

    def _cleanup_workspace_volumes(self, workspace_id: str) -> None:
        """清理 workspace 掛載的資料目錄
        
        Args:
            workspace_id: Workspace ID
        """
        # 將 UUID 中的橫線替換為下底線
        safe_workspace_id = workspace_id.replace('-', '_')

        # 定義需要刪除的目錄
        directories_to_remove = [
            Path(self.settings.MANAGER_WORKSPACES_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_WORKSPACE_SCRIPTS_DIR) / safe_workspace_id,
            Path(self.settings.MANAGER_CLAUDE_DATA_DIR) / safe_workspace_id,
        ]
        
        for directory in directories_to_remove:
            try:
                if directory.exists():
                    logger.debug(f"刪除目錄: {directory}")
                    shutil.rmtree(directory)
                    logger.debug(f"成功刪除目錄: {directory}")
                    self._log_event(workspace_id, "volume_removed", f"已刪除目錄: {directory}")
                else:
                    logger.debug(f"目錄不存在: {directory}")
                    
            except Exception as e:
                logger.error(f"刪除目錄 {directory} 失敗: {e}")
                self._log_event(workspace_id, "volume_error", f"刪除目錄失敗: {directory} - {str(e)}")
                # 不拋出異常，繼續刪除其他目錄

    def _log_event(self, workspace_id: str, stage: str, message: str, metadata: Optional[dict] = None) -> None:
        """記錄 workspace 操作日誌

        Args:
            workspace_id: Workspace ID
            stage: 操作階段
            message: 日誌訊息
            metadata: 額外的元數據
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
            logger.error(f"記錄日誌失敗: {e}")
            self.db.rollback()
            # 不拋出異常，避免影響主流程


def run_delete_workspace_task(workspace_id: str) -> None:
    """背景任務入口：刪除 workspace
    
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
    """背景任務入口：重啟 workspace container

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
    """背景任務入口：重啟 Browser 容器

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
    """背景任務入口：重啟 Canvas 容器

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
