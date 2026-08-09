"""Lifecycle and durable-job product conformance scenarios."""

from __future__ import annotations

import re
from uuid import uuid4

from .api import require_status
from .cluster import WORKSPACE_LIFETIME_UID_KEYS
from .component_restart import component_snapshot, wait_component_restart
from .context import ProductContext
from .contract import Evidence

_OPERATOR_OUTAGE_JOB_TIMEOUT_SECONDS = 360


def _snapshot_contains_knowledge_base(snapshot: object, kb_id: str) -> bool:
    return isinstance(snapshot, list) and any(
        isinstance(item, dict) and item.get("knowledgeBaseId") == kb_id
        for item in snapshot
    )


def assert_visual_services_ready(context: ProductContext) -> dict[str, object]:
    """Prove the real Browser and Canvas processes serve their product endpoints."""

    urls = context.workspace_service_urls
    neko_response = context.http.get(f"{urls['browserNeko']}/health")
    require_status(neko_response, 200, operation="Browser Neko health")

    cdp_response = context.http.get(f"{urls['browser']}/json/version")
    require_status(cdp_response, 200, operation="Browser CDP version")
    cdp_version = cdp_response.json()
    websocket_url = cdp_version.get("webSocketDebuggerUrl")
    if not isinstance(websocket_url, str) or not websocket_url.startswith("ws://"):
        raise AssertionError(
            f"Browser CDP payload has no WebSocket debugger URL: {cdp_version!r}"
        )

    canvas_ready_response = context.http.get(f"{urls['canvasApi']}/ready")
    require_status(canvas_ready_response, 200, operation="Canvas readiness")
    canvas_ready = canvas_ready_response.json()
    if canvas_ready.get("status") != "ready" or not canvas_ready.get(
        "renderer_available"
    ):
        raise AssertionError(
            f"Canvas readiness payload is unexpected: {canvas_ready!r}"
        )

    canvas_response = context.http.get(f"{urls['canvas']}/")
    require_status(canvas_response, 200, operation="Canvas renderer")
    if not canvas_response.content:
        raise AssertionError("Canvas renderer returned an empty response")

    return {
        "browserNekoStatus": neko_response.status_code,
        "browserCdp": {
            "status": cdp_response.status_code,
            "webSocketDebuggerUrl": websocket_url,
        },
        "canvasReady": canvas_ready,
        "canvasRendererStatus": canvas_response.status_code,
    }


