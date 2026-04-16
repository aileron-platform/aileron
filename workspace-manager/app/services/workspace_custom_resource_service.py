"""Workspace 自訂資源管理服務。"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models

logger = logging.getLogger(__name__)

_WORKSPACE_GROUP = "platform.aileron.io"
_WORKSPACE_VERSION = "v1alpha1"
_WORKSPACE_PLURAL = "workspaces"

_RESTART_OPERATION_FIELDS = {
    "workspace": "restartWorkspaceAt",
    "runtime": "restartRuntimeAt",
    "browser": "restartBrowserAt",
    "nextjs": "restartNextjsAt",
}

_KUBERNETES_PHASE_TO_DB_STATUS = {
    "Pending": "starting",
    "Reconciling": "starting",
    "Running": "running",
    "Failed": "error",
    "Disabled": "stopped",
}

_STATUS_SYNC_MAX_ATTEMPTS = 10
_STATUS_SYNC_INTERVAL_SECONDS = 1.0


class WorkspaceCustomResourceService:
    """負責產生並更新 Kubernetes Workspace 自訂資源描述。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.manifest_root = Path(self.settings.RUNTIME_SCRIPT_ROOT) / "k8s-workspaces"

    def apply_workspace_custom_resource(self, workspace_id: str) -> None:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.error("Workspace %s 不存在，無法產生自訂資源", workspace_id)
            return

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s 非 kubernetes 模式，跳過自訂資源同步", workspace_id)
            return

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation="apply_custom_resource",
            strategy="kubernetes",
            status="queued",
            retries=0,
            scheduled_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()

        self._log_event(
            workspace.id,
            "queued",
            "已排入 Kubernetes Workspace 自訂資源同步",
            {"jobId": job.id},
        )
        self.db.commit()

        try:
            job.status = "provisioning"
            job.started_at = datetime.utcnow()
            self._log_event(workspace.id, "provisioning", "開始產生 Kubernetes Workspace 自訂資源")

            manifest = self._build_workspace_custom_resource(workspace)
            manifest_path = self._write_manifest(workspace, manifest)
            self._apply_manifest_to_cluster(manifest)
            status_synced = self._wait_for_status_sync(workspace.id)

            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log_event(
                workspace.id,
                "completed",
                "Kubernetes Workspace 自訂資源已更新",
                {
                    "manifestPath": str(manifest_path),
                    "crNamespace": manifest["metadata"]["namespace"],
                    "statusSynced": status_synced,
                },
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover - 實際錯誤需紀錄
            logger.exception("更新 Workspace 自訂資源失敗: %s", workspace.id)
            self.db.rollback()
            workspace = self.db.get(db_models.Workspace, workspace_id)
            job = self.db.get(db_models.WorkspaceRuntimeJob, job.id)
            if not workspace or not job:
                return

            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            workspace.runtime_status = "error"
            self._log_event(
                workspace.id,
                "failed",
                "Kubernetes Workspace 自訂資源同步失敗",
                {"error": str(exc)},
            )
            self.db.commit()

    def delete_workspace_custom_resource(self, workspace_id: str) -> bool:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.error("Workspace %s 不存在，無法刪除自訂資源", workspace_id)
            return False

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s 非 kubernetes 模式，跳過自訂資源刪除", workspace_id)
            return False

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation="delete_custom_resource",
            strategy="kubernetes",
            status="queued",
            retries=0,
            scheduled_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()
        self._log_event(
            workspace.id,
            "deleting",
            "開始刪除 Kubernetes Workspace 自訂資源",
            {"jobId": job.id},
        )
        self.db.commit()

        try:
            manifest_path = self._manifest_path(workspace)
            if manifest_path.exists():
                manifest_path.unlink()
            self._delete_custom_resource_from_cluster(workspace)

            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log_event(
                workspace.id,
                "deleted",
                "Kubernetes Workspace 自訂資源已刪除",
                {"manifestPath": str(manifest_path)},
            )
            self.db.delete(workspace)
            self.db.commit()
            return True
        except Exception as exc:  # pragma: no cover
            logger.exception("刪除 Workspace 自訂資源失敗: %s", workspace.id)
            self.db.rollback()
            workspace = self.db.get(db_models.Workspace, workspace_id)
            job = self.db.get(db_models.WorkspaceRuntimeJob, job.id)
            if workspace and job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.utcnow()
                workspace.runtime_status = "error"
                self._log_event(
                    workspace.id,
                    "error",
                    "Kubernetes Workspace 自訂資源刪除失敗",
                    {"error": str(exc)},
                )
                self.db.commit()
            raise

    def request_workspace_restart(self, workspace_id: str) -> None:
        """寫入整體 workspace restart intent。"""
        self._request_restart_operation(
            workspace_id,
            component="workspace",
            status_stage="restarting",
            status_message="已寫入 Kubernetes workspace 重啟意圖",
        )

    def request_runtime_restart(self, workspace_id: str) -> None:
        """寫入 runtime restart intent。"""
        self._request_restart_operation(
            workspace_id,
            component="runtime",
            status_stage="restarting",
            status_message="已寫入 Kubernetes runtime 重啟意圖",
        )

    def request_browser_restart(self, workspace_id: str) -> None:
        """寫入 browser restart intent。"""
        self._request_restart_operation(
            workspace_id,
            component="browser",
            status_stage="browser_restarting",
            status_message="已寫入 Kubernetes browser 重啟意圖",
        )

    def request_nextjs_restart(self, workspace_id: str) -> None:
        """寫入 nextjs restart intent。"""
        self._request_restart_operation(
            workspace_id,
            component="nextjs",
            status_stage="nextjs_restarting",
            status_message="已寫入 Kubernetes nextjs 重啟意圖",
        )

    def sync_workspace_status(self, workspace_id: str) -> bool:
        """從 Kubernetes Workspace CR status 同步工作區 URL 與階段資訊。"""
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.warning("Workspace %s 不存在，無法同步 CR status", workspace_id)
            return False
        return self.sync_workspace_record_status(workspace)

    def sync_workspace_record_status(self, workspace: db_models.Workspace) -> bool:
        """將既有 Workspace ORM 物件與 Kubernetes CR status 對齊。"""
        if workspace.provisioner != "kubernetes":
            return False

        metadata_name, cr_namespace = self._custom_resource_identity(workspace)
        api = self._get_custom_objects_api()

        try:
            custom_resource = api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=cr_namespace,
                plural=_WORKSPACE_PLURAL,
                name=metadata_name,
            )
        except ApiException as exc:
            if exc.status == 404:
                logger.info(
                    "Workspace CR %s/%s 尚未存在，跳過狀態同步",
                    cr_namespace,
                    metadata_name,
                )
                return False
            raise

        status = custom_resource.get("status") or {}
        components = status.get("components") or {}

        workspace.runtime_status = self._normalize_component_phase(
            status.get("phase"),
            fallback=workspace.runtime_status,
        )

        self._apply_component_status(
            workspace,
            component_status=components.get("runtime"),
            phase_attr="runtime_status",
            internal_url_attr="runtime_internal_url",
            external_url_attr="runtime_external_url",
            internal_port_attr="runtime_internal_port",
            external_port_attr="runtime_external_port",
        )
        self._apply_component_status(
            workspace,
            component_status=components.get("browser"),
            phase_attr="browser_status",
            internal_url_attr="browser_webrtc_internal_url",
            external_url_attr="browser_webrtc_external_url",
            internal_port_attr="browser_webrtc_internal_port",
            external_port_attr="browser_webrtc_external_port",
        )
        self._apply_component_status(
            workspace,
            component_status=components.get("nextjs"),
            phase_attr="nextjs_status",
            internal_url_attr="nextjs_internal_url",
            external_url_attr="nextjs_external_url",
            internal_port_attr="nextjs_internal_port",
            external_port_attr="nextjs_external_port",
        )

        workspace.web_preview_internal_url = workspace.nextjs_internal_url
        workspace.web_preview_external_url = workspace.nextjs_external_url
        workspace.web_preview_internal_port = workspace.nextjs_internal_port
        workspace.web_preview_external_port = workspace.nextjs_external_port

        # In k8s, the Go terminal service (port 3004) shares the runtime Ingress host.
        # The operator adds a /ws/terminal path rule that routes to port 3004,
        # so terminal_external_url is identical to runtime_external_url.
        if workspace.runtime_external_url:
            workspace.terminal_external_url = workspace.runtime_external_url
            workspace.terminal_external_port = workspace.runtime_external_port

        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def _build_workspace_custom_resource(self, workspace: db_models.Workspace) -> dict:
        target_namespace = workspace.target_namespace or self.settings.RUNTIME_K8S_NAMESPACE
        cr_namespace = self.settings.RUNTIME_K8S_CR_NAMESPACE or self.settings.RUNTIME_K8S_NAMESPACE
        metadata_name = f"workspace-{workspace.id}"

        return {
            "apiVersion": "platform.aileron.io/v1alpha1",
            "kind": "Workspace",
            "metadata": {
                "name": metadata_name,
                "namespace": cr_namespace,
                "labels": {
                    "app.kubernetes.io/part-of": "aileron",
                    "aileron.io/workspace-id": workspace.id,
                    "aileron.io/owner-id": workspace.owner_id,
                },
            },
            "spec": {
                "workspaceId": workspace.id,
                "ownerId": workspace.owner_id,
                "provisioner": workspace.provisioner,
                "targetNamespace": target_namespace,
                "runtime": {
                    "image": self.settings.RUNTIME_K8S_IMAGE,
                    "imageKey": workspace.runtime,
                    "resources": self._runtime_resources_spec(workspace),
                },
                "nextjs": {
                    "enabled": True,
                    "image": self.settings.RUNTIME_K8S_NEXTJS_IMAGE,
                    "resources": self.settings.RUNTIME_K8S_NEXTJS_RESOURCES,
                },
                "browser": {
                    "enabled": True,
                    "image": self.settings.RUNTIME_K8S_BROWSER_IMAGE,
                    "resources": self.settings.RUNTIME_K8S_BROWSER_RESOURCES,
                },
                "git": {
                    "url": workspace.git_url,
                    "branch": workspace.branch,
                },
                "workspacePath": workspace.workspace_path,
                "envVars": workspace.env_vars or [],
                "operations": {},
                "firewall": {
                    "workspace": {
                        "networkAccessEnabled": workspace.workspace_firewall_network_access_enabled,
                        "domainAccessMode": workspace.workspace_firewall_domain_access_mode,
                        "allowedDomains": workspace.workspace_firewall_allowed_domains or [],
                    },
                    "browser": {
                        "networkAccessEnabled": workspace.browser_firewall_network_access_enabled,
                        "domainAccessMode": workspace.browser_firewall_domain_access_mode,
                        "allowedDomains": workspace.browser_firewall_allowed_domains or [],
                    },
                },
            },
        }

    def _runtime_resources_spec(self, workspace: db_models.Workspace) -> dict:
        return workspace.runtime_resources or self.settings.RUNTIME_K8S_RUNTIME_RESOURCES

    def _request_restart_operation(
        self,
        workspace_id: str,
        *,
        component: str,
        status_stage: str,
        status_message: str,
    ) -> None:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.error("Workspace %s 不存在，無法寫入重啟意圖", workspace_id)
            return

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s 非 kubernetes 模式，跳過重啟意圖寫入", workspace_id)
            return

        if component not in _RESTART_OPERATION_FIELDS:
            raise ValueError(f"不支援的 Kubernetes restart component: {component}")

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation=f"restart_{component}_custom_resource",
            strategy="kubernetes",
            status="queued",
            retries=0,
            scheduled_at=datetime.utcnow(),
        )
        self.db.add(job)
        self.db.flush()
        self._log_event(
            workspace.id,
            status_stage,
            status_message,
            {"jobId": job.id, "component": component},
        )
        self.db.commit()

        try:
            manifest = self._load_or_build_manifest(workspace)
            operations = manifest.setdefault("spec", {}).setdefault("operations", {})
            restart_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

            if component == "workspace":
                operations[_RESTART_OPERATION_FIELDS["workspace"]] = restart_at
                operations[_RESTART_OPERATION_FIELDS["runtime"]] = restart_at
                operations[_RESTART_OPERATION_FIELDS["browser"]] = restart_at
                operations[_RESTART_OPERATION_FIELDS["nextjs"]] = restart_at
            else:
                operations[_RESTART_OPERATION_FIELDS[component]] = restart_at

            manifest_path = self._write_manifest(workspace, manifest)
            self._apply_manifest_to_cluster(manifest)
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log_event(
                workspace.id,
                "completed",
                "Kubernetes Workspace 重啟意圖已更新",
                {
                    "component": component,
                    "manifestPath": str(manifest_path),
                    "requestedAt": restart_at,
                },
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover
            logger.exception("寫入 Workspace 重啟意圖失敗: %s", workspace.id)
            self.db.rollback()
            workspace = self.db.get(db_models.Workspace, workspace_id)
            job = self.db.get(db_models.WorkspaceRuntimeJob, job.id)
            if workspace and job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.utcnow()
                self._mark_restart_failure(workspace, component)
                self._log_event(
                    workspace.id,
                    "error",
                    "Kubernetes Workspace 重啟意圖更新失敗",
                    {"component": component, "error": str(exc)},
                )
                self.db.commit()
            raise

    def _load_or_build_manifest(self, workspace: db_models.Workspace) -> dict:
        manifest_path = self._manifest_path(workspace)
        if manifest_path.exists():
            return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        return self._build_workspace_custom_resource(workspace)

    def _mark_restart_failure(
        self,
        workspace: db_models.Workspace,
        component: str,
    ) -> None:
        if component in {"workspace", "runtime"}:
            workspace.runtime_status = "error"
        if component in {"workspace", "browser"}:
            workspace.browser_status = "error"
        if component in {"workspace", "nextjs"}:
            workspace.nextjs_status = "error"

    def _write_manifest(self, workspace: db_models.Workspace, manifest: dict) -> Path:
        output_dir = self._manifest_dir(workspace)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._manifest_path(workspace)
        output_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return output_path

    def _manifest_dir(self, workspace: db_models.Workspace) -> Path:
        namespace = self.settings.RUNTIME_K8S_CR_NAMESPACE or self.settings.RUNTIME_K8S_NAMESPACE
        return self.manifest_root / namespace

    def _manifest_path(self, workspace: db_models.Workspace) -> Path:
        return self._manifest_dir(workspace) / f"{workspace.id}.yaml"

    def _custom_resource_identity(self, workspace: db_models.Workspace) -> tuple[str, str]:
        cr_namespace = self.settings.RUNTIME_K8S_CR_NAMESPACE or self.settings.RUNTIME_K8S_NAMESPACE
        return f"workspace-{workspace.id}", cr_namespace

    def _normalize_component_phase(self, phase: str | None, *, fallback: str) -> str:
        if not phase:
            return fallback
        return _KUBERNETES_PHASE_TO_DB_STATUS.get(phase, fallback)

    def _apply_component_status(
        self,
        workspace: db_models.Workspace,
        *,
        component_status: dict | None,
        phase_attr: str,
        internal_url_attr: str,
        external_url_attr: str,
        internal_port_attr: str,
        external_port_attr: str,
    ) -> None:
        if not component_status:
            return

        setattr(
            workspace,
            phase_attr,
            self._normalize_component_phase(
                component_status.get("phase"),
                fallback=getattr(workspace, phase_attr),
            ),
        )

        internal_url = component_status.get("internalUrl") or None
        external_url = component_status.get("externalUrl") or None

        setattr(workspace, internal_url_attr, internal_url)
        setattr(workspace, external_url_attr, external_url)
        setattr(
            workspace,
            internal_port_attr,
            self._port_from_url(internal_url) or getattr(workspace, internal_port_attr),
        )
        setattr(
            workspace,
            external_port_attr,
            self._port_from_url(external_url),
        )

    def _wait_for_status_sync(
        self,
        workspace_id: str,
        *,
        max_attempts: int = _STATUS_SYNC_MAX_ATTEMPTS,
        interval_seconds: float = _STATUS_SYNC_INTERVAL_SECONDS,
    ) -> bool:
        for attempt in range(1, max_attempts + 1):
            try:
                if self.sync_workspace_status(workspace_id):
                    return True
            except Exception:
                logger.exception(
                    "同步 Workspace CR 狀態失敗: %s (attempt=%s/%s)",
                    workspace_id,
                    attempt,
                    max_attempts,
                )

            if attempt < max_attempts:
                time.sleep(interval_seconds)

        logger.warning(
            "Workspace CR 狀態尚未同步回資料庫: %s (attempts=%s)",
            workspace_id,
            max_attempts,
        )
        return False

    def _port_from_url(self, value: str | None) -> int | None:
        if not value:
            return None
        parsed = urlparse(value)
        return parsed.port

    def _get_custom_objects_api(self) -> client.CustomObjectsApi:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        return client.CustomObjectsApi()

    def _apply_manifest_to_cluster(self, manifest: dict) -> None:
        metadata = manifest["metadata"]
        api = self._get_custom_objects_api()
        body = {
            "apiVersion": manifest["apiVersion"],
            "kind": manifest["kind"],
            "metadata": metadata,
            "spec": manifest["spec"],
        }
        try:
            api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=metadata["namespace"],
                plural=_WORKSPACE_PLURAL,
                name=metadata["name"],
            )
        except ApiException as exc:
            if exc.status != 404:
                raise
            api.create_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=metadata["namespace"],
                plural=_WORKSPACE_PLURAL,
                body=body,
            )
            return

        api.patch_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=metadata["namespace"],
            plural=_WORKSPACE_PLURAL,
            name=metadata["name"],
            body=body,
        )

    def _delete_custom_resource_from_cluster(self, workspace: db_models.Workspace) -> None:
        manifest = self._load_or_build_manifest(workspace)
        metadata = manifest["metadata"]
        api = self._get_custom_objects_api()
        try:
            api.delete_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=metadata["namespace"],
                plural=_WORKSPACE_PLURAL,
                name=metadata["name"],
            )
        except ApiException as exc:
            if exc.status != 404:
                raise

    def _log_event(
        self,
        workspace_id: str,
        stage: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        log_entry = db_models.WorkspaceRuntimeLog(
            id=str(uuid4()),
            workspace_id=workspace_id,
            stage=stage,
            message=message,
            log_metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
        self.db.add(log_entry)
        logger.info("[workspace:%s][%s] %s", workspace_id, stage, message)


def run_apply_workspace_custom_resource_task(workspace_id: str) -> None:
    """背景任務入口：開啟新的資料庫連線並產生 Workspace CR manifest。"""

    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        service = WorkspaceCustomResourceService(db)
        service.apply_workspace_custom_resource(workspace_id)
    finally:
        db.close()


__all__ = [
    "WorkspaceCustomResourceService",
    "run_apply_workspace_custom_resource_task",
]
