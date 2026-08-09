"""Evidence contract for product conformance capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

CAPABILITY_KEYS = (
    "managerApiLifecycle",
    "durableJobs",
    "rapidConsecutiveMutations",
    "reconcileFailureRetry",
    "startStopRestart",
    "errorRecovery",
    "stoppedWorkspace",
    "actionGate",
    "signedDrain",
    "forcedTerminationProof",
    "oldConnectionRejection",
    "browserPairing",
)


@dataclass(frozen=True)
class Evidence:
    kind: str
    ref: str
    assertion: str
    observed: Any


@dataclass
class CapabilityResult:
    passed: bool = False
    evidence: list[Evidence] = field(default_factory=list)
    failure: str | None = "scenario not executed"


class ConformanceReport:
    """Only records a pass after concrete evidence has been asserted."""

    def __init__(self, *, run_id: str, namespace: str) -> None:
        self.run_id = run_id
        self.namespace = namespace
        self.started_at = datetime.now(timezone.utc)
        self.capabilities = {key: CapabilityResult() for key in CAPABILITY_KEYS}

    def pass_capability(self, key: str, evidence: list[Evidence]) -> None:
        self._require_key(key)
        if not evidence:
            raise ValueError(f"{key} cannot pass without evidence")
        for item in evidence:
            if not isinstance(item, Evidence):
                raise TypeError(f"{key} evidence must use the Evidence contract")
            if (
                not item.kind.strip()
                or not item.ref.strip()
                or not item.assertion.strip()
            ):
                raise ValueError(f"{key} evidence metadata cannot be empty")
            if item.observed is None:
                raise ValueError(f"{key} evidence must include an observed value")
        self.capabilities[key] = CapabilityResult(
            passed=True,
            evidence=list(evidence),
            failure=None,
        )

    def fail_capability(
        self,
        key: str,
        failure: str,
        *,
        evidence: list[Evidence] | None = None,
    ) -> None:
        self._require_key(key)
        self.capabilities[key] = CapabilityResult(
            passed=False,
            evidence=list(evidence or []),
            failure=failure,
        )

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.capabilities.values())

    def to_dict(self) -> dict[str, Any]:
        finished_at = datetime.now(timezone.utc)
        return {
            "schemaVersion": 1,
            "runId": self.run_id,
            "namespace": self.namespace,
            "result": "passed" if self.passed else "failed",
            "startedAt": self.started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "capabilities": {
                key: _json_safe(asdict(result))
                for key, result in self.capabilities.items()
            },
        }

    def _require_key(self, key: str) -> None:
        if key not in self.capabilities:
            raise KeyError(f"Unknown capability: {key}")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    raise TypeError(f"Evidence value is not JSON serializable: {type(value).__name__}")
