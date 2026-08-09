"""Component-scoped workspace restart conformance helpers."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable

COMPONENTS = ("runtime", "browser", "canvas")
COMPONENT_OPERATIONS = {
    "runtime": "runtime_restart",
    "browser": "browser_restart",
    "canvas": "canvas_restart",
}


async def _invoke(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = function(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def component_snapshot(context: Any) -> dict[str, Any]:
    """Read the CR identities and DB/CR component revision fences."""

    workspace_id = getattr(context, "workspace_id", None)
    if not isinstance(workspace_id, str) or not workspace_id:
        raise AssertionError("Product context has no workspace_id")
    generation = await _invoke(context.cluster.get_generation, workspace_id)
    workspace = await _invoke(context.db.get_workspace, workspace_id)
    if not isinstance(generation, dict) or not isinstance(workspace, dict):
        raise AssertionError("Component restart snapshot is incomplete")

    pod_uids = generation.get("podUids")
    cr_revisions = generation.get("componentRevisions")
    if not isinstance(pod_uids, dict) or set(pod_uids) != set(COMPONENTS):
        raise AssertionError("Component Pod UID snapshot is incomplete")
    if not isinstance(cr_revisions, dict) or set(cr_revisions) != set(COMPONENTS):
        raise AssertionError("Component CR revision snapshot is incomplete")

    revisions: dict[str, dict[str, int]] = {}
    for component in COMPONENTS:
        uid = pod_uids.get(component)
        cr_revision = cr_revisions.get(component)
        db_desired = workspace.get(f"{component}_desired_revision")
        db_observed = workspace.get(f"{component}_observed_revision")
        if not isinstance(uid, str) or not uid:
            raise AssertionError(f"{component} Pod UID is missing")
        if not isinstance(cr_revision, dict):
            raise AssertionError(f"{component} CR revisions are missing")
        values = {
            "dbDesired": db_desired,
            "dbObserved": db_observed,
            "crDesired": cr_revision.get("desired"),
            "crObserved": cr_revision.get("observed"),
        }
        if not all(isinstance(value, int) and value >= 1 for value in values.values()):
            raise AssertionError(
                f"{component} component revisions are invalid: {values!r}"
            )
        if len(set(values.values())) != 1:
            raise AssertionError(
                f"{component} component revisions are not converged: {values!r}"
            )
        revisions[component] = values

    runtime_instance_id = generation.get("runtimeInstanceId")
    if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
        raise AssertionError("Runtime instance identity is missing")
    return {
        "runtimeInstanceId": runtime_instance_id,
        "podUids": dict(pod_uids),
        "revisions": revisions,
    }


def assert_component_restart(
    before: dict[str, Any],
    after: dict[str, Any],
    component: str,
    *,
    revision_increment: int = 1,
) -> None:
    """Assert one component advanced while both sibling identities stayed stable."""

    if component not in COMPONENTS:
        raise AssertionError(f"Unsupported workspace component: {component}")
    if revision_increment < 1:
        raise AssertionError("Component revision increment must be positive")
    siblings = set(COMPONENTS) - {component}
    if after["podUids"][component] == before["podUids"][component]:
        raise AssertionError(f"{component} Pod identity did not change")
    for sibling in siblings:
        if after["podUids"][sibling] != before["podUids"][sibling]:
            raise AssertionError(f"{sibling} Pod identity changed unexpectedly")

    if component == "runtime":
        if after["runtimeInstanceId"] == before["runtimeInstanceId"]:
            raise AssertionError("Runtime instance identity did not change")
    elif after["runtimeInstanceId"] != before["runtimeInstanceId"]:
        raise AssertionError("Runtime instance identity changed unexpectedly")

    for name in COMPONENTS:
        before_revisions = before["revisions"][name]
        after_revisions = after["revisions"][name]
        expected = (
            before_revisions["dbDesired"] + revision_increment
            if name == component
            else before_revisions["dbDesired"]
        )
        if set(after_revisions.values()) != {expected}:
            raise AssertionError(
                f"{name} revisions changed unexpectedly: "
                f"before={before_revisions!r}, after={after_revisions!r}"
            )


def assert_component_recreation(
    before: dict[str, Any],
    after: dict[str, Any],
    component: str,
) -> None:
    """Assert controller recreation changes only one Pod identity."""

    if component not in COMPONENTS:
        raise AssertionError(f"Unsupported workspace component: {component}")
    if after["podUids"][component] == before["podUids"][component]:
        raise AssertionError(f"{component} Pod identity did not change")
    for sibling in set(COMPONENTS) - {component}:
        if after["podUids"][sibling] != before["podUids"][sibling]:
            raise AssertionError(f"{sibling} Pod identity changed unexpectedly")
    if after["runtimeInstanceId"] != before["runtimeInstanceId"]:
        raise AssertionError("Runtime instance identity changed unexpectedly")
    if after["revisions"] != before["revisions"]:
        raise AssertionError(
            "Component revisions changed during Pod recreation: "
            f"before={before['revisions']!r}, after={after['revisions']!r}"
        )


async def wait_component_recreation(
    context: Any,
    component: str,
    before: dict[str, Any],
    *,
    timeout_seconds: float = 600,
    poll_seconds: float = 1,
) -> dict[str, Any]:
    """Wait for controller-driven Pod recreation without a revision change."""

    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            after = await component_snapshot(context)
            assert_component_recreation(before, after, component)
            return after
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(poll_seconds)
    raise AssertionError(
        f"{component} Pod recreation did not converge before timeout: {last_error}"
    )


async def wait_component_restart(
    context: Any,
    component: str,
    before: dict[str, Any],
    *,
    timeout_seconds: float = 600,
    poll_seconds: float = 1,
    revision_increment: int = 1,
) -> dict[str, Any]:
    """Wait until the requested component revision and identity converge."""

    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            after = await component_snapshot(context)
            assert_component_restart(
                before,
                after,
                component,
                revision_increment=revision_increment,
            )
            return after
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(poll_seconds)
    raise AssertionError(
        f"{component} restart did not converge before timeout: {last_error}"
    )


__all__ = [
    "COMPONENT_OPERATIONS",
    "COMPONENTS",
    "assert_component_recreation",
    "assert_component_restart",
    "component_snapshot",
    "wait_component_recreation",
    "wait_component_restart",
]
