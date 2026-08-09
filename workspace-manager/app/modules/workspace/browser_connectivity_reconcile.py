"""Docker Browser connectivity evidence reconciliation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.db import models as db_models
from app.db.database import SessionLocal
from app.modules.workspace.advisory_lock import (
    try_acquire_workspace_transaction_lock,
)
from app.modules.workspace.browser_connectivity_contract import (
    TURNPathEvidenceSnapshot,
    TURNReachabilityProfile,
)
from app.modules.workspace.browser_connectivity_evaluator import (
    BrowserConnectivityDecision,
    evaluate_browser_connectivity,
)

logger = logging.getLogger(__name__)

BROWSER_CONNECTIVITY_RECONCILE_LEASE = "docker-browser-connectivity"


@dataclass(frozen=True)
class _WorkspaceConnectivitySnapshot:
    workspace_id: str
    browser_instance_id: str
    browser_container_id: str
    browser_status: str


class DockerBrowserConnectivityReconcileService:
    """Read Docker evidence and write a fenced Browser connectivity projection."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()

    def reconcile_batch(self, *, limit: int) -> dict[str, int]:
        candidate_db = self._session_factory()
        try:
            workspace_ids = list(
                candidate_db.scalars(
                    select(db_models.Workspace.id)
                    .where(
                        db_models.Workspace.provisioner == "docker",
                        db_models.Workspace.browser_status == "running",
                        db_models.Workspace.browser_instance_id.is_not(None),
                    )
                    .order_by(db_models.Workspace.id)
                    .limit(limit)
                )
            )
        finally:
            candidate_db.close()

        result = {
            "candidates": len(workspace_ids),
            "reconciled": 0,
            "skipped": 0,
            "failed": 0,
        }
        for workspace_id in workspace_ids:
            try:
                outcome = self.reconcile_workspace(str(workspace_id))
            except Exception:
                logger.exception(
                    "Docker Browser connectivity reconciliation failed",
                    extra={"workspace_id": str(workspace_id)},
                )
                result["failed"] += 1
                continue
            result[outcome] += 1
        return result

    def reconcile_workspace(self, workspace_id: str) -> str:
        snapshot = self._snapshot(workspace_id)
        if snapshot is None:
            return "skipped"

        profile = self._load_profile()
        now = datetime.now(timezone.utc)
        backend: TURNPathEvidenceSnapshot | None = None
        backend_error: str | None = None
        frontend: dict[str, TURNPathEvidenceSnapshot | None] = {}
        frontend_errors: dict[str, str | None] = {}

        if profile is not None:
            with httpx.Client(
                timeout=self._settings.TURN_BROWSER_CONNECTIVITY_HTTP_TIMEOUT_SECONDS
            ) as client:
                backend, backend_error = self._read_evidence(
                    client,
                    self._backend_evidence_url(snapshot.workspace_id),
                )
                internal_token = self._read_internal_token()
                for vantage in profile.required_frontend_vantages:
                    frontend[vantage], frontend_errors[vantage] = self._read_evidence(
                        client,
                        self._frontend_evidence_url(profile, vantage),
                        bearer_token=internal_token,
                    )

        decision = evaluate_browser_connectivity(
            profile=profile,
            credential_revision=self._settings.TURN_CREDENTIAL_REVISION,
            backend=backend,
            backend_error=backend_error,
            frontend=frontend,
            frontend_errors=frontend_errors,
            now=now,
        )
        return self._commit_decision(snapshot, decision)

    def _snapshot(self, workspace_id: str) -> _WorkspaceConnectivitySnapshot | None:
        db = self._session_factory()
        try:
            workspace = db.get(db_models.Workspace, workspace_id)
            if (
                workspace is None
                or workspace.provisioner != "docker"
                or workspace.browser_status != "running"
                or not workspace.browser_instance_id
                or not workspace.browser_container_id
            ):
                return None
            return _WorkspaceConnectivitySnapshot(
                workspace_id=workspace.id,
                browser_instance_id=workspace.browser_instance_id,
                browser_container_id=workspace.browser_container_id,
                browser_status=workspace.browser_status,
            )
        finally:
            db.close()

    def _commit_decision(
        self,
        snapshot: _WorkspaceConnectivitySnapshot,
        decision: BrowserConnectivityDecision,
    ) -> str:
        db = self._session_factory()
        try:
            if not try_acquire_workspace_transaction_lock(db, snapshot.workspace_id):
                db.rollback()
                return "skipped"
            workspace = db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == snapshot.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                workspace is None
                or workspace.provisioner != "docker"
                or workspace.browser_status != "running"
                or workspace.browser_instance_id != snapshot.browser_instance_id
                or workspace.browser_container_id != snapshot.browser_container_id
            ):
                db.rollback()
                return "skipped"

            projection_changed = (
                workspace.browser_connectivity_state != decision.state
                or workspace.browser_connectivity_admission != decision.admission
                or workspace.browser_connectivity_profile_revision
                != decision.profile_revision
                or workspace.browser_connectivity_credential_revision
                != decision.credential_revision
            )
            workspace.browser_connectivity_browser_generation = (
                snapshot.browser_instance_id
            )
            workspace.browser_connectivity_state = decision.state
            workspace.browser_connectivity_contract_version = decision.contract_version
            workspace.browser_connectivity_admission = decision.admission
            workspace.browser_connectivity_profile_revision = decision.profile_revision
            workspace.browser_connectivity_credential_revision = (
                decision.credential_revision
            )
            workspace.browser_connectivity_accepted_at = decision.accepted_at
            workspace.browser_connectivity_expires_at = decision.expires_at
            workspace.browser_connectivity_reason = decision.reason
            workspace.browser_connectivity_error_code = decision.error_code
            if (
                projection_changed
                or workspace.browser_connectivity_last_transition_at is None
            ):
                workspace.browser_connectivity_last_transition_at = datetime.now(
                    timezone.utc
                )
            workspace.browser_connectivity_backend_state = decision.backend_state
            workspace.browser_connectivity_backend_accepted_at = (
                decision.backend_accepted_at
            )
            workspace.browser_connectivity_backend_expires_at = (
                decision.backend_expires_at
            )
            workspace.browser_connectivity_backend_reason = decision.backend_reason
            workspace.browser_connectivity_backend_error_code = (
                decision.backend_error_code
            )
            workspace.browser_connectivity_frontend_state = decision.frontend_state
            workspace.browser_connectivity_frontend_accepted_at = (
                decision.frontend_accepted_at
            )
            workspace.browser_connectivity_frontend_expires_at = (
                decision.frontend_expires_at
            )
            workspace.browser_connectivity_frontend_reason = decision.frontend_reason
            workspace.browser_connectivity_frontend_error_code = (
                decision.frontend_error_code
            )
            db.commit()
            return "reconciled"
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _load_profile(self) -> TURNReachabilityProfile | None:
        path = self._settings.TURN_REACHABILITY_PROFILE_FILE.strip()
        if not path:
            return None
        from app.modules.workspace.browser_connectivity_contract import (
            TURNReachabilityProfileError,
        )

        try:
            return TURNReachabilityProfile.from_file(path)
        except TURNReachabilityProfileError:
            logger.error("TURN reachability profile is unavailable")
            return None

    def _read_internal_token(self) -> str:
        path = self._settings.TURN_CONNECTIVITY_GATEWAY_INTERNAL_TOKEN_FILE.strip()
        if not path:
            return ""
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            logger.error("Connectivity Gateway internal token is unreadable")
            return ""

    @staticmethod
    def _read_evidence(
        client: httpx.Client,
        endpoint: str,
        *,
        bearer_token: str = "",
    ) -> tuple[TURNPathEvidenceSnapshot | None, str | None]:
        try:
            headers = (
                {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
            )
            response = client.get(endpoint, headers=headers)
            response.raise_for_status()
            return TURNPathEvidenceSnapshot.from_mapping(response.json()), None
        except (httpx.HTTPError, ValueError, TypeError):
            return None, "evidence_unavailable"

    def _backend_evidence_url(self, workspace_id: str) -> str:
        return f"http://workspace-browser-{workspace_id}:8082/v1/evidence"

    def _frontend_evidence_url(
        self,
        profile: TURNReachabilityProfile,
        vantage: str,
    ) -> str:
        return (
            self._settings.TURN_CONNECTIVITY_GATEWAY_URL.rstrip("/")
            + "/v1/evidence/"
            + quote(profile.revision, safe="")
            + "/"
            + quote(vantage, safe="")
        )


def enqueue_docker_browser_connectivity_reconcile(workspace_id: str) -> None:
    """Best-effort enqueue after a lifecycle commit has become durable."""

    from celery import current_app

    try:
        current_app.send_task(
            "workspace_browser_connectivity.reconcile_workspace",
            args=[workspace_id],
        )
    except Exception:
        logger.warning(
            "Docker Browser connectivity reconcile dispatch failed",
            extra={"workspace_id": workspace_id},
        )


__all__ = [
    "BROWSER_CONNECTIVITY_RECONCILE_LEASE",
    "DockerBrowserConnectivityReconcileService",
    "enqueue_docker_browser_connectivity_reconcile",
]