async def setup_manager_api_lifecycle(context: ProductContext) -> list[Evidence]:
    """Create real API resources and wait for a complete execution plane."""

    slug_suffix = re.sub(r"[^a-z0-9]+", "-", context.settings.run_id.lower()).strip("-")
    slug_suffix = slug_suffix[-24:] or "run"
    kb_response = context.request_owner(
        "POST",
        "/knowledge-bases",
        json={
            "name": f"Product Conformance {slug_suffix}",
            "slug": f"product-conformance-{slug_suffix}",
        },
    )
    require_status(kb_response, 201, operation="create product knowledge base")
    kb = kb_response.json()
    kb_id = kb.get("id")
    if not isinstance(kb_id, str) or not kb_id:
        raise AssertionError("Created knowledge base has no id")
    context.knowledge_base_ids["primary"] = kb_id

    workspace_response = context.request_owner(
        "POST",
        "/workspaces",
        json={
            "name": f"Product Conformance {slug_suffix}",
            "description": "Formal product conformance workspace",
            "runtime": "universal",
            "branch": "main",
            "agenticTools": ["claude-code"],
        },
    )
    require_status(workspace_response, 201, operation="create product workspace")
    workspace = workspace_response.json()
    workspace_id = workspace.get("id")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise AssertionError("Created workspace has no id")
    context.workspace_id = workspace_id
    storage = context.cluster.ensure_workspace_storage(workspace_id)

    runtime_job = workspace.get("runtimeJob") or {}
    start_job_id = runtime_job.get("id")
    if not isinstance(start_job_id, str) or not start_job_id:
        latest = context.db.get_latest_job(workspace_id, "workspace_start")
        start_job_id = latest.get("id") if latest else None
    if not isinstance(start_job_id, str) or not start_job_id:
        raise AssertionError("Workspace create did not persist a start job")
    context.lifecycle_start_job_id = start_job_id
    start_job = context.db.wait_job(start_job_id, "succeeded")
    workspace_row = context.db.wait_workspace(
        workspace_id,
        lambda row: bool(
            row and row["runtime_status"] == "running" and row["runtime_instance_id"]
        ),
        description="created workspace persisted as running",
    )
    if workspace_row is None:
        raise AssertionError("Created workspace disappeared before readiness")
    generation = context.refresh_generation()
    context.workspace_lifetime_uids = {
        key: generation[key] for key in WORKSPACE_LIFETIME_UID_KEYS
    }
    context.workspace_storage_markers = context.cluster.write_workspace_storage_markers(
        workspace_id
    )

    runtime_health_response = context.http.get(
        f"{context.workspace_service_urls['runtime']}/health"
    )
    require_status(runtime_health_response, 200, operation="Runtime health")
    runtime_health = runtime_health_response.json()
    if runtime_health.get("status") != "healthy":
        raise AssertionError(f"Runtime health is not healthy: {runtime_health!r}")
    terminal_summary = runtime_health.get("terminal_service") or {}
    if terminal_summary.get("status") != "ready":
        raise AssertionError(
            f"Runtime does not report Terminal ready: {runtime_health!r}"
        )

    terminal_health_response = context.http.get(
        context.workspace_service_urls["runtime"].replace(":3002", ":3004") + "/health"
    )
    require_status(terminal_health_response, 200, operation="Terminal health")
    terminal_health = terminal_health_response.json()
    if terminal_health != {"status": "healthy", "service": "terminal-service"}:
        raise AssertionError(
            f"Terminal health payload is unexpected: {terminal_health!r}"
        )

    visual_services = assert_visual_services_ready(context)

    runtime_contract = context.cluster.assert_workspace_runtime_contract(
        workspace_id,
        runtime_image=context.settings.runtime_image,
        browser_image=context.settings.browser_image,
        canvas_image=context.settings.canvas_image,
        manager_url=context.settings.manager_url,
        assertion_secret_name="runtime-assertion-public-jwks",
        knowledge_bases_pvc_name="product-knowledge-bases-pvc",
        image_pull_secret_name=context.settings.image_pull_secret_name,
    )
    shares = context.establish_workspace_shares()
    return [
        Evidence(
            kind="api",
            ref="POST /api/v1/knowledge-bases",
            assertion="real authenticated Manager API persisted a knowledge base",
            observed={"status": kb_response.status_code, "knowledgeBaseId": kb_id},
        ),
        Evidence(
            kind="api",
            ref="POST /api/v1/workspaces",
            assertion="real authenticated Manager API persisted a workspace and start job",
            observed={
                "status": workspace_response.status_code,
                "workspaceId": workspace_id,
                "jobId": start_job_id,
                "jobStatus": start_job["status"],
            },
        ),
        Evidence(
            kind="postgresql",
            ref=f"workspaces/{workspace_id}",
            assertion="workspace and lifecycle state converged in PostgreSQL",
            observed={
                "runtimeStatus": workspace_row["runtime_status"],
                "runtimeInstanceId": workspace_row["runtime_instance_id"],
                "provisioner": workspace_row["provisioner"],
            },
        ),
        Evidence(
            kind="kubernetes",
            ref=f"workspace-{workspace_id}",
            assertion=(
                "Workspace CR, both persistent PVCs, and all three product Pods "
                "are Ready"
            ),
            observed={
                "storage": storage,
                "generation": generation,
                "storageMarkers": context.workspace_storage_markers,
            },
        ),
        Evidence(
            kind="health",
            ref=f"workspace-runtime-{workspace_id}:3002,3004",
            assertion="formal Runtime and Terminal health endpoints are healthy",
            observed={"runtime": runtime_health, "terminal": terminal_health},
        ),
        Evidence(
            kind="visual-services-health",
            ref=f"workspace-browser-{workspace_id},workspace-canvas-{workspace_id}",
            assertion=(
                "formal Browser Neko and direct CDP endpoints plus Canvas readiness "
                "and renderer endpoints are serving"
            ),
            observed=visual_services,
        ),
        Evidence(
            kind="kubernetes-runtime-contract",
            ref=f"workspace-runtime-{workspace_id}",
            assertion=(
                "formal Manager CR values and the rolled-out manual Operator "
                "produced Ready Pods with exact images, service endpoints, and SecretKeyRefs"
            ),
            observed=runtime_contract,
        ),
        Evidence(
            kind="authorization",
            ref=f"workspaces/{workspace_id}/shares",
            assertion="real bundled OIDC adapter users were shared through Manager",
            observed=shares,
        ),
    ]


