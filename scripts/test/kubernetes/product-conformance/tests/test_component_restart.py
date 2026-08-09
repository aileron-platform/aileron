"""Unit tests for component-scoped restart invariants."""

from __future__ import annotations

import copy
import unittest

from product_conformance.component_restart import (
    assert_component_recreation,
    assert_component_restart,
)


def _snapshot() -> dict[str, object]:
    return {
        "runtimeInstanceId": "runtime-instance-1",
        "podUids": {
            "runtime": "runtime-pod-1",
            "browser": "browser-pod-1",
            "canvas": "canvas-pod-1",
        },
        "revisions": {
            component: {
                "dbDesired": 1,
                "dbObserved": 1,
                "crDesired": 1,
                "crObserved": 1,
            }
            for component in ("runtime", "browser", "canvas")
        },
    }


def _restarted(component: str) -> tuple[dict[str, object], dict[str, object]]:
    before = _snapshot()
    after = copy.deepcopy(before)
    after["podUids"][component] = f"{component}-pod-2"  # type: ignore[index]
    revisions = after["revisions"][component]  # type: ignore[index]
    for key in revisions:
        revisions[key] = 2
    if component == "runtime":
        after["runtimeInstanceId"] = "runtime-instance-2"
    return before, after


class ComponentRestartInvariantTest(unittest.TestCase):
    def test_runtime_pod_recreation_keeps_instance_and_revisions(self) -> None:
        before = _snapshot()
        after = copy.deepcopy(before)
        after["podUids"]["runtime"] = "runtime-pod-2"  # type: ignore[index]

        assert_component_recreation(before, after, "runtime")

    def test_pod_recreation_rejects_revision_change(self) -> None:
        before = _snapshot()
        after = copy.deepcopy(before)
        after["podUids"]["runtime"] = "runtime-pod-2"  # type: ignore[index]
        after["revisions"]["runtime"]["dbDesired"] = 2  # type: ignore[index]

        with self.assertRaisesRegex(AssertionError, "revisions changed"):
            assert_component_recreation(before, after, "runtime")

    def test_runtime_restart_changes_only_runtime(self) -> None:
        before, after = _restarted("runtime")

        assert_component_restart(before, after, "runtime")

    def test_browser_restart_changes_only_browser(self) -> None:
        before, after = _restarted("browser")

        assert_component_restart(before, after, "browser")

    def test_canvas_restart_changes_only_canvas(self) -> None:
        before, after = _restarted("canvas")

        assert_component_restart(before, after, "canvas")

    def test_restart_rejects_sibling_identity_change(self) -> None:
        before, after = _restarted("runtime")
        after["podUids"]["browser"] = "browser-pod-2"  # type: ignore[index]

        with self.assertRaisesRegex(AssertionError, "browser Pod identity"):
            assert_component_restart(before, after, "runtime")

    def test_restart_rejects_sibling_revision_change(self) -> None:
        before, after = _restarted("browser")
        revisions = after["revisions"]["canvas"]  # type: ignore[index]
        for key in revisions:
            revisions[key] = 2

        with self.assertRaisesRegex(AssertionError, "canvas revisions"):
            assert_component_restart(before, after, "browser")


if __name__ == "__main__":
    unittest.main()
