"""Read-only PostgreSQL assertions for product conformance scenarios."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import psycopg
from psycopg.rows import dict_row

Row = dict[str, Any]
_TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed", "superseded"})


class ProductDatabase:
    """Query persisted product state without mutating it behind the API."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def ping(self) -> None:
        row = self.fetch_one("SELECT 1 AS value")
        if row != {"value": 1}:
            raise AssertionError("PostgreSQL prerequisite query failed")

    def fetch_one(
        self,
        query: str,
        params: Iterable[Any] = (),
    ) -> Row | None:
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                row = cursor.fetchone()
                return dict(row) if row is not None else None

    def fetch_all(
        self,
        query: str,
        params: Iterable[Any] = (),
    ) -> list[Row]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return [dict(row) for row in cursor.fetchall()]

    def get_workspace(self, workspace_id: str) -> Row | None:
        return self.fetch_one(
            """
            SELECT id, owner_id, provisioner, target_namespace, runtime_status,
                   runtime_instance_id::text AS runtime_instance_id,
                   runtime_container_id, browser_container_id, canvas_container_id,
                   runtime_internal_url, terminal_internal_url,
                   knowledge_base_mount_active_revision,
                   knowledge_base_mount_desired_revision,
                   knowledge_base_mount_observed_revision,
                   knowledge_base_mount_sync_status,
                   knowledge_base_mount_error_code,
                   knowledge_base_mount_active_snapshot,
                   knowledge_base_mount_candidate_snapshot,
                   knowledge_base_mount_failed_snapshot,
                   runtime_access_revision,
                   runtime_access_observed_revision,
                   runtime_desired_revision,
                   runtime_observed_revision,
                   browser_desired_revision,
                   browser_observed_revision,
                   canvas_desired_revision,
                   canvas_observed_revision
              FROM workspaces
             WHERE id = %s
            """,
            (workspace_id,),
        )

    def wait_workspace(
        self,
        workspace_id: str,
        predicate: Callable[[Row | None], bool],
        *,
        description: str,
        timeout_seconds: float = 600,
    ) -> Row | None:
        return self._wait(
            lambda: self.get_workspace(workspace_id),
            predicate,
            description=description,
            timeout_seconds=timeout_seconds,
        )

    def get_job(self, job_id: str) -> Row | None:
        return self.fetch_one(
            f"""
            SELECT {self._job_columns()}
              FROM workspace_runtime_jobs
             WHERE id = %s
            """,
            (job_id,),
        )

    def get_latest_job(
        self,
        workspace_id: str,
        operation_type: str | None = None,
    ) -> Row | None:
        operation_clause = " AND operation = %s" if operation_type else ""
        params: tuple[Any, ...] = (
            (workspace_id, operation_type) if operation_type else (workspace_id,)
        )
        return self.fetch_one(
            f"""
            SELECT {self._job_columns()}
              FROM workspace_runtime_jobs
             WHERE workspace_id = %s{operation_clause}
             ORDER BY scheduled_at DESC, id DESC
             LIMIT 1
            """,
            params,
        )

    def get_job_by_correlation(
        self,
        *,
        workspace_id: str,
        operation: str,
        correlation_id: str,
    ) -> Row | None:
        return self.fetch_one(
            f"""
            SELECT {self._job_columns()}
              FROM workspace_runtime_jobs
             WHERE workspace_id = %s
               AND operation = %s
               AND correlation_id = %s
            """,
            (workspace_id, operation, correlation_id),
        )

    def list_jobs(
        self,
        workspace_id: str,
        *,
        operation: str | None = None,
    ) -> list[Row]:
        operation_clause = " AND operation = %s" if operation else ""
        params: tuple[Any, ...] = (
            (workspace_id, operation) if operation else (workspace_id,)
        )
        return self.fetch_all(
            f"""
            SELECT {self._job_columns()}
              FROM workspace_runtime_jobs
             WHERE workspace_id = %s{operation_clause}
             ORDER BY scheduled_at, id
            """,
            params,
        )

    def wait_job(
        self,
        job_id: str,
        expected_status: str | set[str],
        *,
        timeout_seconds: float = 600,
    ) -> Row:
        statuses = (
            {expected_status}
            if isinstance(expected_status, str)
            else set(expected_status)
        )
        result = self._wait(
            lambda: self.get_job(job_id),
            lambda row: self._job_status_matches(
                row,
                expected_statuses=statuses,
                description=f"job {job_id}",
            ),
            description=f"job {job_id} to enter {sorted(statuses)}",
            timeout_seconds=timeout_seconds,
        )
        if result is None:
            raise AssertionError(f"Job disappeared while waiting: {job_id}")
        return result

    def wait_job_by_correlation(
        self,
        *,
        workspace_id: str,
        operation: str,
        correlation_id: str,
        expected_status: str | set[str],
        timeout_seconds: float = 600,
    ) -> Row:
        statuses = (
            {expected_status}
            if isinstance(expected_status, str)
            else set(expected_status)
        )
        result = self._wait(
            lambda: self.get_job_by_correlation(
                workspace_id=workspace_id,
                operation=operation,
                correlation_id=correlation_id,
            ),
            lambda row: self._job_status_matches(
                row,
                expected_statuses=statuses,
                description=f"{operation} correlation {correlation_id}",
            ),
            description=(
                f"{operation} correlation {correlation_id} to enter "
                f"{sorted(statuses)}"
            ),
            timeout_seconds=timeout_seconds,
        )
        if result is None:
            raise AssertionError(
                f"Job disappeared while waiting for correlation {correlation_id}"
            )
        return result

    def list_active_attachments(self, workspace_id: str) -> list[Row]:
        return self.fetch_all(
            """
            SELECT id, workspace_id, kb_id, mount_alias, attached_by_id,
                   created_at, updated_at
              FROM workspace_knowledge_base_attachments
             WHERE workspace_id = %s
             ORDER BY created_at, id
            """,
            (workspace_id,),
        )

    def list_attachment_kb_ids(self, workspace_id: str) -> list[str]:
        rows = self.fetch_all(
            """
            SELECT kb_id
              FROM workspace_knowledge_base_attachments
             WHERE workspace_id = %s
             ORDER BY kb_id
            """,
            (workspace_id,),
        )
        return [str(row["kb_id"]) for row in rows]

    def audit_cursor(self) -> tuple[datetime, str]:
        row = self.fetch_one("""
            SELECT created_at, id
              FROM audit_events
             ORDER BY created_at DESC, id DESC
             LIMIT 1
            """)
        if row is None:
            return datetime(1970, 1, 1, tzinfo=timezone.utc), ""
        return row["created_at"], row["id"]

    def audit_delta(
        self,
        cursor: tuple[datetime, str],
        event_type: str | None = None,
    ) -> list[Row]:
        event_clause = " AND event_type = %s" if event_type else ""
        params: tuple[Any, ...] = (
            (cursor[0], cursor[0], cursor[1], event_type)
            if event_type
            else (cursor[0], cursor[0], cursor[1])
        )
        return self.fetch_all(
            f"""
            SELECT id, event_type, actor_type, actor_id, actor_user_id,
                   target_type, target_id, action, result, error_code,
                   correlation_id, root_correlation_id, event_metadata,
                   created_at
              FROM audit_events
             WHERE (created_at > %s OR (created_at = %s AND id > %s))
                   {event_clause}
             ORDER BY created_at, id
            """,
            params,
        )

    @staticmethod
    def _job_columns() -> str:
        return """
            id, workspace_id, operation, target_component, strategy, status, retries,
            target_revision, target_runtime_instance_id::text
                AS target_runtime_instance_id,
            correlation_id, root_correlation_id, job_metadata,
            lifecycle_job_id, retry_of_job_id, dispatch_attempts,
            scheduled_at, started_at, finished_at, error_code
        """

    @staticmethod
    def _job_status_matches(
        row: Row | None,
        *,
        expected_statuses: set[str],
        description: str,
    ) -> bool:
        if row is None:
            return False
        observed_status = str(row["status"])
        if observed_status in expected_statuses:
            return True
        if observed_status in _TERMINAL_JOB_STATUSES:
            raise AssertionError(
                f"{description} reached terminal status {observed_status!r} "
                f"while waiting for {sorted(expected_statuses)}; "
                f"error_code={row.get('error_code')!r}"
            )
        return False

    @staticmethod
    def _wait(
        read: Callable[[], Any],
        predicate: Callable[[Any], bool],
        *,
        description: str,
        timeout_seconds: float,
        interval_seconds: float = 1.0,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        last_value: Any = None
        while time.monotonic() < deadline:
            last_value = read()
            if predicate(last_value):
                return last_value
            time.sleep(interval_seconds)
        raise AssertionError(
            f"Timed out waiting for {description}; last observed={last_value!r}"
        )