async def finalize_manager_api_lifecycle(
    context: ProductContext,
    setup_evidence: list[Evidence],
) -> list[Evidence]:
    """Delete through Manager and prove every persisted/cluster artifact absent."""

    if not context.workspace_id:
        raise AssertionError("No product workspace exists for lifecycle finalization")
    workspace_id = context.workspace_id
    response = context.request_owner("DELETE", f"/workspaces/{workspace_id}")
    require_status(response, 202, operation="delete product workspace")
    command = response.json()
    delete_job_id = command.get("jobId")
    if not isinstance(delete_job_id, str) or not delete_job_id:
        raise AssertionError("Workspace delete response has no job id")
    queued_delete = context.db.get_job(delete_job_id)
    if queued_delete is None or queued_delete["operation"] != "workspace_delete":
        raise AssertionError("Workspace delete job was not durably persisted")

    context.db.wait_workspace(
        workspace_id,
        lambda row: row is None,
        description="deleted workspace absent from PostgreSQL",
        timeout_seconds=600,
    )
    cluster_absence = context.cluster.wait_workspace_absent(
        workspace_id,
        expected_uids=context.workspace_lifetime_uids,
    )
    job_absent = context.db.get_job(delete_job_id) is None
    if not job_absent:
        raise AssertionError("Workspace delete job did not cascade with workspace")
    return [
        *setup_evidence,
        Evidence(
            kind="api",
            ref=f"DELETE /api/v1/workspaces/{workspace_id}",
            assertion="Manager accepted the final durable workspace deletion",
            observed={
                "status": response.status_code,
                "jobId": delete_job_id,
                "initialJobStatus": queued_delete["status"],
            },
        ),
        Evidence(
            kind="absence-proof",
            ref=f"workspace/{workspace_id}",
            assertion=(
                "DB row, lifecycle rows, Workspace CR, both PVCs, and managed "
                "Pods are absent"
            ),
            observed={
                "workspaceRowAbsent": True,
                "jobRowAbsent": job_absent,
                **cluster_absence,
            },
        ),
    ]


