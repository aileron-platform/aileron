"""Workspace custom resource management service."""

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
    "canvas": "restartCanvasAt",
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
    """Responsible for generating and updating Kubernetes workspace custom resource descriptions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.manifest_root = Path(self.settings.RUNTIME_SCRIPT_ROOT) / "k8s-workspaces"

    def apply_workspace_custom_resource(self, workspace_id: str) -> None:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.error("Workspace %s does not exist, cannot generate custom resource", workspace_id)
            return

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s is not kubernetes mode, skip custom resource synchronization", workspace_id)
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
            "Queued Kubernetes workspace custom resource synchronization",
            {"jobId": job.id},
        )
        self.db.commit()

        try:
            job.status = "provisioning"
            job.started_at = datetime.utcnow()
            self._log_event(workspace.id, "provisioning", "Begin generating Kubernetes workspace custom resource")

            manifest = self._build_workspace_custom_resource(workspace)
            manifest_path = self._write_manifest(workspace, manifest)
            self._apply_manifest_to_cluster(manifest)
            status_synced = self._wait_for_status_sync(workspace.id)

            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log_event(
                workspace.id,
                "completed",
                "Kubernetes workspace custom resource updated",
                {
                    "manifestPath": str(manifest_path),
                    "crNamespace": manifest["metadata"]["namespace"],
                    "statusSynced": status_synced,
                },
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover - actual errors need logging
            logger.exception("Failed to update workspace custom resource: %s", workspace.id)
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
                "Kubernetes workspace custom resource synchronization failed",
                {"error": str(exc)},
            )
            self.db.commit()

    def delete_workspace_custom_resource(self, workspace_id: str) -> bool:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.error("Workspace %s does not exist, cannot delete custom resource", workspace_id)
            return False

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s is not kubernetes mode, skip custom resource deletion", workspace_id)
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
            "Begin deleting Kubernetes workspace custom resource",
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
                "Kubernetes workspace custom resource deleted",
                {"manifestPath": str(manifest_path)},
            )
            self.db.delete(workspace)
            self.db.commit()
            return True
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to delete workspace custom resource: %s", workspace.id)
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
                    "Kubernetes workspace custom resource deletion failed",
                    {"error": str(exc)},
                )
                self.db.commit()
            raise

    def request_workspace_restart(self, workspace_id: str) -> None:
        """Write overall workspace restart intent."""
        self._request_restart_operation(
            workspace_id,
            component="workspace",
            status_stage="restarting",
            status_message="Wrote Kubernetes workspace restart intent",
        )

    def request_runtime_restart(self, workspace_id: str) -> None:
        """Write runtime restart intent."""
        self._request_restart_operation(
            workspace_id,
            component="runtime",
            status_stage="restarting",
            status_message="Wrote Kubernetes runtime restart intent",
        )

    def request_browser_restart(self, workspace_id: str) -> None:
        """Write browser restart intent."""
        self._request_restart_operation(
            workspace_id,
            component="browser",
            status_stage="browser_restarting",
            status_message="Wrote Kubernetes browser restart intent",
        )

    def request_canvas_restart(self, workspace_id: str) -> None:
        """Write canvas restart intent."""
        self._request_restart_operation(
            workspace_id,
            component="canvas",
            status_stage="canvas_restarting",
            status_message="Wrote Kubernetes canvas restart intent",
        )

    def sync_workspace_status(self, workspace_id: str) -> bool:
        """Sync workspace URL and phase information from Kubernetes workspace CR status."""
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            logger.warning("Workspace %s does not exist, cannot sync CR status", workspace_id)
            return False
        return self.sync_workspace_record_status(workspace)

    def sync_workspace_record_status(self, workspace: db_models.Workspace) -> bool:
        """Align existing workspace ORM object with Kubernetes CR status."""
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
                    "Workspace CR %s/%s does not exist yet, skip status synchronization",
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
            component_status=components.get("canvas"),
            phase_attr="canvas_status",
            internal_url_attr="canvas_internal_url",
            external_url_attr="canvas_external_url",
            internal_port_attr="canvas_internal_port",
            external_port_attr="canvas_external_port",
        )

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
                    "agentState": self._agent_state_spec(workspace),
                },
                "canvas": {
                    "enabled": True,
                    "image": self.settings.RUNTIME_K8S_CANVAS_IMAGE,
                    "resources": self.settings.RUNTIME_K8S_CANVAS_RESOURCES,
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
                "knowledgeBases": self._knowledge_base_specs(workspace),
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

    def _knowledge_base_specs(self, workspace: db_models.Workspace) -> list[dict[str, object]]:
        specs: list[dict[str, object]] = []
        raw_attachments = getattr(workspace, "knowledge_base_attachments", [])
        if not isinstance(raw_attachments, list):
            return specs

        for attachment in raw_attachments:
            knowledge_base = getattr(attachment, "knowledge_base", None)
            if getattr(knowledge_base, "tombstoned_at", None) is not None:
                continue

            kb_id = getattr(attachment, "kb_id", None)
            mount_alias = getattr(attachment, "mount_alias", None)
            if not isinstance(kb_id, str) or not isinstance(mount_alias, str):
                continue

            specs.append(
                {
                    "kbId": kb_id,
                    "mountAlias": mount_alias,
                    "readOnly": getattr(attachment, "mode", "rw") == "ro",
                }
            )

        return specs

    def _runtime_resources_spec(self, workspace: db_models.Workspace) -> dict:
        return workspace.runtime_resources or self.settings.RUNTIME_K8S_RUNTIME_RESOURCES

    def _agent_state_spec(self, workspace: db_models.Workspace) -> dict[str, object]:
        workspace_id = workspace.id.replace("-", "_")
        sub_path_root = self.settings.RUNTIME_K8S_AGENT_STATE_SUB_PATH_ROOT.strip("/")
        return {
            "pvcName": self.settings.RUNTIME_K8S_AGENT_STATE_PVC_NAME,
            "subPathRoot": sub_path_root,
            "mounts": [
                {
                    "provider": "claude",
                    "sourceSubPath": f"{sub_path_root}/{workspace_id}/claude/home",
                    "mountPath": "/home/developer/.claude",
                },
                {
                    "provider": "codex",
                    "sourceSubPath": f"{sub_path_root}/{workspace_id}/codex/home",
                    "mountPath": "/home/developer/.codex",
                },
                {
                    "provider": "codex-sessions",
                    "sourceSubPath": f"{sub_path_root}/{workspace_id}/codex/sessions",
                    "mountPath": "/home/developer/.codex-sessions",
                },
                {
                    "provider": "gemini",
                    "sourceSubPath": f"{sub_path_root}/{workspace_id}/gemini/home",
                    "mountPath": "/home/developer/.gemini",
                },
            ],
        }

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
            logger.error("Workspace %s does not exist, cannot write restart intent", workspace_id)
            return

        if workspace.provisioner != "kubernetes":
            logger.info("Workspace %s is not kubernetes mode, skip restart intent write", workspace_id)
            return

        if component not in _RESTART_OPERATION_FIELDS:
            raise ValueError(f"Unsupported Kubernetes restart component: {component}")

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
                operations[_RESTART_OPERATION_FIELDS["canvas"]] = restart_at
            else:
                operations[_RESTART_OPERATION_FIELDS[component]] = restart_at

            manifest_path = self._write_manifest(workspace, manifest)
            self._apply_manifest_to_cluster(manifest)
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            self._log_event(
                workspace.id,
                "completed",
                "Kubernetes workspace restart intent updated",
                {
                    "component": component,
                    "manifestPath": str(manifest_path),
                    "requestedAt": restart_at,
                },
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to write workspace restart intent: %s", workspace.id)
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
                    "Kubernetes workspace restart intent update failed",
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
        if component in {"workspace", "canvas"}:
            workspace.canvas_status = "error"

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
                    "Failed to sync workspace CR status: %s (attempt=%s/%s)",
                    workspace_id,
                    attempt,
                    max_attempts,
                )

            if attempt < max_attempts:
                time.sleep(interval_seconds)

        logger.warning(
            "Workspace CR status not yet synced to database: %s (attempts=%s)",
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
    """Background task entry: Open new database connection and generate workspace CR manifest."""

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
