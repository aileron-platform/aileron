"""Product conformance scenarios for Runtime and browser realtime fencing."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from .component_restart import component_snapshot, wait_component_restart
from .contract import Evidence

_POLL_INTERVAL_SECONDS = float(os.getenv("PRODUCT_POLL_INTERVAL_SECONDS", "1"))
_SCENARIO_TIMEOUT_SECONDS = float(os.getenv("PRODUCT_SCENARIO_TIMEOUT_SECONDS", "300"))
_WEBSOCKET_OPEN_TIMEOUT_SECONDS = float(
    os.getenv("PRODUCT_WEBSOCKET_OPEN_TIMEOUT_SECONDS", "20")
)
_WEBSOCKET_CLOSE_TIMEOUT_SECONDS = float(
    os.getenv("PRODUCT_WEBSOCKET_CLOSE_TIMEOUT_SECONDS", "90")
)
_DRAIN_ACK_MESSAGE = "Workspace component drain acknowledged"
_DRAIN_FAILURE_MESSAGE = "Workspace component drain acknowledgement failed"


@dataclass
class _RealtimeState:
    latest_generation: dict[str, Any] | None = None
    removed_actor: str | None = None
    removed_actor_token: str | None = None
    old_pairing_assertion: str | None = None
    old_pairing_runtime_instance_id: str | None = None
    closed_surfaces: dict[str, dict[str, Any]] = field(default_factory=dict)


def _state(context: Any) -> _RealtimeState:
    current = getattr(context, "_product_realtime_state", None)
    if isinstance(current, _RealtimeState):
        return current
    current = _RealtimeState()
    setattr(context, "_product_realtime_state", current)
    return current


async def _invoke(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = function(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _workspace_id(context: Any) -> str:
    value = getattr(context, "workspace_id", None)
    if not isinstance(value, str) or not value:
        raise AssertionError("Product context has no workspace_id")
    return value


def _namespace(context: Any) -> str:
    for owner_name in ("settings", "config"):
        owner = getattr(context, owner_name, None)
        value = getattr(owner, "namespace", None)
        if isinstance(value, str) and value:
            return value
    value = getattr(context, "namespace", None)
    if isinstance(value, str) and value:
        return value
    raise AssertionError("Product context has no Kubernetes namespace")


def _runtime_grant(context: Any, actor: str) -> str:
    return context.execution_grant(
        actor,
        audience="workspace-runtime",
        actions=[
            "agent",
            "automation",
            "browser_automation",
            "runtime_read",
            "runtime_write",
            "workspace_settings",
        ],
    )


def _terminal_grant(context: Any, actor: str) -> str:
    return context.execution_grant(
        actor,
        audience="workspace-terminal",
        actions=["terminal"],
    )


def _service_url(context: Any, key: str) -> str:
    urls = getattr(context, "workspace_service_urls", None)
    value = urls.get(key) if isinstance(urls, dict) else None
    if not isinstance(value, str) or not value:
        raise AssertionError(f"Product context has no workspace service URL: {key}")
    return value.rstrip("/")


def _websocket_url(value: str, path: str = "") -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        raise AssertionError(f"Unsupported service URL scheme: {parsed.scheme}")
    scheme = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    normalized_path = parsed.path.rstrip("/")
    if path:
        normalized_path += "/" + path.lstrip("/")
    return urlunsplit((scheme, parsed.netloc, normalized_path or "/", parsed.query, ""))


def _bearer_protocols(protocol: str, token: str) -> list[str]:
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).rstrip(b"=")
    return [protocol, "bearer." + encoded.decode("ascii")]


async def _request_owner(context: Any, method: str, path: str, **kwargs: Any) -> Any:
    return await _invoke(context.request_owner, method, path, **kwargs)


def _expect_status(response: Any, expected_status: int) -> Any:
    status_code = getattr(response, "status_code", None)
    if status_code != expected_status:
        body = getattr(response, "text", "")
        raise AssertionError(
            f"Expected HTTP {expected_status}, received {status_code}: {body[:500]}"
        )
    return response


async def _issue_pairing_assertion(context: Any) -> dict[str, str]:
    workspace_id = _workspace_id(context)
    response = await _request_owner(
        context,
        "POST",
        f"/api/v1/workspaces/{workspace_id}/browser-extension-pairing-assertions",
    )
    _expect_status(response, 200)
    if response.headers.get("cache-control") != "no-store":
        raise AssertionError("Pairing assertion response is cacheable")
    payload = response.json()
    if set(payload) != {"assertion", "runtimeInstanceId"}:
        raise AssertionError("Pairing assertion response shape changed")
    if not all(isinstance(payload[key], str) and payload[key] for key in payload):
        raise AssertionError("Pairing assertion response is incomplete")
    return payload


async def _open_thread(context: Any, token: str) -> ClientConnection:
    uri = _websocket_url(
        _service_url(context, "runtime"),
        "/api/v1/threads/events",
    )
    connection = await connect(
        uri,
        subprotocols=_bearer_protocols("aileron-thread-v1", token),
        open_timeout=_WEBSOCKET_OPEN_TIMEOUT_SECONDS,
        close_timeout=5,
        ping_interval=None,
    )
    if connection.subprotocol != "aileron-thread-v1":
        await connection.close()
        raise AssertionError(
            "Thread WebSocket did not negotiate its canonical protocol"
        )
    return connection


async def _open_terminal(context: Any, token: str) -> ClientConnection:
    workspace_id = _workspace_id(context)
    uri = _websocket_url(
        _service_url(context, "terminal"),
        f"/ws/terminal?workspace_id={workspace_id}",
    )
    connection = await connect(
        uri,
        subprotocols=_bearer_protocols("aileron-terminal-v1", token),
        open_timeout=_WEBSOCKET_OPEN_TIMEOUT_SECONDS,
        close_timeout=5,
        ping_interval=None,
    )
    if connection.subprotocol != "aileron-terminal-v1":
        await connection.close()
        raise AssertionError(
            "Terminal WebSocket did not negotiate its canonical protocol"
        )
    raw_message = await asyncio.wait_for(
        connection.recv(), timeout=_WEBSOCKET_OPEN_TIMEOUT_SECONDS
    )
    message = json.loads(raw_message)
    if message.get("type") != "connected":
        await connection.close()
        raise AssertionError("Terminal WebSocket did not send its connected event")
    return connection


async def _open_extension(context: Any, assertion: str) -> ClientConnection:
    uri = _websocket_url(
        _service_url(context, "runtime"),
        "/api/v1/client-browser-relay/extension",
    )
    connection = await connect(
        uri,
        subprotocols=[
            "aileron-browser-extension",
            f"assertion.{assertion}",
        ],
        open_timeout=_WEBSOCKET_OPEN_TIMEOUT_SECONDS,
        close_timeout=5,
        ping_interval=None,
    )
    if connection.subprotocol != "aileron-browser-extension":
        await connection.close()
        raise AssertionError(
            "Extension WebSocket did not negotiate its canonical protocol"
        )
    return connection


async def _open_cdp(context: Any, token: str) -> ClientConnection:
    configured = _service_url(context, "browserCdp")
    if "/api/v1/client-browser-relay/cdp" in configured:
        uri = _websocket_url(configured)
    else:
        uri = _websocket_url(
            configured,
            "/api/v1/client-browser-relay/cdp/product-conformance",
        )
    return await connect(
        uri,
        additional_headers={"Authorization": f"Bearer {token}"},
        open_timeout=_WEBSOCKET_OPEN_TIMEOUT_SECONDS,
        close_timeout=5,
        ping_interval=None,
    )


async def _assert_live(connection: ClientConnection) -> None:
    pong = await connection.ping()
    await asyncio.wait_for(pong, timeout=5)


async def _wait_closed(connection: ClientConnection) -> dict[str, Any]:
    deadline = time.monotonic() + _WEBSOCKET_CLOSE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            await asyncio.wait_for(
                connection.recv(),
                timeout=min(5, max(0.1, deadline - time.monotonic())),
            )
        except ConnectionClosed as exc:
            return {
                "closed": True,
                "code": getattr(exc, "code", None),
                "reason": getattr(exc, "reason", ""),
            }
        except asyncio.TimeoutError:
            continue
    raise AssertionError("WebSocket remained open after execution-plane recycle")


async def _expect_websocket_rejected(
    opener: Callable[[], Awaitable[ClientConnection]],
    *,
    accepted_close_codes: set[int],
) -> dict[str, Any]:
    try:
        connection = await opener()
    except InvalidStatus as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code != 403:
            raise AssertionError(
                f"WebSocket rejection used unexpected HTTP status {status_code}"
            ) from exc
        return {"rejected": True, "handshakeStatus": status_code}

    try:
        result = await _wait_closed(connection)
    finally:
        await connection.close()
    if result["code"] not in accepted_close_codes:
        raise AssertionError(
            f"WebSocket rejection used unexpected close code {result['code']}"
        )
    result["rejected"] = True
    return result


async def _get_generation(context: Any) -> dict[str, Any]:
    return await component_snapshot(context)


async def _wait_new_generation(
    context: Any,
    previous: dict[str, Any],
) -> dict[str, Any]:
    current = await wait_component_restart(
        context,
        "runtime",
        previous,
        timeout_seconds=_SCENARIO_TIMEOUT_SECONDS,
        poll_seconds=_POLL_INTERVAL_SECONDS,
    )
    await _assert_pod_uids_absent(context, {previous["podUids"]["runtime"]})
    return current


async def _assert_pod_uids_absent(context: Any, pod_uids: set[str]) -> None:
    cluster = context.cluster
    helper = getattr(cluster, "pod_uids_absent", None)
    if callable(helper):
        result = await _invoke(helper, _workspace_id(context), sorted(pod_uids))
        if result is not True:
            raise AssertionError("Old generation Pod UID absence proof failed")
        return

    core = getattr(cluster, "core", None)
    if core is None:
        raise AssertionError("Cluster adapter cannot prove old Pod UID absence")
    pods = await _invoke(
        core.list_namespaced_pod,
        _namespace(context),
        label_selector=f"aileron.io/workspace-id={_workspace_id(context)}",
    )
    present = {
        str(item.metadata.uid)
        for item in pods.items
        if getattr(item.metadata, "uid", None)
    }
    overlap = present.intersection(pod_uids)
    if overlap:
        raise AssertionError(f"Old generation Pod UIDs still exist: {sorted(overlap)}")


async def _latest_job(context: Any, operation: str) -> dict[str, Any] | None:
    result = await _invoke(
        context.db.get_latest_job,
        _workspace_id(context),
        operation_type=operation,
    )
    if result is not None and not isinstance(result, dict):
        raise AssertionError(f"Latest {operation} job has an invalid shape")
    return result


async def _wait_specific_job_succeeded(
    context: Any,
    operation: str,
    job_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + _SCENARIO_TIMEOUT_SECONDS
    observed: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        observed = await _invoke(context.db.get_job, job_id)
        if observed is None:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            continue
        if not isinstance(observed, dict) or observed.get("operation") != operation:
            raise AssertionError(
                f"Job {job_id} does not match {operation}: {observed!r}"
            )
        status = observed.get("status")
        if status == "succeeded":
            return observed
        if status in {"failed", "superseded"}:
            raise AssertionError(
                f"{operation} job reached unexpected terminal status {status}: {observed}"
            )
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"{operation} job {job_id} did not succeed before timeout: {observed}"
    )


async def _wait_new_job_succeeded(
    context: Any,
    operation: str,
    previous_job_id: str | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + _SCENARIO_TIMEOUT_SECONDS
    latest: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        latest = await _latest_job(context, operation)
        if latest is None or latest.get("id") == previous_job_id:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            continue
        job_id = latest.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise AssertionError(f"New {operation} job has no id: {latest!r}")
        return await _wait_specific_job_succeeded(context, operation, job_id)
    raise AssertionError(
        f"No new {operation} job appeared after {previous_job_id!r}: {latest!r}"
    )


async def _manager_logs(context: Any) -> list[str]:
    helper = getattr(context.cluster, "manager_log_lines", None)
    if callable(helper):
        result = await _invoke(helper)
        return [str(line) for line in result]

    core = getattr(context.cluster, "core", None)
    if core is None:
        raise AssertionError("Cluster adapter cannot read Manager logs")
    pods = await _invoke(
        core.list_namespaced_pod,
        _namespace(context),
        label_selector="app.kubernetes.io/component=workspace-manager",
    )
    if len(pods.items) != 1:
        raise AssertionError(f"Expected one Manager Pod, found {len(pods.items)}")
    log_text = await _invoke(
        core.read_namespaced_pod_log,
        pods.items[0].metadata.name,
        _namespace(context),
        container="workspace-manager",
    )
    return str(log_text).splitlines()


def _drain_log_counts(lines: list[str], cursor: int) -> dict[str, int]:
    delta = lines[cursor:]
    return {
        "acknowledged": sum(_DRAIN_ACK_MESSAGE in line for line in delta),
        "failed": sum(_DRAIN_FAILURE_MESSAGE in line for line in delta),
    }


async def _wait_drain_log_count(
    context: Any,
    cursor: int,
    *,
    acknowledged: int,
    failed: int,
) -> tuple[list[str], dict[str, int]]:
    deadline = time.monotonic() + _SCENARIO_TIMEOUT_SECONDS
    latest_lines: list[str] = []
    latest_counts = {"acknowledged": 0, "failed": 0}
    while time.monotonic() < deadline:
        latest_lines = await _manager_logs(context)
        latest_counts = _drain_log_counts(latest_lines, cursor)
        if (
            latest_counts["acknowledged"] >= acknowledged
            and latest_counts["failed"] >= failed
        ):
            return latest_lines, latest_counts
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    raise AssertionError(
        "Manager drain acknowledgement evidence did not appear before timeout: "
        f"{latest_counts}"
    )


def _assert_exact_drain_counts(
    lines: list[str],
    cursor: int,
    *,
    acknowledged: int,
    failed: int,
) -> dict[str, int]:
    counts = _drain_log_counts(lines, cursor)
    expected = {"acknowledged": acknowledged, "failed": failed}
    if counts != expected:
        raise AssertionError(
            f"Unexpected Manager drain acknowledgement delta: {counts}, expected {expected}"
        )
    return counts


def _removable_actor(context: Any) -> tuple[str, str]:
    share_ids = getattr(context, "share_ids", None)
    if not isinstance(share_ids, dict):
        raise AssertionError("Product context has no workspace share IDs")
    for actor in ("editor", "reader", "collaborator"):
        share_id = share_ids.get(actor)
        if isinstance(share_id, str) and share_id:
            return actor, share_id
    raise AssertionError("Product context has no removable collaborator share")


async def _restart_runtime(context: Any) -> dict[str, Any]:
    response = await _request_owner(
        context,
        "POST",
        f"/api/v1/workspaces/{_workspace_id(context)}/components/runtime/restart",
    )
    _expect_status(response, 202)
    payload = response.json()
    job_id = payload.get("jobId") if isinstance(payload, dict) else None
    if not isinstance(job_id, str) or not job_id:
        raise AssertionError("Runtime restart response has no durable jobId")
    return await _wait_specific_job_succeeded(
        context,
        "runtime_restart",
        job_id,
    )


async def run_signed_drain(context: Any) -> list[Evidence]:
    """Prove a signed restart drains every realtime surface before replacement."""

    owner_token = _runtime_grant(context, "owner")
    terminal_token = _terminal_grant(context, "owner")
    previous = await _get_generation(context)
    pairing = await _issue_pairing_assertion(context)
    if pairing["runtimeInstanceId"] != previous["runtimeInstanceId"]:
        raise AssertionError("Pairing assertion was not bound to the ready generation")

    connections: dict[str, ClientConnection] = {}
    try:
        connections["thread"] = await _open_thread(context, owner_token)
        connections["terminal"] = await _open_terminal(context, terminal_token)
        connections["extension"] = await _open_extension(context, pairing["assertion"])
        connections["cdp"] = await _open_cdp(context, owner_token)
        await asyncio.gather(*(_assert_live(item) for item in connections.values()))

        log_before = await _manager_logs(context)
        job = await _restart_runtime(context)
        current = await _wait_new_generation(context, previous)
        closed = dict(
            zip(
                connections,
                await asyncio.gather(
                    *(_wait_closed(item) for item in connections.values())
                ),
                strict=True,
            )
        )
        log_after, _ = await _wait_drain_log_count(
            context,
            len(log_before),
            acknowledged=2,
            failed=0,
        )
        drain_counts = _assert_exact_drain_counts(
            log_after,
            len(log_before),
            acknowledged=2,
            failed=0,
        )
    finally:
        await asyncio.gather(
            *(item.close() for item in connections.values()),
            return_exceptions=True,
        )

    state = _state(context)
    state.latest_generation = current
    state.closed_surfaces = closed
    if hasattr(context, "runtime_instance_id"):
        context.runtime_instance_id = current["runtimeInstanceId"]

    return [
        Evidence(
            kind="websocket",
            ref="Runtime, Terminal, extension, and CDP sockets",
            assertion="all four realtime surfaces closed during signed drain",
            observed=closed,
        ),
        Evidence(
            kind="manager-log",
            ref=str(job.get("id", "runtime_restart")),
            assertion="Runtime and Terminal each acknowledged one drain request",
            observed=drain_counts,
        ),
        Evidence(
            kind="kubernetes",
            ref=_workspace_id(context),
            assertion=(
                "only the Runtime revision and identity changed while Browser and "
                "Canvas stayed stable"
            ),
            observed={"before": previous, "after": current},
        ),
    ]


async def run_forced_termination_proof(context: Any) -> list[Evidence]:
    """Prove a failed Terminal drain cannot preserve an old generation."""

    actor, share_id = _removable_actor(context)
    actor_token = _terminal_grant(context, actor)
    previous = await _get_generation(context)
    terminal = await _open_terminal(context, actor_token)
    await _assert_live(terminal)
    old_pairing = await _issue_pairing_assertion(context)
    log_before = await _manager_logs(context)
    service_snapshot: Any | None = None
    service_restored = False
    operator_previous_replicas: int | None = None
    operator_restored = False
    operator_pause: dict[str, Any] | None = None
    operator_restore: dict[str, Any] | None = None

    try:
        previous_replicas = await _invoke(context.cluster.operator_replicas)
        if (
            not isinstance(previous_replicas, int)
            or isinstance(previous_replicas, bool)
            or previous_replicas < 1
        ):
            raise AssertionError(
                "Workspace Operator pre-pause replica snapshot must be positive"
            )
        operator_previous_replicas = previous_replicas
        operator_pause = await _invoke(context.cluster.scale_operator, 0)
        if (
            not isinstance(operator_pause, dict)
            or operator_pause.get("previousReplicas") != operator_previous_replicas
            or operator_pause.get("replicas") != 0
        ):
            raise AssertionError(
                "Workspace Operator pause returned an invalid scale result"
            )
        service_snapshot = await _invoke(
            context.cluster.patch_terminal_target_port,
            _workspace_id(context),
            65534,
        )
        previous_access_job = await _latest_job(
            context,
            "workspace_access_recycle",
        )
        previous_access_job_id = (
            previous_access_job.get("id") if previous_access_job is not None else None
        )
        response = await _request_owner(
            context,
            "DELETE",
            f"/api/v1/workspaces/{_workspace_id(context)}/shares/{share_id}",
        )
        _expect_status(response, 204)

        log_after_failure, _ = await _wait_drain_log_count(
            context,
            len(log_before),
            acknowledged=1,
            failed=1,
        )
        _assert_exact_drain_counts(
            log_after_failure,
            len(log_before),
            acknowledged=1,
            failed=1,
        )
        await _invoke(context.cluster.restore_service, service_snapshot)
        service_restored = True
        operator_restore = await _invoke(
            context.cluster.scale_operator,
            operator_previous_replicas,
        )
        if (
            not isinstance(operator_restore, dict)
            or operator_restore.get("replicas") != operator_previous_replicas
        ):
            raise AssertionError(
                "Workspace Operator restore returned an invalid scale result"
            )
        operator_restored = True

        job = await _wait_new_job_succeeded(
            context,
            "workspace_access_recycle",
            previous_access_job_id,
        )
        current = await _wait_new_generation(context, previous)
        terminal_closed = await _wait_closed(terminal)
        log_after = await _manager_logs(context)
        if len(log_after) < len(log_after_failure):
            raise AssertionError("Manager log stream moved backwards during recycle")
        drain_counts = _assert_exact_drain_counts(
            log_after,
            len(log_before),
            acknowledged=1,
            failed=1,
        )
    finally:
        try:
            if service_snapshot is not None and not service_restored:
                await _invoke(context.cluster.restore_service, service_snapshot)
        finally:
            try:
                if operator_previous_replicas is not None and not operator_restored:
                    await _invoke(
                        context.cluster.scale_operator,
                        operator_previous_replicas,
                    )
            finally:
                await terminal.close()

    state = _state(context)
    state.latest_generation = current
    state.removed_actor = actor
    state.removed_actor_token = actor_token
    state.old_pairing_assertion = old_pairing["assertion"]
    state.old_pairing_runtime_instance_id = old_pairing["runtimeInstanceId"]
    state.closed_surfaces[f"{actor}-terminal"] = terminal_closed
    if hasattr(context, "runtime_instance_id"):
        context.runtime_instance_id = current["runtimeInstanceId"]

    return [
        Evidence(
            kind="manager-log",
            ref=str(job.get("id", "workspace_access_recycle")),
            assertion="Runtime drain succeeded once and Terminal drain failed once",
            observed=drain_counts,
        ),
        Evidence(
            kind="kubernetes",
            ref=_workspace_id(context),
            assertion=(
                "failed graceful drain changed only Runtime revision and identity"
            ),
            observed={"before": previous, "after": current},
        ),
        Evidence(
            kind="kubernetes",
            ref=str((operator_pause or {}).get("name", "workspace-operator")),
            assertion=(
                "Workspace Operator was temporarily paused only for deterministic "
                "Service failure injection and restored before recycle verification"
            ),
            observed={
                "pause": operator_pause,
                "restore": operator_restore,
                "serviceRestoredBeforeOperator": True,
            },
        ),
        Evidence(
            kind="websocket",
            ref=f"{actor} terminal socket",
            assertion="the old Terminal socket closed after forced termination",
            observed=terminal_closed,
        ),
    ]


async def run_old_connection_rejection(context: Any) -> list[Evidence]:
    """Prove revoked identities and old-generation assertions cannot reconnect."""

    state = _state(context)
    actor = state.removed_actor
    actor_token = state.removed_actor_token
    old_assertion = state.old_pairing_assertion
    old_instance = state.old_pairing_runtime_instance_id
    if not all(
        isinstance(value, str) and value
        for value in (actor, actor_token, old_assertion, old_instance)
    ):
        raise AssertionError(
            "forcedTerminationProof must run before oldConnectionRejection"
        )
    current = await _get_generation(context)
    if current["runtimeInstanceId"] == old_instance:
        raise AssertionError("Workspace did not leave the old Runtime generation")

    thread_rejection = await _expect_websocket_rejected(
        lambda: _open_thread(context, actor_token),
        accepted_close_codes={4403},
    )
    terminal_rejection = await _expect_websocket_rejected(
        lambda: _open_terminal(context, actor_token),
        accepted_close_codes={4403},
    )
    cdp_rejection = await _expect_websocket_rejected(
        lambda: _open_cdp(context, actor_token),
        accepted_close_codes={4403},
    )
    old_pairing_rejection = await _expect_websocket_rejected(
        lambda: _open_extension(context, old_assertion),
        accepted_close_codes={4409},
    )

    new_pairing = await _issue_pairing_assertion(context)
    if new_pairing["runtimeInstanceId"] != current["runtimeInstanceId"]:
        raise AssertionError(
            "New pairing assertion did not target the ready generation"
        )
    extension = await _open_extension(context, new_pairing["assertion"])
    try:
        await _assert_live(extension)
    finally:
        await extension.close()

    return [
        Evidence(
            kind="authorization",
            ref=f"revoked workspace actor {actor}",
            assertion="revoked JWT cannot open Thread, Terminal, or CDP sockets",
            observed={
                "thread": thread_rejection,
                "terminal": terminal_rejection,
                "cdp": cdp_rejection,
            },
        ),
        Evidence(
            kind="assertion",
            ref=old_instance,
            assertion="old-generation pairing assertion is rejected by the new Runtime",
            observed={
                "currentRuntimeInstanceId": current["runtimeInstanceId"],
                "rejection": old_pairing_rejection,
            },
        ),
        Evidence(
            kind="websocket",
            ref=current["runtimeInstanceId"],
            assertion="owner can connect with a fresh current-generation assertion",
            observed={"connected": True},
        ),
    ]


async def run_browser_pairing(context: Any) -> list[Evidence]:
    """Prove single-use and generation-bound browser extension pairing."""

    previous = await _get_generation(context)
    first = await _issue_pairing_assertion(context)
    extension = await _open_extension(context, first["assertion"])
    try:
        await _assert_live(extension)
    finally:
        await extension.close()

    replay_rejection = await _expect_websocket_rejected(
        lambda: _open_extension(context, first["assertion"]),
        accepted_close_codes={4401},
    )
    old_unconsumed = await _issue_pairing_assertion(context)

    job = await _restart_runtime(context)
    current = await _wait_new_generation(context, previous)
    old_generation_rejection = await _expect_websocket_rejected(
        lambda: _open_extension(context, old_unconsumed["assertion"]),
        accepted_close_codes={4409},
    )

    fresh = await _issue_pairing_assertion(context)
    if fresh["runtimeInstanceId"] != current["runtimeInstanceId"]:
        raise AssertionError(
            "Fresh pairing assertion targeted a stale Runtime instance"
        )
    fresh_extension = await _open_extension(context, fresh["assertion"])
    try:
        await _assert_live(fresh_extension)
    finally:
        await fresh_extension.close()

    _state(context).latest_generation = current
    if hasattr(context, "runtime_instance_id"):
        context.runtime_instance_id = current["runtimeInstanceId"]

    return [
        Evidence(
            kind="assertion",
            ref=first["runtimeInstanceId"],
            assertion="a consumed browser pairing assertion cannot be replayed",
            observed=replay_rejection,
        ),
        Evidence(
            kind="assertion",
            ref=old_unconsumed["runtimeInstanceId"],
            assertion="an unconsumed assertion is still rejected after generation recycle",
            observed=old_generation_rejection,
        ),
        Evidence(
            kind="websocket",
            ref=str(job.get("id", "runtime_restart")),
            assertion="a fresh assertion connects to the new ready generation",
            observed={"before": previous, "after": current, "connected": True},
        ),
    ]


SCENARIOS = {
    "signedDrain": run_signed_drain,
    "forcedTerminationProof": run_forced_termination_proof,
    "oldConnectionRejection": run_old_connection_rejection,
    "browserPairing": run_browser_pairing,
}


__all__ = [
    "SCENARIOS",
    "run_browser_pairing",
    "run_forced_termination_proof",
    "run_old_connection_rejection",
    "run_signed_drain",
]