async def durable_jobs(context: ProductContext) -> list[Evidence]:
    """Prove a queued lifecycle command survives complete Manager Pod loss."""

    manager_deleted = False
    try:
        stopped_output = context.cluster.supervisor(
            "stop", "celery-worker", "celery-beat"
        )
        stopped = context.cluster.wait_supervisor_processes(
            {"celery-worker": "STOPPED", "celery-beat": "STOPPED"}
        )
        old_manager = context.cluster.manager_pod()
        old_uid = str(old_manager.metadata.uid)
        before = await component_snapshot(context)
        correlation_id = str(uuid4())
        response = context.request_owner(
            "POST",
            f"/workspaces/{context.workspace_id}/components/runtime/restart",
            headers={"X-Correlation-ID": correlation_id},
        )
        require_status(response, 202, operation="queue Runtime restart")
        response_job_id = response.json().get("jobId")
        if not isinstance(response_job_id, str) or not response_job_id:
            raise AssertionError("Runtime restart response has no job id")
        queued = context.db.get_job(response_job_id)
        if (
            queued is None
            or queued["status"] != "queued"
            or queued["operation"] != "runtime_restart"
            or queued["target_component"] != "runtime"
        ):
            raise AssertionError(f"Runtime restart was not durably queued: {queued!r}")

        deleted_uid = context.cluster.delete_manager_pod()
        manager_deleted = True
        if deleted_uid != old_uid:
            raise AssertionError("Deleted Manager Pod identity changed unexpectedly")
        new_manager = context.cluster.wait_manager_pod(different_uid=old_uid)
        new_uid = str(new_manager.metadata.uid)
        processes = context.cluster.wait_supervisor_processes(
            {
                "fastapi": "RUNNING",
                "celery-worker": "RUNNING",
                "celery-beat": "RUNNING",
            }
        )
    finally:
        if not manager_deleted:
            context.cluster.supervisor("start", "celery-worker", "celery-beat")
            context.cluster.wait_supervisor_processes(
                {"celery-worker": "RUNNING", "celery-beat": "RUNNING"}
            )
    completed = context.db.wait_job(response_job_id, "succeeded")
    operation_jobs = context.db.list_jobs(
        context.workspace_id,
        operation="runtime_restart",
    )
    active = [job for job in operation_jobs if job["status"] in {"queued", "running"}]
    matching_terminal = [
        job
        for job in operation_jobs
        if job["id"] == response_job_id
        and job["status"] in {"succeeded", "failed", "superseded"}
    ]
    if active or len(matching_terminal) != 1:
        raise AssertionError(
            "Durable restart produced duplicate active or terminal outcomes: "
            f"{operation_jobs!r}"
        )
    generation = await wait_component_restart(context, "runtime", before)
    context.runtime_instance_id = generation["runtimeInstanceId"]
    context.workspace_service_urls = context.cluster.workspace_urls(
        context.workspace_id
    )
    return [
        Evidence(
            kind="process-control",
            ref=f"pod/{old_manager.metadata.name}",
            assertion="Celery worker and Beat were both stopped before API mutation",
            observed={"command": stopped_output, "states": stopped},
        ),
        Evidence(
            kind="postgresql",
            ref=f"workspace_runtime_jobs/{response_job_id}",
            assertion="the exact queued job id survived Manager Pod deletion and succeeded",
            observed={
                "queued": queued,
                "completed": completed,
                "oldManagerPodUid": old_uid,
                "newManagerPodUid": new_uid,
                "supervisor": processes,
            },
        ),
        Evidence(
            kind="deduplication",
            ref="workspace_runtime_jobs/runtime_restart",
            assertion="one operation has no duplicate active or terminal outcome",
            observed={
                "jobIds": [job["id"] for job in operation_jobs],
                "activeCount": len(active),
                "matchingTerminalCount": len(matching_terminal),
                "generation": generation,
            },
        ),
    ]


