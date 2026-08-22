"""Workspace lifecycle and action-gate product conformance scenarios."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from kubernetes.client.rest import ApiException
from websockets.asyncio.client import ClientConnection, connect

from .api import require_status
from .cluster import WORKSPACE_LIFETIME_UID_KEYS
from .component_restart import (
    COMPONENT_OPERATIONS,
    COMPONENTS,
    component_snapshot,
    wait_component_recreation,
    wait_component_restart,
)
from .context import ProductContext
from .contract import Evidence

_POLL_SECONDS = 1.0
_LIFECYCLE_TIMEOUT_SECONDS = 600.0
_WEBSOCKET_TIMEOUT_SECONDS = 30.0
_ACTIONS = (
    "runtime_read",
    "runtime_write",
    "terminal",
    "agent",
    "automation",
    "browser_automation",
)


def _job_id(response: Any, operation: str) -> str:
    value = response.json().get("jobId")
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{operation} response has no durable job id")
    return value


def _workspace_error_code(response: Any) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        value = detail.get("errorCode")
    else:
        value = payload.get("errorCode") if isinstance(payload, dict) else None
    return value if isinstance(value, str) else None


async def _wait_for(
    read: Callable[[], Any],
    predicate: Callable[[Any], bool],
    *,
    description: str,
    timeout_seconds: float = _LIFECYCLE_TIMEOUT_SECONDS,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last_value: Any = None
    while time.monotonic() < deadline:
        try:
            last_value = read()
            if predicate(last_value):
                return last_value
        except Exception as exc:
            last_value = exc
        await asyncio.sleep(_POLL_SECONDS)
    raise AssertionError(
        f"Timed out waiting for {description}; last observed={last_value!r}"
    )


def _generation(context: ProductContext) -> dict[str, Any]:
    generation = context.cluster.get_generation(context.workspace_id)
    instance_id = generation.get("runtimeInstanceId")
    pod_uids = generation.get("podUids")
    if not isinstance(instance_id, str) or not instance_id:
        raise AssertionError("Ready generation has no runtime instance id")
    if not isinstance(pod_uids, dict) or set(pod_uids) != {
        "runtime",
        "browser",
        "canvas",
    }:
        raise AssertionError("Ready generation has an incomplete Pod UID set")
    if not all(isinstance(value, str) and value for value in pod_uids.values()):
        raise AssertionError("Ready generation has an empty Pod UID")
    if not all(
        isinstance(generation.get(key), str) and generation[key]
        for key in WORKSPACE_LIFETIME_UID_KEYS
    ):
        raise AssertionError("Ready generation has incomplete Workspace lifetime UIDs")
    return generation


def _assert_workspace_persistence(
    context: ProductContext,
    *,
    operation: str,
) -> dict[str, Any]:
    expected_uids = context.workspace_lifetime_uids
    if set(expected_uids) != set(WORKSPACE_LIFETIME_UID_KEYS):
        raise AssertionError("Workspace lifetime UID baseline is incomplete")
    generation = _generation(context)
    observed_uids = {key: generation[key] for key in WORKSPACE_LIFETIME_UID_KEYS}
    if observed_uids != expected_uids:
        raise AssertionError(
            f"{operation} replaced a Workspace lifetime resource: "
            f"expected={expected_uids!r}, observed={observed_uids!r}"
        )
    expected_markers = context.workspace_storage_markers
    observed_markers = context.cluster.read_workspace_storage_markers(
        context.workspace_id
    )
    if not expected_markers or observed_markers != expected_markers:
        raise AssertionError(
            f"{operation} did not preserve Workspace storage markers: "
            f"expected={expected_markers!r}, observed={observed_markers!r}"
        )
    return {
        "uids": observed_uids,
        "markers": observed_markers,
    }


async def _wait_new_generation(
    context: ProductContext,
    previous: dict[str, Any],
) -> dict[str, Any]:
    old_instance = previous["runtimeInstanceId"]
    old_uids = set(previous["podUids"].values())

    def ready() -> dict[str, Any] | None:
        try:
            context.cluster.wait_workspace_ready(
                context.workspace_id,
                timeout_seconds=2,
            )
            return _generation(context)
        except (AssertionError, ApiException):
            return None

    current = await _wait_for(
        ready,
        lambda value: bool(
            value
            and value["runtimeInstanceId"] != old_instance
            and set(value["podUids"].values()).isdisjoint(old_uids)
        ),
        description="a different complete Workspace generation",
    )
    if not context.cluster.pod_uids_absent(context.workspace_id, list(old_uids)):
        raise AssertionError("Old generation Pod UID absence proof failed")
    context.runtime_instance_id = current["runtimeInstanceId"]
    context.workspace_service_urls = context.cluster.workspace_urls(
        context.workspace_id
    )
    return current


async def _wait_execution_stopped(
    context: ProductContext,
    previous: dict[str, Any],
) -> dict[str, Any]:
    expected_uids = context.workspace_lifetime_uids
    result = await _wait_for(
        lambda: context.cluster.workspace_stopped_state(
            context.workspace_id,
            expected_runtime_instance_id=previous["runtimeInstanceId"],
            old_pod_uids=set(previous["podUids"].values()),
        ),
        lambda value: value["customResourceStopped"]
        and not value["podUids"]
        and value["oldPodUidsAbsent"]
        and {key: value.get(key) for key in WORKSPACE_LIFETIME_UID_KEYS}
        == expected_uids,
        description="stopped Workspace CR, retained PVCs, and no managed Pods",
    )
    return result


def _request_lifecycle(
    context: ProductContext,
    operation: str,
) -> tuple[Any, str]:
    path = {
        "workspace_start": "start",
        "workspace_stop": "stop",
    }[operation]
    response = context.request_owner(
        "POST",
        f"/workspaces/{context.workspace_id}/{path}",
    )
    require_status(response, 202, operation=operation)
    return response, _job_id(response, operation)


def _request_component_restart(
    context: ProductContext,
    component: str,
) -> tuple[Any, str]:
    operation = COMPONENT_OPERATIONS[component]
    response = context.request_owner(
        "POST",
        f"/workspaces/{context.workspace_id}/components/{component}/restart",
    )
    require_status(response, 202, operation=operation)
    return response, _job_id(response, operation)


def _request_full_rebuild(context: ProductContext) -> tuple[Any, str]:
    operation = "workspace full rebuild"
    response = context.request_owner(
        "POST",
        f"/workspaces/{context.workspace_id}/availability/actions/rebuild",
    )
    require_status(response, 202, operation=operation)
    return response, _job_id(response, operation)


async def start_stop_restart(context: ProductContext) -> list[Evidence]:
    """Prove Pod recreation, stop/start, and component restart preserve storage."""

    baseline = await component_snapshot(context)
    baseline_persistence = _assert_workspace_persistence(
        context,
        operation="initial persistence snapshot",
    )
    deleted_pod = context.cluster.delete_workspace_component_pod(
        context.workspace_id,
        "runtime",
    )
    recreated = await wait_component_recreation(context, "runtime", baseline)
    recreation_persistence = _assert_workspace_persistence(
        context,
        operation="Runtime Pod recreation",
    )

    _, stop_job_id = _request_lifecycle(context, "workspace_stop")
    stop_job = context.db.wait_job(stop_job_id, "succeeded")
    stopped_row = context.db.wait_workspace(
        context.workspace_id,
        lambda row: bool(
            row
            and row["runtime_status"] == "stopped"
            and row["runtime_instance_id"] is None
        ),
        description="Workspace persisted as stopped",
    )
    if stopped_row is None:
        raise AssertionError("Stopped Workspace row disappeared")
    stopped_state = await _wait_execution_stopped(context, recreated)

    _, start_job_id = _request_lifecycle(context, "workspace_start")
    start_job = context.db.wait_job(start_job_id, "succeeded")
    started = await _wait_for(
        lambda: context.cluster.wait_workspace_ready(
            context.workspace_id,
            timeout_seconds=2,
        ),
        lambda value: value is not None,
        description="Workspace start generation Ready",
    )
    del started
    start_generation = await component_snapshot(context)
    if start_generation["runtimeInstanceId"] == recreated["runtimeInstanceId"]:
        raise AssertionError("Workspace start reused the stopped Runtime instance")
    start_persistence = _assert_workspace_persistence(
        context,
        operation="Workspace stop/start",
    )

    restart_evidence: list[Evidence] = []
    previous = start_generation
    for component in COMPONENTS:
        _, restart_job_id = _request_component_restart(context, component)
        restart_job = context.db.wait_job(restart_job_id, "succeeded")
        restarted = await wait_component_restart(context, component, previous)
        persistence = _assert_workspace_persistence(
            context,
            operation=f"{component} restart",
        )
        restart_evidence.append(
            Evidence(
                kind="component-lifecycle",
                ref=f"workspace_runtime_jobs/{restart_job_id}",
                assertion=(
                    f"{component} restart changed only its revision and Pod identity"
                ),
                observed={
                    "job": restart_job,
                    "before": previous,
                    "after": restarted,
                    "persistence": persistence,
                },
            )
        )
        previous = restarted

    context.refresh_generation()

    return [
        Evidence(
            kind="pod-recreation",
            ref=f"pod/{deleted_pod['name']}",
            assertion=(
                "Runtime Pod recreation changed only its Pod UID and retained "
                "the Workspace CR, both PVCs, working tree, and Runtime HOME"
            ),
            observed={
                "deletedPod": deleted_pod,
                "before": baseline,
                "after": recreated,
                "baselinePersistence": baseline_persistence,
                "persistence": recreation_persistence,
            },
        ),
        Evidence(
            kind="lifecycle",
            ref=f"workspace_runtime_jobs/{stop_job_id}",
            assertion=(
                "stop retained the same Workspace CR and both PVCs without "
                "managed Pods"
            ),
            observed={
                "job": stop_job,
                "workspace": stopped_row,
                "clusterState": stopped_state,
            },
        ),
        Evidence(
            kind="lifecycle",
            ref=f"workspace_runtime_jobs/{start_job_id}",
            assertion=(
                "start created a new complete workload generation while "
                "retaining both persistent volume markers"
            ),
            observed={
                "job": start_job,
                "generation": start_generation,
                "persistence": start_persistence,
            },
        ),
        *restart_evidence,
    ]


async def error_recovery(context: ProductContext) -> list[Evidence]:
    """Prove a failed Runtime restart enters error and full rebuild recovers."""

    baseline = await component_snapshot(context)
    scale = context.cluster.scale_operator(0)
    restored = False
    try:
        response, failed_job_id = _request_component_restart(context, "runtime")
        del response
        failed_job = context.db.wait_job(
            failed_job_id,
            "failed",
            timeout_seconds=360,
        )
        error_row = context.db.wait_workspace(
            context.workspace_id,
            lambda row: bool(row and row["runtime_status"] == "error"),
            description="Workspace lifecycle error after Operator outage",
            timeout_seconds=360,
        )
        if error_row is None:
            raise AssertionError("Workspace error row disappeared")
        if not isinstance(failed_job.get("error_code"), str):
            raise AssertionError("Failed restart did not persist a stable error code")

        context.cluster.scale_operator(scale["previousReplicas"] or 1)
        restored = True
        _, recovery_job_id = _request_full_rebuild(context)
        recovery_job = context.db.wait_job(
            recovery_job_id,
            "succeeded",
            timeout_seconds=600,
        )
        recovered = await _wait_new_generation(
            context,
            baseline,
        )
        persistence = _assert_workspace_persistence(
            context,
            operation="Workspace full rebuild",
        )
        running_row = context.db.wait_workspace(
            context.workspace_id,
            lambda row: bool(
                row
                and row["runtime_status"] == "running"
                and row["runtime_instance_id"] == recovered["runtimeInstanceId"]
            ),
            description="Workspace recovered from lifecycle error",
        )
        if running_row is None:
            raise AssertionError("Recovered Workspace row disappeared")
    finally:
        if not restored:
            context.cluster.scale_operator(scale["previousReplicas"] or 1)

    return [
        Evidence(
            kind="failure-injection",
            ref=f"deployment/{scale['name']}",
            assertion="Operator outage made the restart job and Workspace fail closed",
            observed={"scale": scale, "job": failed_job, "workspace": error_row},
        ),
        Evidence(
            kind="full-rebuild",
            ref=f"workspace_runtime_jobs/{recovery_job_id}",
            assertion=(
                "full rebuild replaced every workload identity while retaining "
                "the Workspace CR, both PVCs, working tree, and Runtime HOME"
            ),
            observed={
                "job": recovery_job,
                "before": baseline,
                "after": recovered,
                "workspace": running_row,
                "persistence": persistence,
            },
        ),
    ]


async def stopped_workspace(context: ProductContext) -> list[Evidence]:
    """Prove stopped attachment mutations remain durable and start absorbs the latest."""

    baseline = _generation(context)
    _, stop_job_id = _request_lifecycle(context, "workspace_stop")
    stop_job = context.db.wait_job(stop_job_id, "succeeded")
    stopped_before = await _wait_execution_stopped(context, baseline)
    workspace_before = context.db.get_workspace(context.workspace_id)
    if workspace_before is None or workspace_before["runtime_status"] != "stopped":
        raise AssertionError("Workspace did not remain stopped before mount mutations")

    kb_id = context.knowledge_base_ids.get("primary")
    if not isinstance(kb_id, str) or not kb_id:
        raise AssertionError("Primary product knowledge base is unavailable")
    suffix = uuid4().hex[:8]
    initial_alias = f"stopped-{suffix}"
    final_alias = f"stopped-final-{suffix}"
    attach_correlation = str(uuid4())
    attach_response = context.request_owner(
        "POST",
        f"/workspaces/{context.workspace_id}/knowledge-bases",
        headers={"X-Correlation-ID": attach_correlation},
        json={"kbId": kb_id, "mountAlias": initial_alias},
    )
    require_status(attach_response, 202, operation="stopped KB attach")
    attachment_id = (attach_response.json().get("attachment") or {}).get("id")
    if not isinstance(attachment_id, str) or not attachment_id:
        raise AssertionError("Stopped KB attach returned no attachment id")

    alias_correlation = str(uuid4())
    alias_response = context.request_owner(
        "PATCH",
        f"/workspaces/{context.workspace_id}/knowledge-bases/{attachment_id}",
        headers={"X-Correlation-ID": alias_correlation},
        json={"mountAlias": final_alias},
    )
    require_status(alias_response, 202, operation="stopped KB alias update")

    attach_job = context.db.get_job_by_correlation(
        workspace_id=context.workspace_id,
        operation="knowledge_base_mount_reconcile",
        correlation_id=attach_correlation,
    )
    alias_job = context.db.get_job_by_correlation(
        workspace_id=context.workspace_id,
        operation="knowledge_base_mount_reconcile",
        correlation_id=alias_correlation,
    )
    if not attach_job or attach_job["status"] != "superseded":
        raise AssertionError(
            f"Stopped attach lineage is not superseded: {attach_job!r}"
        )
    if not alias_job or alias_job["status"] != "queued":
        raise AssertionError(f"Stopped alias lineage is not queued: {alias_job!r}")
    workspace_pending = context.db.get_workspace(context.workspace_id)
    if not workspace_pending:
        raise AssertionError("Stopped Workspace row disappeared")
    pending_candidate = workspace_pending["knowledge_base_mount_candidate_snapshot"]
    matching_candidates = [
        item
        for item in pending_candidate or []
        if isinstance(item, dict)
        and item.get("attachmentId") == attachment_id
        and item.get("knowledgeBaseId") == kb_id
        and item.get("mountAlias") == final_alias
    ]
    if (
        workspace_pending["runtime_status"] != "stopped"
        or workspace_pending["knowledge_base_mount_sync_status"] != "preflighting"
        or workspace_pending["knowledge_base_mount_desired_revision"]
        <= workspace_pending["knowledge_base_mount_observed_revision"]
        or len(matching_candidates) != 1
    ):
        raise AssertionError(
            f"Stopped desired mount state is not pending: {workspace_pending!r}"
        )
    stopped_pending = await _wait_execution_stopped(context, baseline)

    _, start_job_id = _request_lifecycle(context, "workspace_start")
    start_job = context.db.wait_job(start_job_id, "succeeded")
    applied_mount_job = context.db.wait_job(alias_job["id"], "succeeded")
    if applied_mount_job["lifecycle_job_id"] != start_job_id:
        raise AssertionError("Start did not absorb the latest stopped mount child")
    current = context.refresh_generation()
    mounts = context.cluster.cr_knowledge_bases(context.workspace_id)
    matching_mounts = [
        item
        for item in mounts
        if item.get("kbId") == kb_id and item.get("alias") == final_alias
    ]
    if len(matching_mounts) != 1:
        raise AssertionError(f"Latest stopped alias was not applied: {mounts!r}")
    workspace_ready = context.db.get_workspace(context.workspace_id)
    if not workspace_ready or not (
        workspace_ready["knowledge_base_mount_sync_status"] == "ready"
        and workspace_ready["knowledge_base_mount_active_revision"]
        == workspace_ready["knowledge_base_mount_desired_revision"]
        == workspace_ready["knowledge_base_mount_observed_revision"]
        and workspace_ready["knowledge_base_mount_active_snapshot"] == pending_candidate
        and workspace_ready["knowledge_base_mount_candidate_snapshot"] is None
        and workspace_ready["knowledge_base_mount_failed_snapshot"] is None
    ):
        raise AssertionError("Stopped mount aggregate did not converge on start")
    active_attachments = context.db.list_active_attachments(context.workspace_id)
    matching_attachments = [
        row
        for row in active_attachments
        if row["id"] == attachment_id
        and row["kb_id"] == kb_id
        and row["mount_alias"] == final_alias
    ]
    if len(matching_attachments) != 1:
        raise AssertionError(
            "Promoted mount snapshot has no matching last-known-good attachment row"
        )

    return [
        Evidence(
            kind="durable-intent",
            ref=f"workspace_runtime_jobs/{alias_job['id']}",
            assertion="stopped attach and alias produced superseded then queued lineage",
            observed={
                "stopJob": stop_job,
                "attachJob": attach_job,
                "aliasJob": alias_job,
                "workspace": workspace_pending,
                "stoppedBefore": stopped_before,
                "stoppedPending": stopped_pending,
            },
        ),
        Evidence(
            kind="lifecycle-barrier",
            ref=f"workspace_runtime_jobs/{start_job_id}",
            assertion="one start absorbed the latest alias and converged its revision",
            observed={
                "startJob": start_job,
                "mountJob": applied_mount_job,
                "generation": current,
                "mounts": mounts,
                "workspace": workspace_ready,
                "activeAttachment": matching_attachments[0],
            },
        ),
    ]


def _access_response(
    context: ProductContext,
    actor: str,
    action: str,
    runtime_instance_id: str,
) -> Any:
    return context.request_actor(
        actor,
        "POST",
        f"/workspaces/{context.workspace_id}/execution-grants",
        json={
            "runtimeInstanceId": runtime_instance_id,
            "audience": (
                "workspace-terminal" if action == "terminal" else "workspace-runtime"
            ),
            "actions": [action],
        },
    )


def _ws_url(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit(
        (
            scheme,
            parsed.netloc,
            parsed.path.rstrip("/") + "/" + path.lstrip("/"),
            "",
            "",
        )
    )


def _bearer_protocols(protocol: str, token: str) -> list[str]:
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).rstrip(b"=")
    return [protocol, f"bearer.{encoded.decode('ascii')}"]


async def _expect_available_websocket(
    opener: Callable[[], Awaitable[ClientConnection]],
) -> dict[str, Any]:
    connection = await opener()
    try:
        pong = await connection.ping()
        await asyncio.wait_for(pong, timeout=_WEBSOCKET_TIMEOUT_SECONDS)
        return {"accepted": True}
    finally:
        await connection.close()


async def _scale_manager(context: ProductContext, replicas: int) -> dict[str, int]:
    name = context.cluster.manager_deployment_name
    deployment = context.cluster.apps.read_namespaced_deployment(
        name,
        context.settings.namespace,
    )
    previous = deployment.spec.replicas or 0
    context.cluster.apps.patch_namespaced_deployment_scale(
        name,
        context.settings.namespace,
        {"spec": {"replicas": replicas}},
    )

    def state() -> dict[str, int]:
        current = context.cluster.apps.read_namespaced_deployment(
            name,
            context.settings.namespace,
        )
        return {
            "specReplicas": current.spec.replicas or 0,
            "replicas": current.status.replicas or 0,
            "readyReplicas": current.status.ready_replicas or 0,
            "availableReplicas": current.status.available_replicas or 0,
        }

    observed = await _wait_for(
        state,
        lambda item: item["specReplicas"] == replicas
        and (
            (replicas == 0 and item["replicas"] == 0 and item["readyReplicas"] == 0)
            or (
                replicas > 0
                and item["readyReplicas"] >= replicas
                and item["availableReplicas"] >= replicas
            )
        ),
        description=f"Manager replicas={replicas}",
        timeout_seconds=300,
    )
    return {"previousReplicas": previous, **observed}


async def action_gate(context: ProductContext) -> list[Evidence]:
    """Prove role/action policy, generation fencing, and Manager fail-closed behavior."""

    generation = await component_snapshot(context)
    context.runtime_instance_id = generation["runtimeInstanceId"]
    instance_id = generation["runtimeInstanceId"]
    matrix: dict[str, dict[str, int]] = {}
    for actor in ("owner", "editor", "reader"):
        matrix[actor] = {}
        for action in _ACTIONS:
            response = _access_response(context, actor, action, instance_id)
            matrix[actor][action] = response.status_code
            expected = 200 if actor != "reader" or action == "runtime_read" else 403
            require_status(
                response,
                expected,
                operation=f"{actor} {action} action gate",
            )
            if expected == 403 and _workspace_error_code(response) != (
                "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
            ):
                raise AssertionError(
                    f"Viewer {action} denial did not use the stable action code"
                )

    stale_instance = str(uuid4())
    stale_response = _access_response(
        context,
        "owner",
        "runtime_read",
        stale_instance,
    )
    require_status(stale_response, 423, operation="stale Runtime instance gate")
    if _workspace_error_code(stale_response) != "WORKSPACE_RUNTIME_INSTANCE_MISMATCH":
        raise AssertionError("Stale Runtime instance did not use the stable fence code")

    owner_token = context.execution_grant(
        "owner",
        audience="workspace-runtime",
        actions=["runtime_read", "runtime_write", "agent", "browser_automation"],
    )
    owner_terminal_token = context.execution_grant(
        "owner",
        audience="workspace-terminal",
        actions=["terminal"],
    )
    manager_scale = await _scale_manager(context, 0)
    restored = False
    runtime_url = context.workspace_service_urls["runtime"]
    terminal_url = context.workspace_service_urls["terminal"]
    try:
        thread = await _expect_available_websocket(
            lambda: connect(
                _ws_url(runtime_url, "/api/v1/threads/events"),
                subprotocols=_bearer_protocols("aileron-thread-v1", owner_token),
                origin=context.settings.platform_public_origin,
                open_timeout=_WEBSOCKET_TIMEOUT_SECONDS,
                ping_interval=None,
            ),
        )
        cdp = await _expect_available_websocket(
            lambda: connect(
                _ws_url(
                    runtime_url,
                    "/api/v1/client-browser-relay/cdp/manager-outage",
                ),
                subprotocols=_bearer_protocols(
                    "aileron-browser-cdp-v1",
                    owner_token,
                ),
                origin=context.settings.platform_public_origin,
                open_timeout=_WEBSOCKET_TIMEOUT_SECONDS,
                ping_interval=None,
            ),
        )
        terminal = await _expect_available_websocket(
            lambda: connect(
                _ws_url(
                    terminal_url,
                    f"/ws/terminal?workspace_id={context.workspace_id}",
                ),
                subprotocols=_bearer_protocols(
                    "aileron-terminal-v1",
                    owner_terminal_token,
                ),
                origin=context.settings.platform_public_origin,
                open_timeout=_WEBSOCKET_TIMEOUT_SECONDS,
                ping_interval=None,
            ),
        )
        await _scale_manager(context, manager_scale["previousReplicas"] or 1)
        restored = True
        manager_pod = context.cluster.wait_manager_pod(timeout_seconds=300)
        supervisor = context.cluster.wait_supervisor_processes(
            {
                "fastapi": "RUNNING",
                "celery-worker": "RUNNING",
                "celery-beat": "RUNNING",
            }
        )
    finally:
        if not restored:
            await _scale_manager(context, manager_scale["previousReplicas"] or 1)

    return [
        Evidence(
            kind="authorization-matrix",
            ref=f"workspaces/{context.workspace_id}/execution-grants",
            assertion="owner/editor have six actions and reader has runtime_read only",
            observed=matrix,
        ),
        Evidence(
            kind="generation-fence",
            ref=stale_instance,
            assertion="a canonical but stale Runtime instance is locked",
            observed={
                "status": stale_response.status_code,
                "errorCode": _workspace_error_code(stale_response),
            },
        ),
        Evidence(
            kind="control-plane-outage",
            ref=context.cluster.manager_deployment_name,
            assertion=(
                "Thread, CDP, and Terminal validate signed grants locally while "
                "Manager is unavailable"
            ),
            observed={
                "scale": manager_scale,
                "thread": thread,
                "cdp": cdp,
                "terminal": terminal,
                "restoredManagerPodUid": str(manager_pod.metadata.uid),
                "supervisor": supervisor,
            },
        ),
    ]


SCENARIOS = {
    "startStopRestart": start_stop_restart,
    "errorRecovery": error_recovery,
    "stoppedWorkspace": stopped_workspace,
    "actionGate": action_gate,
}


__all__ = [
    "SCENARIOS",
    "action_gate",
    "error_recovery",
    "start_stop_restart",
    "stopped_workspace",
]
