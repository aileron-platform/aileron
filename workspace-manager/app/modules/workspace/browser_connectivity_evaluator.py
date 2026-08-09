"""Pure Browser connectivity projection evaluator for non-Kubernetes runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from app.modules.workspace.browser_connectivity_contract import (
    BROWSER_CONNECTIVITY_CONTRACT_VERSION,
    TURNPathEvidence,
    TURNPathEvidenceSnapshot,
    TURNReachabilityProfile,
    evidence_is_fresh,
)


@dataclass(frozen=True)
class BrowserConnectivityDecision:
    """Complete typed projection decision shared by DB writers and fixtures."""

    contract_version: str
    state: str
    admission: str
    profile_revision: str | None
    credential_revision: str | None
    accepted_at: datetime | None
    expires_at: datetime | None
    reason: str
    error_code: str | None
    backend_state: str
    backend_accepted_at: datetime | None
    backend_expires_at: datetime | None
    backend_reason: str | None
    backend_error_code: str | None
    frontend_state: str
    frontend_accepted_at: datetime | None
    frontend_expires_at: datetime | None
    frontend_reason: str | None
    frontend_error_code: str | None


def _earliest(*values: datetime | None) -> datetime | None:
    candidates = [value for value in values if value is not None]
    return min(candidates) if candidates else None


def _snapshot_matches_vantage(
    snapshot: TURNPathEvidenceSnapshot,
    vantage: str | None,
) -> bool:
    return (
        snapshot.contract_version == BROWSER_CONNECTIVITY_CONTRACT_VERSION
        and snapshot.latest_attempt.contract_version
        == BROWSER_CONNECTIVITY_CONTRACT_VERSION
        and (vantage is None or snapshot.latest_attempt.vantage_id == vantage)
    )


def _base_decision(
    *,
    state: str,
    profile_revision: str | None,
    credential_revision: str | None,
    reason: str,
    error_code: str | None,
    backend_state: str,
    backend_accepted_at: datetime | None = None,
    backend_expires_at: datetime | None = None,
    backend_reason: str | None = None,
    backend_error_code: str | None = None,
    frontend_state: str = "pending",
    frontend_accepted_at: datetime | None = None,
    frontend_expires_at: datetime | None = None,
    frontend_reason: str | None = None,
    frontend_error_code: str | None = None,
) -> BrowserConnectivityDecision:
    return BrowserConnectivityDecision(
        contract_version=BROWSER_CONNECTIVITY_CONTRACT_VERSION,
        state=state,
        admission="allowed" if state in {"ready", "degraded"} else "denied",
        profile_revision=profile_revision,
        credential_revision=credential_revision,
        accepted_at=_earliest(backend_accepted_at, frontend_accepted_at),
        expires_at=_earliest(backend_expires_at, frontend_expires_at),
        reason=reason,
        error_code=error_code,
        backend_state=backend_state,
        backend_accepted_at=backend_accepted_at,
        backend_expires_at=backend_expires_at,
        backend_reason=backend_reason,
        backend_error_code=backend_error_code,
        frontend_state=frontend_state,
        frontend_accepted_at=frontend_accepted_at,
        frontend_expires_at=frontend_expires_at,
        frontend_reason=frontend_reason,
        frontend_error_code=frontend_error_code,
    )


def evaluate_browser_connectivity(
    *,
    profile: TURNReachabilityProfile | None,
    credential_revision: str,
    backend: TURNPathEvidenceSnapshot | None,
    backend_error: str | None,
    frontend: Mapping[str, TURNPathEvidenceSnapshot | None],
    frontend_errors: Mapping[str, str | None],
    now: datetime,
) -> BrowserConnectivityDecision:
    """Evaluate current evidence without performing I/O or database writes."""

    if profile is None:
        return _base_decision(
            state="unavailable",
            profile_revision=None,
            credential_revision=None,
            reason="TURNProfileUnavailable",
            error_code="TURN_PROFILE_UNAVAILABLE",
            backend_state="unavailable",
            backend_reason="TURNProfileUnavailable",
            backend_error_code="TURN_PROFILE_UNAVAILABLE",
            frontend_state="unavailable",
            frontend_reason="TURNProfileUnavailable",
            frontend_error_code="TURN_PROFILE_UNAVAILABLE",
        )

    profile_revision = profile.revision
    credential_revision = credential_revision.strip()
    if not credential_revision:
        return _base_decision(
            state="unavailable",
            profile_revision=profile_revision,
            credential_revision=None,
            reason="TURNProfileUnavailable",
            error_code="TURN_PROFILE_UNAVAILABLE",
            backend_state="unavailable",
            backend_reason="TURNProfileUnavailable",
            backend_error_code="TURN_PROFILE_UNAVAILABLE",
            frontend_state="unavailable",
            frontend_reason="TURNProfileUnavailable",
            frontend_error_code="TURN_PROFILE_UNAVAILABLE",
        )

    if backend_error is not None:
        return _base_decision(
            state="unavailable",
            profile_revision=profile_revision,
            credential_revision=credential_revision,
            reason="BackendEvidenceUnavailable",
            error_code="BACKEND_EVIDENCE_UNAVAILABLE",
            backend_state="unavailable",
            backend_reason="BackendEvidenceUnavailable",
            backend_error_code="BACKEND_EVIDENCE_UNAVAILABLE",
        )

    if backend is None:
        return _base_decision(
            state="pending",
            profile_revision=profile_revision,
            credential_revision=credential_revision,
            reason="BrowserConnectivityPending",
            error_code=None,
            backend_state="pending",
        )

    backend_success = backend.last_success
    if (
        not _snapshot_matches_vantage(backend, None)
        or backend.latest_attempt.outcome != "success"
        or backend_success is None
        or not evidence_is_fresh(
            backend_success,
            profile_revision=profile_revision,
            credential_revision=credential_revision,
            now=now,
        )
    ):
        return _base_decision(
            state="not_ready",
            profile_revision=profile_revision,
            credential_revision=credential_revision,
            reason="BackendTURNPathNotReady",
            error_code="BACKEND_TURN_PATH_NOT_READY",
            backend_state="not_ready",
            backend_accepted_at=backend.latest_attempt.accepted_at,
            backend_expires_at=backend.latest_attempt.expires_at,
            backend_reason="BackendTURNPathNotReady",
            backend_error_code="BACKEND_TURN_PATH_NOT_READY",
        )

    backend_accepted_at = backend_success.accepted_at
    backend_expires_at = backend_success.expires_at
    required_vantages = profile.required_frontend_vantages
    frontend_successes: list[TURNPathEvidence] = []
    degraded = False
    missing_required_evidence = False
    for vantage in required_vantages:
        snapshot = frontend.get(vantage)
        if (
            snapshot is None
            or not _snapshot_matches_vantage(snapshot, vantage)
            or snapshot.last_success is None
            or not evidence_is_fresh(
                snapshot.last_success,
                profile_revision=profile_revision,
                credential_revision=credential_revision,
                now=now,
            )
        ):
            missing_required_evidence = True
            continue
        frontend_successes.append(snapshot.last_success)
        if (
            snapshot.latest_attempt.outcome != "success"
            or frontend_errors.get(vantage) is not None
        ):
            degraded = True

    frontend_accepted_at = _earliest(
        *(evidence.accepted_at for evidence in frontend_successes)
    )
    frontend_expires_at = _earliest(
        *(evidence.expires_at for evidence in frontend_successes)
    )
    if missing_required_evidence or degraded:
        frontend_state = "not_ready" if missing_required_evidence else "degraded"
        aggregate_state = frontend_state
        return _base_decision(
            state=aggregate_state,
            profile_revision=profile_revision,
            credential_revision=credential_revision,
            reason="FrontendTURNPathNotReady",
            error_code="FRONTEND_TURN_PATH_NOT_READY",
            backend_state="ready",
            backend_accepted_at=backend_accepted_at,
            backend_expires_at=backend_expires_at,
            backend_reason="BackendTURNPathReady",
            frontend_state=frontend_state,
            frontend_accepted_at=frontend_accepted_at,
            frontend_expires_at=frontend_expires_at,
            frontend_reason="FrontendTURNPathNotReady",
            frontend_error_code="FRONTEND_TURN_PATH_NOT_READY",
        )

    return _base_decision(
        state="ready",
        profile_revision=profile_revision,
        credential_revision=credential_revision,
        reason="BrowserConnectivityReady",
        error_code=None,
        backend_state="ready",
        backend_accepted_at=backend_accepted_at,
        backend_expires_at=backend_expires_at,
        backend_reason="BackendTURNPathReady",
        frontend_state="ready",
        frontend_accepted_at=frontend_accepted_at,
        frontend_expires_at=frontend_expires_at,
        frontend_reason="FrontendTURNPathReady",
    )


__all__ = [
    "BrowserConnectivityDecision",
    "evaluate_browser_connectivity",
]