async def rapid_consecutive_mutations(context: ProductContext) -> list[Evidence]:
    """Prove three queued mount intents retain lineage and only the last applies."""

    context.cluster.supervisor("stop", "celery-worker", "celery-beat")
    context.cluster.wait_supervisor_processes(
        {"celery-worker": "STOPPED", "celery-beat": "STOPPED"}
    )
    try:
        suffix = uuid4().hex[:10]
        kb_response = context.request_owner(
            "POST",
            "/knowledge-bases",
            json={"name": f"Rapid {suffix}", "slug": f"rapid-{suffix}"},
        )
        require_status(kb_response, 201, operation="create rapid mutation KB")
        kb_id = kb_response.json()["id"]
        context.knowledge_base_ids["rapid"] = kb_id

        correlations = [str(uuid4()) for _ in range(3)]
        attach_response = context.request_owner(
            "POST",
            f"/workspaces/{context.workspace_id}/knowledge-bases",
            json={"kbId": kb_id, "mountAlias": f"rapid-{suffix}"},
            headers={"X-Correlation-ID": correlations[0]},
        )
        require_status(attach_response, 202, operation="queue rapid KB attach")
        attachment_id = attach_response.json()["attachment"]["id"]
        alias_response = context.request_owner(
            "PATCH",
            f"/workspaces/{context.workspace_id}/knowledge-bases/{attachment_id}",
            json={"mountAlias": f"rapid-renamed-{suffix}"},
            headers={"X-Correlation-ID": correlations[1]},
        )
        require_status(alias_response, 202, operation="queue rapid KB alias update")
        detach_response = context.request_owner(
            "DELETE",
            f"/workspaces/{context.workspace_id}/knowledge-bases/{attachment_id}",
            headers={"X-Correlation-ID": correlations[2]},
        )
        require_status(detach_response, 202, operation="queue rapid KB detach")

        queued_rows = [
            context.db.get_job_by_correlation(
                workspace_id=context.workspace_id,
                operation="knowledge_base_mount_reconcile",
                correlation_id=correlation,
            )
            for correlation in correlations
        ]
        if any(row is None for row in queued_rows):
            raise AssertionError(
                f"Rapid mutation lineage is incomplete: {queued_rows!r}"
            )
        rows = [row for row in queued_rows if row is not None]
        statuses = [row["status"] for row in rows]
        revisions = [row["target_revision"] for row in rows]
        if statuses != ["superseded", "superseded", "queued"]:
            raise AssertionError(f"Unexpected rapid mutation statuses: {statuses!r}")
        if revisions != sorted(revisions) or len(set(revisions)) != 3:
            raise AssertionError(
                f"Rapid mutation revisions are not monotonic: {revisions!r}"
            )
    finally:
        context.cluster.supervisor("start", "celery-worker", "celery-beat")
        context.cluster.wait_supervisor_processes(
            {"celery-worker": "RUNNING", "celery-beat": "RUNNING"}
        )
    final_job = context.db.wait_job(rows[-1]["id"], "succeeded")
    workspace = context.db.wait_workspace(
        context.workspace_id,
        lambda row: bool(
            row
            and row["knowledge_base_mount_sync_status"] == "ready"
            and row["knowledge_base_mount_active_revision"]
            == row["knowledge_base_mount_desired_revision"]
            and row["knowledge_base_mount_desired_revision"]
            == row["knowledge_base_mount_observed_revision"]
            and row["knowledge_base_mount_candidate_snapshot"] is None
            and row["knowledge_base_mount_failed_snapshot"] is None
        ),
        description="rapid mutation final mount revision converged",
    )
    if workspace is None:
        raise AssertionError("Rapid mutation workspace disappeared")
    if _snapshot_contains_knowledge_base(
        workspace["knowledge_base_mount_active_snapshot"],
        kb_id,
    ):
        raise AssertionError("Detached rapid mutation KB remains in active snapshot")
    attachment_kb_ids = context.db.list_attachment_kb_ids(context.workspace_id)
    if kb_id in attachment_kb_ids:
        raise AssertionError("Detached rapid mutation KB still has an attachment row")
    generation = context.refresh_generation()
    cr_mounts = context.cluster.cr_knowledge_bases(context.workspace_id)
    if any(mount.get("kbId") == kb_id for mount in cr_mounts):
        raise AssertionError("Detached rapid mutation KB remains in Workspace CR")
    return [
        Evidence(
            kind="postgresql",
            ref="workspace_runtime_jobs/rapid-mutations",
            assertion="attach and alias intents are superseded while detach stays queued",
            observed={
                "correlationIds": correlations,
                "jobIds": [row["id"] for row in rows],
                "statuses": statuses,
                "targetRevisions": revisions,
            },
        ),
        Evidence(
            kind="convergence",
            ref=f"workspace-{context.workspace_id}",
            assertion="only the final detach desired state reached DB and Workspace CR",
            observed={
                "finalJob": final_job,
                "workspace": workspace,
                "attachmentKbIds": attachment_kb_ids,
                "crKnowledgeBases": cr_mounts,
                "generation": generation,
            },
        ),
    ]


