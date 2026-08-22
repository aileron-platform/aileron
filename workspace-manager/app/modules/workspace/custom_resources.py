"""Workspace custom resource management service."""

from __future__ import annotations

import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, cast
from urllib.parse import urlparse
from uuid import UUID

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.knowledge_base.mount_snapshot import canonical_mount_snapshot
from app.modules.platform_resource_capacity.lifecycle import (
    PlatformResourceCapacityAdministration,
)
from app.modules.platform_resource_capacity.models import (
    STORAGE_ERROR_CODES,
    StorageErrorCode,
    StorageObservation,
    WorkspaceStorageDesiredState,
    WorkspaceStorageKind,
    WorkspaceStorageObservation,
)
from app.modules.workspace.advisory_lock import (
    try_acquire_workspace_transaction_lock,
)
from app.modules.workspace.browser_connectivity_contract_generated import (
    CONNECTIVITY_ERROR_CODES,
    CONNECTIVITY_REASONS,
)
from app.modules.workspace.orchestrator.base import (
    WorkspaceRuntimeTerminationUnconfirmedError,
)
from app.modules.workspace.runtime.control_token import issue_runtime_control_token
from app.modules.workspace.runtime.database import (
    RuntimeDatabaseCredential,
    WorkspaceRuntimeDatabaseService,
)
from app.modules.workspace.runtime.job_repository import (
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
)
from app.modules.workspace.service_identities import workspace_service_identity

logger = logging.getLogger(__name__)

_WORKSPACE_GROUP = "platform.aileron.io"
_WORKSPACE_VERSION = "v1alpha1"
_WORKSPACE_PLURAL = "workspaces"
_IMMUTABLE_IMAGE_REFERENCE_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$"
)

_KUBERNETES_PHASE_TO_DB_STATUS = {
    "Pending": "starting",
    "Reconciling": "starting",
    "Running": "running",
    "Failed": "error",
    "Disabled": "stopped",
}

_READ_SYNC_PROTECTED_STATUSES = {
    "starting",
    "stopping",
    "restarting",
    "deleting",
    "error",
}

_RUNTIME_STATE_OWNER_OPERATIONS = {
    "starting": {"workspace_start"},
    "stopping": {"workspace_stop"},
    "restarting": {"runtime_restart"},
    "deleting": {"workspace_delete"},
}

_STATUS_SYNC_MAX_ATTEMPTS = 10
_STATUS_SYNC_INTERVAL_SECONDS = 1.0
_TERMINATION_PROOF_MAX_ATTEMPTS = 180
_TERMINATION_PROOF_INTERVAL_SECONDS = 1.0


def _storage_spec_payload(
    desired: WorkspaceStorageDesiredState,
) -> dict[str, dict[str, int]]:
    return {
        "workspaceData": {
            "capacityBytes": desired.workspace_data.capacity_bytes,
            "revision": desired.workspace_data.revision,
        },
        "runtimeHome": {
            "capacityBytes": desired.runtime_home.capacity_bytes,
            "revision": desired.runtime_home.revision,
        },
    }


def _storage_observation(
    value: object,
) -> WorkspaceStorageObservation:
    if not isinstance(value, dict):
        return WorkspaceStorageObservation(items=())
    items: list[StorageObservation] = []
    for storage_kind, wire_name in (
        ("workspace_data", "workspaceData"),
        ("runtime_home", "runtimeHome"),
    ):
        raw = value.get(wire_name)
        if not isinstance(raw, dict):
            continue
        allocated_bytes = raw.get("allocatedBytes")
        observed_revision = raw.get("observedRevision")
        expansion_supported = raw.get("expansionSupported")
        error_code = raw.get("errorCode")
        observed_at = raw.get("observedAt")
        if (
            not isinstance(allocated_bytes, int)
            or isinstance(allocated_bytes, bool)
            or allocated_bytes < 0
            or not isinstance(observed_revision, int)
            or isinstance(observed_revision, bool)
            or observed_revision < 0
            or not isinstance(expansion_supported, bool)
            or (error_code is not None and not isinstance(error_code, str))
            or (observed_at is not None and not isinstance(observed_at, str))
        ):
            continue
        try:
            parsed_observed_at = (
                datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                if observed_at is not None
                else None
            )
        except ValueError:
            continue
        normalized_error = error_code.strip() if error_code else None
        if normalized_error is not None and normalized_error not in STORAGE_ERROR_CODES:
            continue
        items.append(
            StorageObservation(
                storage_kind=cast(WorkspaceStorageKind, storage_kind),
                allocated_bytes=allocated_bytes,
                observed_revision=observed_revision,
                expansion_supported=expansion_supported,
                error_code=(
                    cast(StorageErrorCode, normalized_error)
                    if normalized_error is not None
                    else None
                ),
                observed_at=parsed_observed_at,
            )
        )
    return WorkspaceStorageObservation(items=tuple(items))


def _optional_status_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_status_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class WorkspaceCustomResourceNotReadyError(RuntimeError):
    """The desired Kubernetes execution-plane generation is not fully ready."""

    code = "WORKSPACE_CUSTOM_RESOURCE_NOT_READY"


class WorkspaceKnowledgeBasePreflightError(RuntimeError):
    """Shared knowledge base PVC is not safe for a candidate generation."""

    code = "KB_MOUNT_SOURCE_INVALID"


@dataclass(frozen=True)
class WorkspaceCustomResourceExecutionPlan:
    """Immutable Kubernetes desired state prepared in a caller-owned transaction."""

    workspace_id: str
    target_namespace: str
    runtime_instance_id: str
    mount_revision: int
    observed_mount_revision: int
    access_revision: int
    database_credential: RuntimeDatabaseCredential
    runtime_control_token: str
    setup_script: str
    manifest: dict[str, object]


@dataclass(frozen=True)
class WorkspaceCustomResourceExecutionResult:
    """Fully-ready Kubernetes workload identities returned without database writes."""

    workspace_id: str
    target_namespace: str
    runtime_instance_id: str
    mount_revision: int
    access_revision: int
    runtime_pod_uid: str
    browser_pod_uid: str | None
    canvas_pod_uid: str | None
    status: dict[str, object]

    @property
    def runtime_internal_url(self) -> str:
        return workspace_service_identity(
            "runtime",
            self.workspace_id,
            self.target_namespace,
        ).url


@dataclass(frozen=True)
class WorkspaceCustomResourceExecutionIdentity:
    """Persisted Kubernetes identities required for fail-closed termination proof."""

    workspace_id: str
    target_namespace: str
    runtime_instance_id: str | None
    runtime_pod_uid: str | None
    browser_pod_uid: str | None
    canvas_pod_uid: str | None


@dataclass(frozen=True)
class WorkspaceCustomResourceStatusSnapshot:
    """Kubernetes status fetched without holding a database connection."""

    workspace_id: str
    resource_name: str
    namespace: str
    custom_resource: dict[str, object]


