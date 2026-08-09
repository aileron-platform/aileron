import json
from datetime import datetime
from pathlib import Path

import pytest

from app.modules.workspace.browser_connectivity_contract import (
    TURNPathEvidenceSnapshot,
    TURNReachabilityProfile,
)
from app.modules.workspace.browser_connectivity_evaluator import (
    evaluate_browser_connectivity,
)

CASES_PATH = Path("/repo-root/contracts/browser-connectivity/evaluator-cases.json")
PROFILE_PATH = Path(
    "/repo-root/contracts/browser-connectivity/turn-reachability-profile.json"
)
CONTRACT = json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _snapshot(value: dict | None) -> TURNPathEvidenceSnapshot | None:
    return TURNPathEvidenceSnapshot.from_mapping(value) if value is not None else None


def _backend(case: dict) -> TURNPathEvidenceSnapshot | None:
    if "backendRef" not in case:
        return _snapshot(case.get("backend"))
    referenced = next(
        item for item in CONTRACT["cases"] if item["name"] == case["backendRef"]
    )
    return _snapshot(referenced["backend"])


@pytest.mark.parametrize("case", CONTRACT["cases"], ids=lambda case: case["name"])
def test_shared_evaluator_cases(case: dict) -> None:
    profile = TURNReachabilityProfile.from_file(PROFILE_PATH)
    decision = evaluate_browser_connectivity(
        profile=profile,
        credential_revision=CONTRACT["credentialRevision"],
        backend=_backend(case),
        backend_error=case.get("backendError"),
        frontend={
            vantage: _snapshot(snapshot)
            for vantage, snapshot in case.get("frontend", {}).items()
        },
        frontend_errors={},
        now=_timestamp(CONTRACT["now"]),
    )

    expected = case["expected"]
    assert decision.state == expected["state"]
    assert decision.admission == expected["admission"]
    assert decision.backend_state == expected["backendState"]
    assert decision.frontend_state == expected["frontendState"]
    assert decision.reason == expected["reason"]
    assert decision.error_code == expected["errorCode"]