async def reconcile_failure_retry(context: ProductContext) -> list[Evidence]:
    """Force a real Operator outage and prove immutable mount retry lineage."""

    suffix = uuid4().hex[:10]
    kb_response = context.request_owner(
        "POST",
        "/knowledge-bases",
        json={"name": f"Retry {suffix}", "slug": f"retry-{suffix}"},
    )
    require_status(kb_response, 201, operation="create retry KB")
    kb_id = kb_response.json()["id"]
    context.knowledge_base_ids["retry"] = kb_id
    seed_response = context.request_owner(
        "POST",
        f"/knowledge-bases/{kb_id}/files",
        data={
            "path": "/raw/operator-outage.md",
            "type": "file",
            "content": "Operator outage conformance fixture",
        },
    )
    require_status(seed_response, 200, operation="seed retry KB")

    scaled = context.cluster.scale_operator(0)
    restored = False
    try:
        mutation_correlation = str(uuid4())
        attach_response = context.request_owner(
            "POST",
            f"/workspaces/{context.workspace_id}/knowledge-bases",
            json={"kbId": kb_id, "mountAlias": f"retry-{suffix}"},
            headers={"X-Correlation-ID": mutation_correlation},
        )
        require_status(attach_response, 202, operation="queue failed mount reconcile")
        failed_job = context.db.wait_job_by_correlation(
            workspace_id=context.workspace_id,
            operation="knowledge_base_mount_reconcile",
            correlation_id=mutation_correlation,
            expected_status="failed",
            timeout_seconds=_OPERATOR_OUTAGE_JOB_TIMEOUT_SECONDS,
        )
        failed_workspace = context.db.wait_workspace(
            context.workspace_id,
            lambda row: bool(
                row
                and row["knowledge_base_mount_sync_status"] == "compensating"
                and row["knowledge_base_mount_error_code"]
                and _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_failed_snapshot"],
                    kb_id,
                )
                and not _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_active_snapshot"],
                    kb_id,
                )
                and not _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_candidate_snapshot"],
                    kb_id,
                )
            ),
            description="forced mount failure staged automatic compensation",
            timeout_seconds=300,
        )
        if failed_workspace is None:
            raise AssertionError("Failed mount workspace disappeared")
        compensation_job = context.db.get_latest_job(
            context.workspace_id,
            "knowledge_base_mount_reconcile",
        )
        if (
            compensation_job is None
            or compensation_job["id"] == failed_job["id"]
            or compensation_job["retry_of_job_id"] != failed_job["id"]
            or compensation_job["job_metadata"].get("mount_action") != "compensate"
        ):
            raise AssertionError(
                "Mount failure did not create an immutable compensation child"
            )

        context.cluster.scale_operator(scaled["previousReplicas"] or 1)
        restored = True
        compensation_job = context.db.wait_job(
            compensation_job["id"],
            "succeeded",
            timeout_seconds=600,
        )
        compensated_workspace = context.db.wait_workspace(
            context.workspace_id,
            lambda row: bool(
                row
                and row["knowledge_base_mount_sync_status"] == "degraded"
                and row["knowledge_base_mount_error_code"]
                and row["knowledge_base_mount_candidate_snapshot"] is None
                and _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_failed_snapshot"],
                    kb_id,
                )
                and not _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_active_snapshot"],
                    kb_id,
                )
                and row["knowledge_base_mount_active_revision"]
                == row["knowledge_base_mount_desired_revision"]
                and row["knowledge_base_mount_desired_revision"]
                == row["knowledge_base_mount_observed_revision"]
            ),
            description="automatic mount compensation restored last-known-good state",
        )
        if compensated_workspace is None:
            raise AssertionError("Compensated mount workspace disappeared")

        retry_correlation = str(uuid4())
        retry_response = context.request_owner(
            "POST",
            f"/workspaces/{context.workspace_id}/knowledge-base-mount-sync/retry",
            headers={"X-Correlation-ID": retry_correlation},
        )
        require_status(retry_response, 202, operation="retry failed mount reconcile")
        retry_job = context.db.wait_job_by_correlation(
            workspace_id=context.workspace_id,
            operation="knowledge_base_mount_reconcile",
            correlation_id=retry_correlation,
            expected_status="succeeded",
            timeout_seconds=600,
        )
        if retry_job["id"] == failed_job["id"]:
            raise AssertionError("Mount retry mutated the failed row in place")
        if retry_job["retry_of_job_id"] != failed_job["id"]:
            raise AssertionError("Mount retry does not reference the failed job")
        if retry_job["root_correlation_id"] != failed_job["root_correlation_id"]:
            raise AssertionError("Mount retry did not preserve root correlation")
        persisted_failed = context.db.get_job(failed_job["id"])
        if persisted_failed is None or persisted_failed["status"] != "failed":
            raise AssertionError("Failed mount row was not retained immutably")

        workspace = context.db.wait_workspace(
            context.workspace_id,
            lambda row: bool(
                row
                and row["knowledge_base_mount_sync_status"] == "ready"
                and row["knowledge_base_mount_active_revision"]
                == row["knowledge_base_mount_desired_revision"]
                and row["knowledge_base_mount_desired_revision"]
                == row["knowledge_base_mount_observed_revision"]
                and row["knowledge_base_mount_candidate_snapshot"] is None
                and row["knowledge_base_mount_failed_snapshot"] is None
                and _snapshot_contains_knowledge_base(
                    row["knowledge_base_mount_active_snapshot"],
                    kb_id,
                )
            ),
            description="retried mount revision converged",
        )
        if workspace is None:
            raise AssertionError("Retried mount workspace disappeared")
        active_attachment_kb_ids = context.db.list_attachment_kb_ids(
            context.workspace_id
        )
        if kb_id not in active_attachment_kb_ids:
            raise AssertionError("Retried KB has no last-known-good attachment row")
        generation = context.refresh_generation()
        return [
            Evidence(
                kind="failure-injection",
                ref=f"deployment/{scaled['name']}",
                assertion="Operator replicas zero caused a real mount job and workspace error",
                observed={
                    "scale": scaled,
                    "failedJob": failed_job,
                    "workspace": failed_workspace,
                    "seedStatus": seed_response.status_code,
                },
            ),
            Evidence(
                kind="compensation",
                ref=f"workspace_runtime_jobs/{compensation_job['id']}",
                assertion=(
                    "failed candidate created an immutable compensation child "
                    "that restored the last-known-good snapshot"
                ),
                observed={
                    "job": compensation_job,
                    "workspace": compensated_workspace,
                },
            ),
            Evidence(
                kind="api",
                ref=(
                    f"POST /api/v1/workspaces/{context.workspace_id}/"
                    "knowledge-base-mount-sync/retry"
                ),
                assertion="retry endpoint created a new immutable lineage row",
                observed={
                    "status": retry_response.status_code,
                    "failedJobId": failed_job["id"],
                    "retryJobId": retry_job["id"],
                    "retryOfJobId": retry_job["retry_of_job_id"],
                    "rootCorrelationId": retry_job["root_correlation_id"],
                },
            ),
            Evidence(
                kind="convergence",
                ref=f"workspace-{context.workspace_id}",
                assertion="retry reached equal desired and observed mount revisions",
                observed={
                    "workspace": workspace,
                    "activeAttachmentKbIds": active_attachment_kb_ids,
                    "generation": generation,
                },
            ),
        ]
    finally:
        if not restored:
            context.cluster.scale_operator(scaled["previousReplicas"] or 1)


SCENARIOS = {
    "durableJobs": durable_jobs,
    "rapidConsecutiveMutations": rapid_consecutive_mutations,
    "reconcileFailureRetry": reconcile_failure_retry,
}


__all__ = [
    "SCENARIOS",
    "durable_jobs",
    "finalize_manager_api_lifecycle",
    "rapid_consecutive_mutations",
    "reconcile_failure_retry",
    "setup_manager_api_lifecycle",
]