class WorkspaceCustomResourceService:
    """Responsible for generating and updating Kubernetes workspace custom resource descriptions."""

    def __init__(
        self,
        db: Session,
        *,
        runtime_database_service: WorkspaceRuntimeDatabaseService | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.runtime_database_service = (
            runtime_database_service
            if runtime_database_service is not None
            else WorkspaceRuntimeDatabaseService()
        )
        self.capacity = PlatformResourceCapacityAdministration(db)

    def _prepare_generation(
        self,
        workspace: db_models.Workspace,
        *,
        runtime_instance_id: str,
    ) -> WorkspaceCustomResourceExecutionPlan:
        """Prepare desired Kubernetes state without creating a job or committing."""

        if workspace.provisioner != "kubernetes":
            raise ValueError("Workspace provisioner must be kubernetes")
        canonical_instance_id = str(UUID(runtime_instance_id))
        if canonical_instance_id != runtime_instance_id:
            raise ValueError("Runtime instance identifier must be canonical")
        database_credential = self.runtime_database_service.prepare(
            workspace_id=workspace.id,
            runtime_instance_id=canonical_instance_id,
        )
        control_token = issue_runtime_control_token()
        # Keep both constrained generation IDs aligned before manifest construction,
        # which can trigger a Session flush.
        workspace.runtime_instance_id = canonical_instance_id
        workspace.runtime_control_instance_id = canonical_instance_id
        workspace.runtime_control_token_hash = control_token.digest
        manifest = self._build_workspace_custom_resource(
            workspace,
            runtime_instance_id=canonical_instance_id,
            runtime_secret_name=database_credential.secret_name,
        )
        target_namespace = self.settings.RUNTIME_K8S_NAMESPACE
        return WorkspaceCustomResourceExecutionPlan(
            workspace_id=workspace.id,
            target_namespace=target_namespace,
            runtime_instance_id=canonical_instance_id,
            mount_revision=workspace.knowledge_base_mount_desired_revision,
            observed_mount_revision=(workspace.knowledge_base_mount_observed_revision),
            access_revision=workspace.runtime_access_revision,
            database_credential=database_credential,
            runtime_control_token=control_token.value,
            setup_script=workspace.setup_script or "#!/bin/sh\nexit 0\n",
            manifest=manifest,
        )

    def _apply_generation(
        self,
        plan: WorkspaceCustomResourceExecutionPlan,
        *,
        assert_claim: Callable[[], None],
        max_attempts: int = _STATUS_SYNC_MAX_ATTEMPTS,
        interval_seconds: float = _STATUS_SYNC_INTERVAL_SECONDS,
    ) -> WorkspaceCustomResourceExecutionResult:
        """Apply and observe one generation without database writes or commits."""

        assert_claim()
        self.runtime_database_service.activate(plan.database_credential)
        try:
            self._upsert_runtime_secret(
                credential=plan.database_credential,
                runtime_control_token=plan.runtime_control_token,
                setup_script=plan.setup_script,
            )
            self._apply_manifest_to_cluster(plan.manifest)
            for attempt in range(1, max_attempts + 1):
                assert_claim()
                try:
                    custom_resource = self._get_workspace_custom_resource(plan.manifest)
                except ApiException as exc:
                    if exc.status != 404:
                        raise
                    custom_resource = {}
                result = self._execution_result(plan, custom_resource)
                if result is not None:
                    assert_claim()
                    return result
                if attempt < max_attempts:
                    time.sleep(interval_seconds)
            raise WorkspaceCustomResourceNotReadyError(
                "Kubernetes workspace generation did not become ready"
            )
        except Exception:
            try:
                self._discard_generation(
                    WorkspaceCustomResourceExecutionIdentity(
                        workspace_id=plan.workspace_id,
                        target_namespace=plan.target_namespace,
                        runtime_instance_id=plan.runtime_instance_id,
                        runtime_pod_uid=None,
                        browser_pod_uid=None,
                        canvas_pod_uid=None,
                    ),
                    assert_claim=assert_claim,
                )
            except Exception:
                logger.exception(
                    "Failed to stop incomplete Kubernetes Workspace generation",
                    extra={
                        "workspace_id": plan.workspace_id,
                        "runtime_instance_id": plan.runtime_instance_id,
                    },
                )
            raise

    def _stage_generation(
        self,
        workspace: db_models.Workspace,
        result: WorkspaceCustomResourceExecutionResult,
    ) -> None:
        """Stage a fully-ready generation in the caller-owned transaction."""

        if workspace.id != result.workspace_id:
            raise ValueError("Workspace execution result does not match workspace")
        if workspace.knowledge_base_mount_desired_revision != result.mount_revision:
            raise ValueError("Knowledge base mount revision advanced during execution")
        if workspace.runtime_access_revision != result.access_revision:
            raise ValueError("Runtime access revision advanced during execution")
        if (
            workspace.runtime_instance_id != result.runtime_instance_id
            or workspace.runtime_control_instance_id != result.runtime_instance_id
            or not workspace.runtime_control_token_hash
        ):
            raise ValueError("Runtime control generation is not active")

        workspace.browser_instance_id = result.runtime_instance_id
        workspace.canvas_instance_id = result.runtime_instance_id
        workspace.runtime_container_id = result.runtime_pod_uid
        workspace.browser_container_id = result.browser_pod_uid
        workspace.canvas_container_id = result.canvas_pod_uid
        self._apply_internal_service_urls(
            workspace,
            namespace=result.target_namespace,
        )
        workspace.knowledge_base_mount_observed_revision = result.mount_revision
        workspace.runtime_access_observed_revision = result.access_revision
        components = result.status.get("components")
        if isinstance(components, dict):
            for component in ("runtime", "browser", "canvas"):
                component_status = components.get(component)
                if not isinstance(component_status, dict):
                    continue
                observed_revision = component_status.get("observedRevision")
                desired_revision = getattr(workspace, f"{component}_desired_revision")
                if (
                    isinstance(observed_revision, int)
                    and 0 <= observed_revision <= desired_revision
                ):
                    setattr(
                        workspace,
                        f"{component}_observed_revision",
                        observed_revision,
                    )
        bootstrap = result.status.get("bootstrap")
        if isinstance(bootstrap, dict):
            observed_revision = bootstrap.get("observedRevision")
            if (
                isinstance(observed_revision, int)
                and 0 <= observed_revision <= workspace.bootstrap_revision
            ):
                workspace.bootstrap_observed_revision = observed_revision
            phase = bootstrap.get("phase")
            if isinstance(phase, str):
                workspace.bootstrap_status = phase.lower()
                workspace.bootstrap_error_code = bootstrap.get("errorCode")
                workspace.bootstrap_last_transition_at = datetime.utcnow()

        components = result.status.get("components") or {}
        if not isinstance(components, dict):
            raise ValueError("Workspace execution result components are invalid")
        self._apply_component_status(
            workspace,
            component="runtime",
            component_status=components.get("runtime"),
            phase_attr="runtime_status",
        )
        self._apply_component_status(
            workspace,
            component="browser",
            component_status=components.get("browser"),
            phase_attr="browser_status",
        )
        self._apply_component_status(
            workspace,
            component="canvas",
            component_status=components.get("canvas"),
            phase_attr="canvas_status",
        )
        workspace.terminal_internal_url = self._url_with_port(
            workspace.runtime_internal_url,
            3004,
        )

    def _discard_generation(
        self,
        execution: (
            WorkspaceCustomResourceExecutionIdentity
            | WorkspaceCustomResourceExecutionResult
        ),
        *,
        assert_claim: Callable[[], None],
        max_attempts: int = _TERMINATION_PROOF_MAX_ATTEMPTS,
        interval_seconds: float = _TERMINATION_PROOF_INTERVAL_SECONDS,
    ) -> None:
        """Stop one failed generation while preserving the Workspace CR and PVCs."""

        state = self._stop_workspace_custom_resource_generation(
            execution,
            assert_claim=assert_claim,
        )
        if state == "replaced" and all(
            pod_uid is None
            for pod_uid in (
                execution.runtime_pod_uid,
                execution.browser_pod_uid,
                execution.canvas_pod_uid,
            )
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation changed before cleanup"
            )
        self._prove_generation_absent(
            execution,
            assert_claim=assert_claim,
            max_attempts=max_attempts,
            interval_seconds=interval_seconds,
        )
        self._cleanup_runtime_generation(execution)

    def _delete_persisted_workspace(
        self,
        identity: WorkspaceCustomResourceExecutionIdentity,
        *,
        assert_claim: Callable[[], None],
        max_attempts: int = _TERMINATION_PROOF_MAX_ATTEMPTS,
        interval_seconds: float = _TERMINATION_PROOF_INTERVAL_SECONDS,
    ) -> None:
        """Delete the domain Workspace CR and prove its managed resources absent."""

        assert_claim()
        self._delete_workspace_custom_resource(
            api=self._get_custom_objects_api(),
            namespace=self.settings.RUNTIME_K8S_NAMESPACE,
            name=f"workspace-{identity.workspace_id}",
            assert_claim=assert_claim,
        )
        self.prove_workspace_absent(
            workspace_id=identity.workspace_id,
            assert_claim=assert_claim,
            max_attempts=max_attempts,
            interval_seconds=interval_seconds,
        )
        self._cleanup_runtime_generation(identity)

    def _cleanup_runtime_generation(
        self,
        identity: WorkspaceCustomResourceExecutionIdentity,
    ) -> None:
        if (
            not isinstance(identity.runtime_instance_id, str)
            or not identity.runtime_instance_id
        ):
            return
        credential = self.runtime_database_service.prepare(
            workspace_id=identity.workspace_id,
            runtime_instance_id=identity.runtime_instance_id,
        )
        self._delete_runtime_secret(
            secret_name=credential.secret_name,
        )
        self.runtime_database_service.deactivate(credential)

    def _stop_persisted_generation(
        self,
        workspace: db_models.Workspace,
        *,
        assert_claim: Callable[[], None],
    ) -> None:
        """Stop compute and revoke its generation while retaining the CR and PVCs."""

        self._discard_generation(
            WorkspaceCustomResourceExecutionIdentity(
                workspace_id=workspace.id,
                target_namespace=self.settings.RUNTIME_K8S_NAMESPACE,
                runtime_instance_id=workspace.runtime_instance_id,
                runtime_pod_uid=workspace.runtime_container_id,
                browser_pod_uid=workspace.browser_container_id,
                canvas_pod_uid=workspace.canvas_container_id,
            ),
            assert_claim=assert_claim,
        )

    def apply_component_desired_revision(
        self,
        workspace: db_models.Workspace,
        *,
        component: str,
        assert_claim: Callable[[], None],
        runtime_plan: WorkspaceCustomResourceExecutionPlan | None = None,
        component_instance_id: str | None = None,
        max_attempts: int = _STATUS_SYNC_MAX_ATTEMPTS,
        interval_seconds: float = _STATUS_SYNC_INTERVAL_SECONDS,
    ) -> None:
        """Patch and observe one component revision without replacing siblings."""

        if component not in {"runtime", "browser", "canvas"}:
            raise ValueError("Workspace component is invalid")
        assert_claim()
        name, namespace = self._custom_resource_identity(workspace)
        target_instance_id = component_instance_id or getattr(
            workspace,
            f"{component}_instance_id",
        )
        if not isinstance(target_instance_id, str):
            raise ValueError("Workspace component instance identifier is required")
        canonical_instance_id = str(UUID(target_instance_id))
        if canonical_instance_id != target_instance_id:
            raise ValueError(
                "Workspace component instance identifier must be canonical"
            )
        component_spec = {
            "desiredState": getattr(workspace, f"{component}_desired_state").title(),
            "instanceId": canonical_instance_id,
            "revision": getattr(workspace, f"{component}_desired_revision"),
        }
        if component == "browser":
            component_spec.update(
                {
                    "credentialSecretName": (
                        f"workspace-browser-credential-{workspace.id}"
                        f"-r{workspace.browser_credential_revision}"
                    ),
                    "credentialRevision": workspace.browser_credential_revision,
                    "credentialKeyId": workspace.browser_credential_key_id,
                    "credentialAlgorithm": workspace.browser_credential_algorithm,
                }
            )
        body_spec: dict[str, object] = {component: component_spec}
        if runtime_plan is not None:
            if component != "runtime":
                raise ValueError("Runtime plan requires the Runtime component")
            self.runtime_database_service.activate(runtime_plan.database_credential)
            self._upsert_runtime_secret(
                credential=runtime_plan.database_credential,
                runtime_control_token=runtime_plan.runtime_control_token,
                setup_script=runtime_plan.setup_script,
            )
            manifest_spec = runtime_plan.manifest["spec"]
            component_spec = manifest_spec["runtime"]
            body_spec = {
                "runtime": component_spec,
                "knowledgeBases": manifest_spec["knowledgeBases"],
            }
        body = {"spec": body_spec}
        api = self._get_custom_objects_api()
        api.patch_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=namespace,
            plural=_WORKSPACE_PLURAL,
            name=name,
            body=body,
        )
        target_revision = getattr(workspace, f"{component}_desired_revision")
        for attempt in range(1, max_attempts + 1):
            assert_claim()
            custom_resource = api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=namespace,
                plural=_WORKSPACE_PLURAL,
                name=name,
            )
            status = custom_resource.get("status")
            components = status.get("components") if isinstance(status, dict) else None
            component_status = (
                components.get(component) if isinstance(components, dict) else None
            )
            browser_credential_observed = True
            if component == "browser":
                browser_credential_observed = isinstance(component_status, dict) and (
                    component_status.get("credentialObservedRevision")
                    == workspace.browser_credential_revision
                    and component_status.get("credentialObservedKeyId")
                    == workspace.browser_credential_key_id
                    and component_status.get("credentialObservedAlgorithm")
                    == workspace.browser_credential_algorithm
                )
            component_ready = (
                isinstance(component_status, dict)
                and component_status.get("observedInstanceId") == canonical_instance_id
                and component_status.get("observedRevision") == target_revision
                and component_status.get("phase") == "Running"
                and component_status.get("ready") is True
                and browser_credential_observed
            )
            if runtime_plan is not None:
                component_ready = self._execution_plane_status_is_ready(
                    custom_resource,
                    runtime_instance_id=runtime_plan.runtime_instance_id,
                    runtime_revision=target_revision,
                    mount_revision=runtime_plan.mount_revision,
                    access_revision=runtime_plan.access_revision,
                )
            if component_ready:
                return
            if attempt < max_attempts:
                time.sleep(interval_seconds)
        raise WorkspaceCustomResourceNotReadyError(
            f"Kubernetes {component} revision did not become ready"
        )

    def preflight_knowledge_base_mounts(
        self,
        workspace: db_models.Workspace,
    ) -> None:
        """Verify the shared PVC is bound before applying a mount generation."""

        if workspace.provisioner != "kubernetes":
            return
        try:
            pvc = self._get_core_v1_api().read_namespaced_persistent_volume_claim(
                name=self.settings.KNOWLEDGE_BASES_PVC_NAME,
                namespace=self.settings.RUNTIME_K8S_NAMESPACE,
            )
        except Exception as exc:
            raise WorkspaceKnowledgeBasePreflightError(
                "Shared knowledge base PVC is unavailable"
            ) from exc
        status = getattr(pvc, "status", None)
        phase = (
            status.get("phase")
            if isinstance(status, dict)
            else getattr(status, "phase", None)
        )
        if phase != "Bound":
            raise WorkspaceKnowledgeBasePreflightError(
                "Shared knowledge base PVC is not bound"
            )

    def _stop_workspace_custom_resource_generation(
        self,
        execution: (
            WorkspaceCustomResourceExecutionIdentity
            | WorkspaceCustomResourceExecutionResult
        ),
        *,
        assert_claim: Callable[[], None],
    ) -> str:
        """CAS-stop the expected generation without deleting its Workspace CR."""

        assert_claim()
        api = self._get_custom_objects_api()
        cr_namespace = execution.target_namespace
        resource_name = f"workspace-{execution.workspace_id}"
        try:
            custom_resource = api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=cr_namespace,
                plural=_WORKSPACE_PLURAL,
                name=resource_name,
            )
        except ApiException as exc:
            assert_claim()
            if exc.status == 404:
                return "absent"
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation could not be stopped"
            ) from None
        else:
            assert_claim()

        if not isinstance(custom_resource, dict):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation could not be stopped"
            )
        expected_runtime_instance_id = execution.runtime_instance_id
        spec = custom_resource.get("spec")
        metadata = custom_resource.get("metadata")
        runtime_spec = spec.get("runtime") if isinstance(spec, dict) else None
        if (
            not isinstance(expected_runtime_instance_id, str)
            or not expected_runtime_instance_id
            or not isinstance(runtime_spec, dict)
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation identity is incomplete"
            )
        if runtime_spec.get("instanceId") != expected_runtime_instance_id:
            return "replaced"
        resource_version = (
            metadata.get("resourceVersion") if isinstance(metadata, dict) else None
        )
        if not isinstance(resource_version, str) or not resource_version:
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation identity is incomplete"
            )

        assert_claim()
        try:
            api.patch_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=cr_namespace,
                plural=_WORKSPACE_PLURAL,
                name=resource_name,
                body={
                    "metadata": {"resourceVersion": resource_version},
                    "spec": {
                        "runtime": {"desiredState": "Stopped"},
                        "browser": {"desiredState": "Stopped"},
                        "canvas": {"desiredState": "Stopped"},
                    },
                },
            )
        except ApiException as exc:
            assert_claim()
            if exc.status == 404:
                return "absent"
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace generation could not be stopped"
            ) from None
        assert_claim()
        return "stopped"

    @staticmethod
    def _delete_workspace_custom_resource(
        *,
        api: client.CustomObjectsApi,
        namespace: str,
        name: str,
        assert_claim: Callable[[], None],
    ) -> None:
        """CAS-delete the domain Workspace CR by its Kubernetes identity."""

        assert_claim()
        try:
            custom_resource = api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=namespace,
                plural=_WORKSPACE_PLURAL,
                name=name,
            )
        except ApiException as exc:
            assert_claim()
            if exc.status == 404:
                return
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace deletion could not be confirmed"
            ) from None
        assert_claim()

        metadata = (
            custom_resource.get("metadata")
            if isinstance(custom_resource, dict)
            else None
        )
        resource_uid = metadata.get("uid") if isinstance(metadata, dict) else None
        resource_version = (
            metadata.get("resourceVersion") if isinstance(metadata, dict) else None
        )
        if (
            not isinstance(resource_uid, str)
            or not resource_uid
            or not isinstance(resource_version, str)
            or not resource_version
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace deletion identity is incomplete"
            )

        assert_claim()
        try:
            api.delete_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=namespace,
                plural=_WORKSPACE_PLURAL,
                name=name,
                body={
                    "apiVersion": "v1",
                    "kind": "DeleteOptions",
                    "preconditions": {
                        "uid": resource_uid,
                        "resourceVersion": resource_version,
                    },
                },
            )
        except ApiException as exc:
            assert_claim()
            if exc.status != 404:
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace deletion could not be confirmed"
                ) from None
        else:
            assert_claim()

    def _prove_generation_absent(
        self,
        identity: (
            WorkspaceCustomResourceExecutionIdentity
            | WorkspaceCustomResourceExecutionResult
        ),
        *,
        assert_claim: Callable[[], None],
        max_attempts: int = _TERMINATION_PROOF_MAX_ATTEMPTS,
        interval_seconds: float = _TERMINATION_PROOF_INTERVAL_SECONDS,
    ) -> None:
        """Fail closed until all three persisted old Pod UIDs are absent."""

        runtime_pod_uid = identity.runtime_pod_uid
        browser_pod_uid = identity.browser_pod_uid
        canvas_pod_uid = identity.canvas_pod_uid
        pod_uids = (runtime_pod_uid, browser_pod_uid, canvas_pod_uid)
        if all(pod_uid is None for pod_uid in pod_uids):
            self.prove_workspace_pods_absent(
                workspace_id=identity.workspace_id,
                assert_claim=assert_claim,
                max_attempts=max_attempts,
                interval_seconds=interval_seconds,
            )
            return
        if any(
            pod_uid is not None and (not isinstance(pod_uid, str) or not pod_uid)
            for pod_uid in pod_uids
        ):
            raise WorkspaceRuntimeTerminationUnconfirmedError(
                "Kubernetes workspace termination identities are incomplete"
            )

        api = self._get_core_v1_api()
        expected_uid_set = {
            pod_uid for pod_uid in pod_uids if isinstance(pod_uid, str) and pod_uid
        }
        for attempt in range(1, max_attempts + 1):
            assert_claim()
            try:
                pods = api.list_namespaced_pod(
                    namespace=self.settings.RUNTIME_K8S_NAMESPACE,
                    label_selector=(f"aileron.io/workspace-id={identity.workspace_id}"),
                )
            except ApiException:
                assert_claim()
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace termination could not be confirmed"
                ) from None
            assert_claim()
            items = getattr(pods, "items", None)
            if not isinstance(items, list):
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace termination could not be confirmed"
                )
            remaining_uids = {
                str(pod.metadata.uid)
                for pod in items
                if getattr(pod, "metadata", None) is not None
                and getattr(pod.metadata, "uid", None) is not None
            }
            if expected_uid_set.isdisjoint(remaining_uids):
                return
            if attempt < max_attempts:
                time.sleep(interval_seconds)
        raise WorkspaceRuntimeTerminationUnconfirmedError(
            "Kubernetes workspace termination could not be confirmed"
        )

    def prove_workspace_pods_absent(
        self,
        *,
        workspace_id: str,
        assert_claim: Callable[[], None],
        max_attempts: int = _TERMINATION_PROOF_MAX_ATTEMPTS,
        interval_seconds: float = _TERMINATION_PROOF_INTERVAL_SECONDS,
    ) -> None:
        """Prove a stopped Workspace has no managed Pods while retaining its CR."""

        core_api = self._get_core_v1_api()
        namespace = self.settings.RUNTIME_K8S_NAMESPACE
        for attempt in range(1, max_attempts + 1):
            assert_claim()
            try:
                pods = core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"aileron.io/workspace-id={workspace_id}",
                )
            except ApiException:
                assert_claim()
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace termination could not be confirmed"
                ) from None
            assert_claim()
            items = getattr(pods, "items", None)
            if not isinstance(items, list):
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace termination could not be confirmed"
                )
            if not items:
                return
            if attempt < max_attempts:
                time.sleep(interval_seconds)
        raise WorkspaceRuntimeTerminationUnconfirmedError(
            "Kubernetes workspace termination could not be confirmed"
        )

    def prove_workspace_absent(
        self,
        *,
        workspace_id: str,
        assert_claim: Callable[[], None],
        max_attempts: int = _TERMINATION_PROOF_MAX_ATTEMPTS,
        interval_seconds: float = _TERMINATION_PROOF_INTERVAL_SECONDS,
    ) -> None:
        """Prove the Workspace CR finalizer completed and all managed Pods are gone."""

        custom_api = self._get_custom_objects_api()
        core_api = self._get_core_v1_api()
        namespace = self.settings.RUNTIME_K8S_NAMESPACE
        for attempt in range(1, max_attempts + 1):
            assert_claim()
            try:
                custom_api.get_namespaced_custom_object(
                    group=_WORKSPACE_GROUP,
                    version=_WORKSPACE_VERSION,
                    namespace=namespace,
                    plural=_WORKSPACE_PLURAL,
                    name=f"workspace-{workspace_id}",
                )
            except ApiException as exc:
                assert_claim()
                if exc.status != 404:
                    raise WorkspaceRuntimeTerminationUnconfirmedError(
                        "Kubernetes workspace deletion could not be confirmed"
                    ) from None
                custom_resource_absent = True
            else:
                assert_claim()
                custom_resource_absent = False

            assert_claim()
            try:
                pods = core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"aileron.io/workspace-id={workspace_id}",
                )
            except ApiException:
                assert_claim()
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace deletion could not be confirmed"
                ) from None
            assert_claim()
            items = getattr(pods, "items", None)
            if not isinstance(items, list):
                raise WorkspaceRuntimeTerminationUnconfirmedError(
                    "Kubernetes workspace deletion could not be confirmed"
                )
            if custom_resource_absent and not items:
                return
            if attempt < max_attempts:
                time.sleep(interval_seconds)
        raise WorkspaceRuntimeTerminationUnconfirmedError(
            "Kubernetes workspace deletion could not be confirmed"
        )

    def fetch_workspace_status_snapshot(
        self,
        workspace_id: str,
    ) -> WorkspaceCustomResourceStatusSnapshot | None:
        """Read one Workspace CR without opening a database transaction."""

        resource_name = f"workspace-{workspace_id}"
        namespace = self.settings.RUNTIME_K8S_NAMESPACE
        api = self._get_custom_objects_api()
        try:
            custom_resource = api.get_namespaced_custom_object(
                group=_WORKSPACE_GROUP,
                version=_WORKSPACE_VERSION,
                namespace=namespace,
                plural=_WORKSPACE_PLURAL,
                name=resource_name,
                _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
            )
        except ApiException as exc:
            if exc.status == 404:
                logger.info(
                    "Workspace CR %s/%s does not exist yet, skip status reconciliation",
                    namespace,
                    resource_name,
                )
                return None
            raise
        if not isinstance(custom_resource, dict):
            raise TypeError("Kubernetes Workspace status response must be an object")
        return WorkspaceCustomResourceStatusSnapshot(
            workspace_id=workspace_id,
            resource_name=resource_name,
            namespace=namespace,
            custom_resource=deepcopy(custom_resource),
        )

    def fetch_workspace_pod_uids(self, workspace_id: str) -> frozenset[str]:
        """Read currently observable Pod UIDs for one Workspace generation."""

        api = self._get_core_v1_api()
        pods = api.list_namespaced_pod(
            namespace=self.settings.RUNTIME_K8S_NAMESPACE,
            label_selector=f"aileron.io/workspace-id={workspace_id}",
            _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
        )
        items = getattr(pods, "items", None)
        if not isinstance(items, list):
            raise TypeError("Kubernetes Pod observation response must contain items")
        return frozenset(
            str(pod.metadata.uid)
            for pod in items
            if getattr(pod, "metadata", None) is not None
            and getattr(pod.metadata, "uid", None) is not None
        )

    def apply_workspace_status_snapshot(
        self,
        snapshot: WorkspaceCustomResourceStatusSnapshot,
    ) -> bool:
        """Apply a current CR snapshot through a short non-blocking transaction."""

        workspace_id = snapshot.workspace_id
        if not try_acquire_workspace_transaction_lock(self.db, workspace_id):
            self.db.rollback()
            logger.info(
                "Workspace status reconciliation skipped because lifecycle owns the lock",
                extra={"workspace_id": workspace_id},
            )
            return False
        current_workspace = self.db.get(
            db_models.Workspace,
            workspace_id,
            populate_existing=True,
            with_for_update=True,
        )
        if current_workspace is None or current_workspace.provisioner != "kubernetes":
            self.db.rollback()
            return False
        workspace = current_workspace

        metadata_name, cr_namespace = self._custom_resource_identity(workspace)
        if (
            snapshot.resource_name != metadata_name
            or snapshot.namespace != cr_namespace
        ):
            self.db.rollback()
            return False
        custom_resource = snapshot.custom_resource
        status = custom_resource.get("status") or {}
        spec = custom_resource.get("spec") or {}
        metadata = custom_resource.get("metadata") or {}
        firewall_status = status.get("firewall") or {}
        firewall_spec = spec.get("firewall") or {}
        firewall_observed_revision = firewall_status.get("observedRevision")
        firewall_phase = firewall_status.get("phase")
        annotations = metadata.get("annotations")
        firewall_delivery_id = (
            annotations.get("platform.aileron.io/firewall-delivery-id")
            if isinstance(annotations, dict)
            else None
        )
        firewall_status_delivery_id = firewall_status.get("targetDeliveryId")
        firewall_changed = False
        storage_changed = self.capacity.reconcile_operator_observation(
            workspace_id=workspace.id,
            observation=_storage_observation(status.get("storage")),
        )
        if (
            firewall_spec.get("revision") == workspace.firewall_revision
            and isinstance(firewall_delivery_id, str)
            and bool(firewall_delivery_id)
            and isinstance(firewall_status_delivery_id, str)
            and bool(firewall_status_delivery_id)
            and firewall_delivery_id == workspace.firewall_target_delivery_id
            and firewall_status_delivery_id == firewall_delivery_id
        ):
            if firewall_phase in {"Error", "Degraded"}:
                workspace.firewall_sync_status = "error"
                workspace.firewall_error_code = (
                    firewall_status.get("errorCode") or "FIREWALL_APPLY_FAILED"
                )
                firewall_changed = True
            elif (
                isinstance(firewall_observed_revision, int)
                and workspace.firewall_observed_revision
                <= firewall_observed_revision
                <= workspace.firewall_revision
            ):
                workspace.firewall_observed_revision = firewall_observed_revision
                firewall_changed = True
                if (
                    firewall_observed_revision == workspace.firewall_revision
                    and firewall_phase == "Applied"
                ):
                    workspace.firewall_sync_status = "applied"
                    workspace.firewall_error_code = None
        if not self._status_matches_current_execution(
            workspace,
            metadata=metadata,
            spec=spec,
            status=status,
        ):
            logger.info(
                "Workspace CR status does not match the current execution, skip synchronization",
                extra={"workspace_id": workspace.id},
            )
            if firewall_changed or storage_changed:
                workspace.updated_at = datetime.utcnow()
                self.db.commit()
            else:
                self.db.rollback()
            return False
        self._apply_internal_service_urls(workspace, namespace=cr_namespace)
        self._converge_undelivered_mount_runtime_revision(
            workspace,
            custom_resource=custom_resource,
        )
        components = status.get("components") or {}
        bootstrap_status = status.get("bootstrap") or {}
        bootstrap_observed_revision = bootstrap_status.get("observedRevision")
        if (
            isinstance(bootstrap_observed_revision, int)
            and 0 <= bootstrap_observed_revision <= workspace.bootstrap_revision
        ):
            workspace.bootstrap_observed_revision = bootstrap_observed_revision
        bootstrap_phase = bootstrap_status.get("phase")
        if isinstance(bootstrap_phase, str):
            workspace.bootstrap_status = bootstrap_phase.lower()
            workspace.bootstrap_error_code = bootstrap_status.get("errorCode")

        preserve_runtime_phase = self._preserve_runtime_phase(
            workspace,
            status=status,
            components=components,
        )
        if not preserve_runtime_phase:
            workspace.runtime_status = self._normalize_component_phase(
                status.get("phase"),
                fallback=workspace.runtime_status,
            )

        self._apply_component_status(
            workspace,
            component="runtime",
            component_status=components.get("runtime"),
            phase_attr="runtime_status",
            preserve_phase=preserve_runtime_phase,
        )
        self._apply_component_status(
            workspace,
            component="browser",
            component_status=components.get("browser"),
            phase_attr="browser_status",
            preserve_phase=(workspace.browser_status in _READ_SYNC_PROTECTED_STATUSES),
        )
        self._apply_browser_connectivity_status(
            workspace,
            status.get("browserConnectivity"),
        )
        self._apply_component_status(
            workspace,
            component="canvas",
            component_status=components.get("canvas"),
            phase_attr="canvas_status",
            preserve_phase=(workspace.canvas_status in _READ_SYNC_PROTECTED_STATUSES),
        )
        workspace.terminal_internal_url = self._url_with_port(
            workspace.runtime_internal_url,
            3004,
        )

        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def _converge_undelivered_mount_runtime_revision(
        self,
        workspace: db_models.Workspace,
        *,
        custom_resource: dict[str, object],
    ) -> None:
        """Discard an unowned Runtime claim that never reached the Workspace CR."""

        if (
            workspace.knowledge_base_mount_sync_status != "degraded"
            or workspace.runtime_desired_revision == workspace.runtime_observed_revision
            or self._has_live_runtime_state_owner(workspace)
            or self._has_active_mount_reconcile_job(workspace)
        ):
            return

        spec = custom_resource.get("spec")
        runtime_spec = spec.get("runtime") if isinstance(spec, dict) else None
        if not isinstance(runtime_spec, dict):
            return
        runtime_revision = runtime_spec.get("revision")
        mount_revision = runtime_spec.get("mountRevision")
        access_revision = runtime_spec.get("accessRevision")
        if (
            type(runtime_revision) is not int
            or runtime_revision != workspace.runtime_observed_revision
            or type(mount_revision) is not int
            or mount_revision != workspace.knowledge_base_mount_active_revision
            or mount_revision != workspace.knowledge_base_mount_observed_revision
            or type(access_revision) is not int
            or access_revision != workspace.runtime_access_revision
            or access_revision != workspace.runtime_access_observed_revision
            or runtime_spec.get("desiredState") != "Running"
            or not isinstance(workspace.runtime_instance_id, str)
            or not self._execution_plane_status_is_ready(
                custom_resource,
                runtime_instance_id=workspace.runtime_instance_id,
                runtime_revision=runtime_revision,
                mount_revision=mount_revision,
                access_revision=access_revision,
            )
        ):
            return

        workspace.runtime_desired_revision = runtime_revision
        logger.info(
            "Converged undelivered mount Runtime revision to the ready Workspace CR",
            extra={
                "workspace_id": workspace.id,
                "runtime_revision": runtime_revision,
            },
        )

    def _has_active_mount_reconcile_job(
        self,
        workspace: db_models.Workspace,
    ) -> bool:
        owner_id = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob.id)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation
                == KNOWLEDGE_BASE_MOUNT_RECONCILE,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
        )
        return owner_id is not None

    def _preserve_runtime_phase(
        self,
        workspace: db_models.Workspace,
        *,
        status: object,
        components: object,
    ) -> bool:
        """Let a live job own transients and heal an unowned Ready generation."""

        if workspace.runtime_status not in _READ_SYNC_PROTECTED_STATUSES:
            return False
        if workspace.runtime_status == "error":
            return True
        if self._has_live_runtime_state_owner(workspace):
            return True
        if not isinstance(status, dict) or status.get("phase") != "Running":
            return True
        runtime_status = (
            components.get("runtime") if isinstance(components, dict) else None
        )
        return not bool(
            isinstance(runtime_status, dict)
            and runtime_status.get("ready") is True
            and runtime_status.get("terminalReady") is True
        )

    def _has_live_runtime_state_owner(
        self,
        workspace: db_models.Workspace,
    ) -> bool:
        operations = _RUNTIME_STATE_OWNER_OPERATIONS.get(workspace.runtime_status)
        if not operations:
            return False
        now = datetime.now(timezone.utc)
        owner_id = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob.id)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                db_models.WorkspaceRuntimeJob.operation.in_(operations),
                or_(
                    db_models.WorkspaceRuntimeJob.status == "queued",
                    and_(
                        db_models.WorkspaceRuntimeJob.status == "running",
                        db_models.WorkspaceRuntimeJob.claim_expires_at.is_not(None),
                        db_models.WorkspaceRuntimeJob.claim_expires_at > now,
                    ),
                ),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
        )
        return owner_id is not None

    def _build_workspace_custom_resource(
        self,
        workspace: db_models.Workspace,
        *,
        runtime_instance_id: str | None = None,
        runtime_secret_name: str,
    ) -> dict:
        target_namespace = self.settings.RUNTIME_K8S_NAMESPACE
        cr_namespace = self.settings.RUNTIME_K8S_NAMESPACE
        metadata_name = f"workspace-{workspace.id}"
        desired_instance_id = runtime_instance_id or workspace.runtime_instance_id
        if not isinstance(desired_instance_id, str):
            raise ValueError("Runtime instance identifier is required")
        canonical_instance_id = str(UUID(desired_instance_id))
        if canonical_instance_id != desired_instance_id:
            raise ValueError("Runtime instance identifier must be canonical")
        if runtime_instance_id is not None:
            browser_instance_id = canonical_instance_id
            canvas_instance_id = canonical_instance_id
        else:
            browser_instance_id = workspace.browser_instance_id
            canvas_instance_id = workspace.canvas_instance_id
            if not isinstance(browser_instance_id, str):
                raise ValueError("Browser instance identifier is required")
            if not isinstance(canvas_instance_id, str):
                raise ValueError("Canvas instance identifier is required")
            canonical_browser_instance_id = str(UUID(browser_instance_id))
            canonical_canvas_instance_id = str(UUID(canvas_instance_id))
            if canonical_browser_instance_id != browser_instance_id:
                raise ValueError("Browser instance identifier must be canonical")
            if canonical_canvas_instance_id != canvas_instance_id:
                raise ValueError("Canvas instance identifier must be canonical")
        images = {
            "RUNTIME_IMAGE_REFERENCE_INVALID": self.settings.RUNTIME_K8S_IMAGE,
            "BROWSER_IMAGE_REFERENCE_INVALID": self.settings.RUNTIME_K8S_BROWSER_IMAGE,
            "CANVAS_IMAGE_REFERENCE_INVALID": self.settings.RUNTIME_K8S_CANVAS_IMAGE,
        }
        for error_code, image in images.items():
            if not _IMMUTABLE_IMAGE_REFERENCE_PATTERN.fullmatch(image):
                raise ValueError(error_code)
        firewall_delivery_id = workspace.firewall_target_delivery_id
        if not isinstance(firewall_delivery_id, str) or not firewall_delivery_id:
            raise ValueError("Firewall delivery identifier is required")
        storage = self.capacity.desired_storage_spec(workspace)

        return {
            "apiVersion": "platform.aileron.io/v1alpha1",
            "kind": "Workspace",
            "metadata": {
                "name": metadata_name,
                "namespace": cr_namespace,
                "annotations": {
                    "platform.aileron.io/firewall-delivery-id": (firewall_delivery_id),
                },
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
                "bootstrap": {"revision": workspace.bootstrap_revision},
                "runtime": {
                    "desiredState": workspace.runtime_desired_state.title(),
                    "instanceId": canonical_instance_id,
                    "revision": workspace.runtime_desired_revision,
                    "mountRevision": workspace.knowledge_base_mount_desired_revision,
                    "accessRevision": workspace.runtime_access_revision,
                    "image": self.settings.RUNTIME_K8S_IMAGE,
                    "resources": self._runtime_resources_spec(),
                    "assertion": {
                        "issuer": self.settings.RUNTIME_ASSERTION_ISSUER,
                        "publicKeySetSecretName": (
                            self.settings.RUNTIME_ASSERTION_PUBLIC_KEY_SET_SECRET_NAME
                        ),
                    },
                    "runtimeSecretName": runtime_secret_name,
                    **(
                        {
                            "databaseTrust": {
                                "secretName": self.settings.RUNTIME_DATABASE_CA_SECRET_NAME,
                                "secretKey": self.settings.RUNTIME_DATABASE_CA_SECRET_KEY,
                                "revision": self.settings.RUNTIME_DATABASE_CA_REVISION,
                            }
                        }
                        if self.settings.RUNTIME_DATABASE_CA_SECRET_NAME
                        else {}
                    ),
                },
                "canvas": {
                    "enabled": True,
                    "desiredState": workspace.canvas_desired_state.title(),
                    "instanceId": canvas_instance_id,
                    "revision": workspace.canvas_desired_revision,
                    "image": self.settings.RUNTIME_K8S_CANVAS_IMAGE,
                    "resources": self.settings.RUNTIME_K8S_CANVAS_RESOURCES,
                },
                "browser": {
                    "enabled": True,
                    "desiredState": workspace.browser_desired_state.title(),
                    "instanceId": browser_instance_id,
                    "revision": workspace.browser_desired_revision,
                    "image": self.settings.RUNTIME_K8S_BROWSER_IMAGE,
                    "resources": self.settings.RUNTIME_K8S_BROWSER_RESOURCES,
                    "credentialSecretName": (
                        f"workspace-browser-credential-{workspace.id}"
                        f"-r{workspace.browser_credential_revision}"
                    ),
                    "credentialRevision": workspace.browser_credential_revision,
                    "credentialKeyId": workspace.browser_credential_key_id,
                    "credentialAlgorithm": workspace.browser_credential_algorithm,
                },
                "knowledgeBases": self._knowledge_base_specs(workspace),
                "workspacePath": workspace.workspace_path,
                "worktreeSubdir": workspace.worktree_subdir,
                "envVars": workspace.env_vars or [],
                "firewall": {
                    "revision": workspace.firewall_revision,
                    "workspace": {
                        "egressMode": workspace.workspace_firewall_egress_mode,
                        "allowedDomains": workspace.workspace_firewall_allowed_domains
                        or [],
                    },
                    "browser": {
                        "egressMode": workspace.browser_firewall_egress_mode,
                        "allowedDomains": workspace.browser_firewall_allowed_domains
                        or [],
                    },
                },
                "storage": _storage_spec_payload(storage),
            },
        }

    def apply_storage_spec(
        self,
        workspace: db_models.Workspace,
        *,
        storage_spec: WorkspaceStorageDesiredState,
    ) -> None:
        """Patch only durable Workspace storage desired state."""

        metadata_name, cr_namespace = self._custom_resource_identity(workspace)
        api = self._get_custom_objects_api()
        current = api.get_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=cr_namespace,
            plural=_WORKSPACE_PLURAL,
            name=metadata_name,
            _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
        )
        metadata = current.get("metadata") or {}
        api.patch_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=cr_namespace,
            plural=_WORKSPACE_PLURAL,
            name=metadata_name,
            body={
                "metadata": {"resourceVersion": metadata.get("resourceVersion")},
                "spec": {"storage": _storage_spec_payload(storage_spec)},
            },
            _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
        )

    def apply_firewall_spec(
        self,
        workspace: db_models.Workspace,
        *,
        delivery_id: str,
    ) -> None:
        """Patch only firewall desired state without changing component revisions."""

        metadata_name, cr_namespace = self._custom_resource_identity(workspace)
        api = self._get_custom_objects_api()
        current = api.get_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=cr_namespace,
            plural=_WORKSPACE_PLURAL,
            name=metadata_name,
            _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
        )
        metadata = current.get("metadata") or {}
        body = {
            "metadata": {
                "resourceVersion": metadata.get("resourceVersion"),
                "annotations": {
                    "platform.aileron.io/firewall-delivery-id": delivery_id,
                },
            },
            "spec": {
                "firewall": {
                    "revision": workspace.firewall_revision,
                    "workspace": {
                        "egressMode": workspace.workspace_firewall_egress_mode,
                        "allowedDomains": workspace.workspace_firewall_allowed_domains
                        or [],
                    },
                    "browser": {
                        "egressMode": workspace.browser_firewall_egress_mode,
                        "allowedDomains": workspace.browser_firewall_allowed_domains
                        or [],
                    },
                }
            },
        }
        api.patch_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=cr_namespace,
            plural=_WORKSPACE_PLURAL,
            name=metadata_name,
            body=body,
            _request_timeout=self.settings.KUBERNETES_STATUS_REQUEST_TIMEOUT_SECONDS,
        )

    def _knowledge_base_specs(
        self, workspace: db_models.Workspace
    ) -> list[dict[str, str]]:
        snapshot = (
            workspace.knowledge_base_mount_candidate_snapshot
            if workspace.knowledge_base_mount_sync_status
            in {"preflighting", "applying", "compensating"}
            else workspace.knowledge_base_mount_active_snapshot
        )
        return sorted(
            [
                {
                    "kbId": entry["knowledgeBaseId"],
                    "alias": entry["mountAlias"],
                }
                for entry in canonical_mount_snapshot(snapshot)
            ],
            key=lambda item: (item["alias"], item["kbId"]),
        )

    def _runtime_resources_spec(self) -> dict:
        resources = self.settings.RUNTIME_K8S_RUNTIME_RESOURCES
        if resources is None:
            raise RuntimeError(
                "RUNTIME_K8S_RUNTIME_RESOURCES must be injected by deployment"
            )
        return resources

    def _custom_resource_identity(
        self, workspace: db_models.Workspace
    ) -> tuple[str, str]:
        return f"workspace-{workspace.id}", self.settings.RUNTIME_K8S_NAMESPACE

    def _normalize_component_phase(self, phase: str | None, *, fallback: str) -> str:
        if not phase:
            return fallback
        return _KUBERNETES_PHASE_TO_DB_STATUS.get(phase, fallback)

    @staticmethod
    def _status_matches_current_execution(
        workspace: db_models.Workspace,
        *,
        metadata: object,
        spec: object,
        status: object,
    ) -> bool:
        if (
            not isinstance(metadata, dict)
            or not isinstance(spec, dict)
            or not isinstance(status, dict)
        ):
            return False
        generation = metadata.get("generation")
        runtime_spec = spec.get("runtime")
        components = status.get("components")
        runtime_status = (
            components.get("runtime") if isinstance(components, dict) else None
        )
        return bool(
            isinstance(generation, int)
            and status.get("observedGeneration") == generation
            and isinstance(workspace.runtime_instance_id, str)
            and isinstance(runtime_spec, dict)
            and runtime_spec.get("instanceId") == workspace.runtime_instance_id
            and isinstance(runtime_status, dict)
            and runtime_status.get("observedRevision") == runtime_spec.get("revision")
        )

    def _apply_component_status(
        self,
        workspace: db_models.Workspace,
        *,
        component: str,
        component_status: dict | None,
        phase_attr: str,
        preserve_phase: bool = False,
    ) -> None:
        if not component_status:
            return

        observed_revision = component_status.get("observedRevision")
        desired_revision = getattr(workspace, f"{component}_desired_revision")
        if (
            isinstance(observed_revision, int)
            and 0 <= observed_revision <= desired_revision
        ):
            setattr(
                workspace,
                f"{component}_observed_revision",
                observed_revision,
            )
        if component == "browser":
            credential_revision = component_status.get("credentialObservedRevision")
            credential_key_id = component_status.get("credentialObservedKeyId")
            credential_algorithm = component_status.get("credentialObservedAlgorithm")
            if (
                isinstance(credential_revision, int)
                and 0 <= credential_revision <= workspace.browser_credential_revision
            ):
                workspace.browser_credential_observed_revision = credential_revision
                workspace.browser_credential_observed_key_id = (
                    credential_key_id
                    if isinstance(credential_key_id, str) and credential_key_id
                    else None
                )
                workspace.browser_credential_observed_algorithm = (
                    credential_algorithm
                    if credential_algorithm == "hkdf-sha256-v1"
                    else None
                )
        setattr(workspace, f"{component}_reason", component_status.get("reason"))
        setattr(
            workspace,
            f"{component}_error_code",
            component_status.get("errorCode"),
        )
        setattr(
            workspace,
            f"{component}_last_transition_at",
            datetime.utcnow(),
        )

        if not preserve_phase:
            setattr(
                workspace,
                phase_attr,
                self._normalize_component_phase(
                    component_status.get("phase"),
                    fallback=getattr(workspace, phase_attr),
                ),
            )

    @staticmethod
    def _apply_internal_service_urls(
        workspace: db_models.Workspace,
        *,
        namespace: str,
    ) -> None:
        runtime = workspace_service_identity("runtime", workspace.id, namespace)
        terminal = workspace_service_identity("terminal", workspace.id, namespace)
        browser = workspace_service_identity("browser", workspace.id, namespace)
        canvas = workspace_service_identity("canvas", workspace.id, namespace)
        workspace.runtime_internal_url = runtime.url
        workspace.runtime_internal_port = runtime.port
        workspace.terminal_internal_url = terminal.url
        workspace.browser_webrtc_internal_url = browser.url
        workspace.browser_webrtc_internal_port = browser.port
        workspace.canvas_internal_url = canvas.url
        workspace.canvas_internal_port = canvas.port

    @staticmethod
    def _apply_browser_connectivity_status(
        workspace: db_models.Workspace,
        connectivity_status: object,
    ) -> None:
        if not isinstance(connectivity_status, dict):
            WorkspaceCustomResourceService._reset_browser_connectivity_status(
                workspace,
                state="pending",
                reason="BrowserConnectivityPending",
                error_code=None,
            )
            return
        state = connectivity_status.get("state")
        admission = connectivity_status.get("admission")
        reason = _optional_status_string(connectivity_status.get("reason"))
        error_code = _optional_status_string(connectivity_status.get("errorCode"))
        backend_state = connectivity_status.get("backendState")
        frontend_state = connectivity_status.get("frontendState")
        connectivity_states = {
            "pending",
            "ready",
            "degraded",
            "not_ready",
            "unavailable",
        }
        valid_state = state in {
            "pending",
            "ready",
            "degraded",
            "not_ready",
            "unavailable",
        }
        valid_admission = admission == (
            "allowed" if state in {"ready", "degraded"} else "denied"
        )
        if (
            connectivity_status.get("contractVersion") != "browser-connectivity/v1"
            or not valid_state
            or not valid_admission
            or reason not in CONNECTIVITY_REASONS
            or (error_code is not None and error_code not in CONNECTIVITY_ERROR_CODES)
            or backend_state not in connectivity_states
            or frontend_state not in connectivity_states
        ):
            WorkspaceCustomResourceService._reset_browser_connectivity_status(
                workspace,
                state="unavailable",
                reason="BrowserConnectivityContractRejected",
                error_code="BROWSER_CONNECTIVITY_CONTRACT_REJECTED",
            )
            return
        accepted_at = _parse_status_datetime(connectivity_status.get("acceptedAt"))
        expires_at = _parse_status_datetime(connectivity_status.get("expiresAt"))
        workspace.browser_connectivity_contract_version = "browser-connectivity/v1"
        workspace.browser_connectivity_state = state
        workspace.browser_connectivity_admission = admission
        workspace.browser_connectivity_browser_generation = _optional_status_string(
            connectivity_status.get("observedBrowserGeneration")
        )
        workspace.browser_connectivity_profile_revision = _optional_status_string(
            connectivity_status.get("profileRevision")
        )
        workspace.browser_connectivity_credential_revision = _optional_status_string(
            connectivity_status.get("credentialRevision")
        )
        workspace.browser_connectivity_accepted_at = accepted_at
        workspace.browser_connectivity_expires_at = expires_at
        workspace.browser_connectivity_reason = reason
        workspace.browser_connectivity_error_code = error_code
        workspace.browser_connectivity_last_transition_at = _parse_status_datetime(
            connectivity_status.get("lastTransitionAt")
        )
        for prefix in ("backend", "frontend"):
            component_state = connectivity_status.get(f"{prefix}State")
            setattr(
                workspace,
                f"browser_connectivity_{prefix}_state",
                component_state,
            )
            setattr(
                workspace,
                f"browser_connectivity_{prefix}_accepted_at",
                _parse_status_datetime(connectivity_status.get(f"{prefix}AcceptedAt")),
            )
            setattr(
                workspace,
                f"browser_connectivity_{prefix}_expires_at",
                _parse_status_datetime(connectivity_status.get(f"{prefix}ExpiresAt")),
            )
            setattr(
                workspace,
                f"browser_connectivity_{prefix}_reason",
                _optional_status_string(connectivity_status.get(f"{prefix}Reason")),
            )
            setattr(
                workspace,
                f"browser_connectivity_{prefix}_error_code",
                _optional_status_string(connectivity_status.get(f"{prefix}ErrorCode")),
            )

    @staticmethod
    def _reset_browser_connectivity_status(
        workspace: db_models.Workspace,
        *,
        state: str,
        reason: str,
        error_code: str | None,
    ) -> None:
        projection_changed = (
            workspace.browser_connectivity_state != state
            or workspace.browser_connectivity_admission != "denied"
            or workspace.browser_connectivity_reason != reason
            or workspace.browser_connectivity_error_code != error_code
        )
        workspace.browser_connectivity_state = state
        workspace.browser_connectivity_contract_version = "browser-connectivity/v1"
        workspace.browser_connectivity_admission = "denied"
        workspace.browser_connectivity_browser_generation = None
        workspace.browser_connectivity_profile_revision = None
        workspace.browser_connectivity_credential_revision = None
        workspace.browser_connectivity_reason = reason
        workspace.browser_connectivity_error_code = error_code
        if (
            projection_changed
            or workspace.browser_connectivity_last_transition_at is None
        ):
            workspace.browser_connectivity_last_transition_at = datetime.now(
                timezone.utc
            )
        workspace.browser_connectivity_accepted_at = None
        workspace.browser_connectivity_expires_at = None
        workspace.browser_connectivity_backend_state = state
        workspace.browser_connectivity_backend_accepted_at = None
        workspace.browser_connectivity_backend_expires_at = None
        workspace.browser_connectivity_backend_reason = reason
        workspace.browser_connectivity_backend_error_code = error_code
        workspace.browser_connectivity_frontend_state = state
        workspace.browser_connectivity_frontend_accepted_at = None
        workspace.browser_connectivity_frontend_expires_at = None
        workspace.browser_connectivity_frontend_reason = reason
        workspace.browser_connectivity_frontend_error_code = error_code

    def _url_with_port(self, value: str | None, port: int) -> str | None:
        if not value:
            return None
        parsed = urlparse(value)
        if not parsed.hostname:
            return None
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        return parsed._replace(netloc=f"{host}:{port}").geturl()

    def _get_custom_objects_api(self) -> client.CustomObjectsApi:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        return client.CustomObjectsApi()

    def _get_core_v1_api(self) -> client.CoreV1Api:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        return client.CoreV1Api()

    def _upsert_runtime_secret(
        self,
        *,
        credential: RuntimeDatabaseCredential,
        runtime_control_token: str,
        setup_script: str,
    ) -> None:
        namespace = self.settings.RUNTIME_K8S_NAMESPACE
        api = self._get_core_v1_api()
        body = client.V1Secret(
            metadata=client.V1ObjectMeta(
                name=credential.secret_name,
                namespace=namespace,
                labels={
                    "app.kubernetes.io/part-of": "aileron",
                    "aileron.io/workspace-id": credential.workspace_id,
                    "aileron.io/runtime-instance-id": credential.runtime_instance_id,
                },
            ),
            string_data={
                "runtime-database-connection": credential.database_url,
                "runtime-control-token": runtime_control_token,
                "custom-setup.sh": setup_script,
            },
            type="Opaque",
        )
        try:
            api.create_namespaced_secret(namespace=namespace, body=body)
            return
        except ApiException as exc:
            if exc.status != 409:
                raise
        api.patch_namespaced_secret(
            name=credential.secret_name,
            namespace=namespace,
            body=body,
        )

    def _delete_runtime_secret(
        self,
        *,
        secret_name: str,
    ) -> None:
        namespace = self.settings.RUNTIME_K8S_NAMESPACE
        try:
            self._get_core_v1_api().delete_namespaced_secret(
                name=secret_name,
                namespace=namespace,
            )
        except ApiException as exc:
            if exc.status != 404:
                raise

    def _get_workspace_custom_resource(self, manifest: dict) -> dict:
        metadata = manifest["metadata"]
        api = self._get_custom_objects_api()
        custom_resource = api.get_namespaced_custom_object(
            group=_WORKSPACE_GROUP,
            version=_WORKSPACE_VERSION,
            namespace=metadata["namespace"],
            plural=_WORKSPACE_PLURAL,
            name=metadata["name"],
        )
        if not isinstance(custom_resource, dict):
            raise TypeError("Workspace custom resource response must be an object")
        return custom_resource

    def _execution_result(
        self,
        plan: WorkspaceCustomResourceExecutionPlan,
        custom_resource: dict,
    ) -> WorkspaceCustomResourceExecutionResult | None:
        status = custom_resource.get("status") or {}
        if not isinstance(status, dict):
            return None
        components = status.get("components") or {}
        if not isinstance(components, dict):
            return None
        runtime = components.get("runtime") or {}
        browser = components.get("browser") or {}
        canvas = components.get("canvas") or {}
        if not all(isinstance(value, dict) for value in (runtime, browser, canvas)):
            return None
        runtime_spec = plan.manifest.get("spec", {}).get("runtime", {})
        runtime_revision = runtime_spec.get("revision")
        if not isinstance(runtime_revision, int) or not (
            self._execution_plane_status_is_ready(
                custom_resource,
                runtime_instance_id=plan.runtime_instance_id,
                runtime_revision=runtime_revision,
                mount_revision=plan.mount_revision,
                access_revision=plan.access_revision,
            )
        ):
            return None

        runtime_pod_uid = runtime.get("podUid")
        browser_pod_uid = browser.get("podUid")
        canvas_pod_uid = canvas.get("podUid")
        if not isinstance(runtime_pod_uid, str) or not runtime_pod_uid:
            return None
        return WorkspaceCustomResourceExecutionResult(
            workspace_id=plan.workspace_id,
            target_namespace=self.settings.RUNTIME_K8S_NAMESPACE,
            runtime_instance_id=plan.runtime_instance_id,
            mount_revision=plan.mount_revision,
            access_revision=plan.access_revision,
            runtime_pod_uid=runtime_pod_uid,
            browser_pod_uid=browser_pod_uid,
            canvas_pod_uid=canvas_pod_uid,
            status=status,
        )

    @staticmethod
    def component_requires_running_workload(
        component: str,
        component_spec: object,
    ) -> bool:
        """Return whether a Workspace CR component must have a running workload."""

        if component == "runtime":
            return True
        return (
            isinstance(component_spec, dict)
            and component_spec.get("enabled") is True
            and component_spec.get("desiredState") != "Stopped"
        )

    @staticmethod
    def _execution_plane_status_is_ready(
        custom_resource: dict,
        *,
        runtime_instance_id: str,
        runtime_revision: int,
        mount_revision: int,
        access_revision: int,
    ) -> bool:
        """Require exact full-plane evidence before advancing observed state."""

        spec = custom_resource.get("spec")
        status = custom_resource.get("status")
        if not isinstance(spec, dict) or not isinstance(status, dict):
            return False
        runtime_spec = spec.get("runtime")
        components = status.get("components")
        if (
            status.get("phase") != "Running"
            or not isinstance(runtime_spec, dict)
            or not isinstance(components, dict)
            or runtime_spec.get("instanceId") != runtime_instance_id
            or runtime_spec.get("revision") != runtime_revision
            or runtime_spec.get("mountRevision") != mount_revision
            or runtime_spec.get("accessRevision") != access_revision
        ):
            return False

        runtime_status = components.get("runtime")
        if not (
            isinstance(runtime_status, dict)
            and runtime_status.get("observedInstanceId") == runtime_instance_id
            and runtime_status.get("observedRevision") == runtime_revision
            and runtime_status.get("mountObservedRevision") == mount_revision
            and runtime_status.get("accessObservedRevision") == access_revision
            and runtime_status.get("phase") == "Running"
            and runtime_status.get("ready") is True
            and runtime_status.get("terminalReady") is True
            and isinstance(runtime_status.get("podUid"), str)
            and bool(runtime_status["podUid"])
        ):
            return False

        for component in ("browser", "canvas"):
            component_spec = spec.get(component)
            if not WorkspaceCustomResourceService.component_requires_running_workload(
                component,
                component_spec,
            ):
                continue
            component_status = components.get(component)
            if not (
                isinstance(component_status, dict)
                and component_status.get("observedInstanceId")
                == component_spec.get("instanceId")
                and component_status.get("observedRevision")
                == component_spec.get("revision")
                and component_status.get("phase") == "Running"
                and component_status.get("ready") is True
                and isinstance(component_status.get("podUid"), str)
                and bool(component_status["podUid"])
            ):
                return False
        return True

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


__all__ = [
    "WorkspaceCustomResourceExecutionIdentity",
    "WorkspaceCustomResourceExecutionPlan",
    "WorkspaceCustomResourceExecutionResult",
    "WorkspaceCustomResourceNotReadyError",
    "WorkspaceCustomResourceService",
    "WorkspaceCustomResourceStatusSnapshot",
]
