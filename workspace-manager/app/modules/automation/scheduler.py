"""Single-loop PostgreSQL Automation scheduler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.database import SessionLocal
from app.modules.automation.repository import AutomationRepository
from app.modules.automation.execution import AutomationExecutionService
from app.modules.automation.notifications import AutomationNotificationService

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Poll due rows with one lifecycle task regardless of job count."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        poll_seconds: float | None = None,
        poll_waiter: Callable[[], Awaitable[None]] | None = None,
        notifications: AutomationNotificationService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._poll_seconds = (
            get_settings().AUTOMATION_SCHEDULER_POLL_SECONDS
            if poll_seconds is None
            else poll_seconds
        )
        self._poll_waiter = poll_waiter
        self._notifications = notifications or AutomationNotificationService()
        self._stop_event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self.task is not None and not self.task.done():
            return
        self._stop_event.clear()
        self.task = asyncio.create_task(self._run_loop(), name="automation-scheduler")

    async def stop(self) -> None:
        task = self.task
        if task is None:
            return
        self._stop_event.set()
        await task
        self.task = None

    def run_once(self) -> int:
        with self._session_factory() as session:
            due = AutomationRepository(session).list_due_occurrences()
            session.rollback()
        processed = 0
        for job_id, scheduled_for in due:
            with self._session_factory() as session:
                try:
                    repository = AutomationRepository(session)
                    execution = repository.enqueue_scheduled_occurrence(
                        job_id=job_id,
                        expected_scheduled_for=scheduled_for,
                    )
                    AutomationExecutionService(repository).cancel_running_after_commit(
                        repository.take_committed_running_cancellations()
                    )
                    if execution is not None and execution.status in {
                        "success",
                        "failed",
                        "cancelled",
                    }:
                        try:
                            notification_status = self._notifications.deliver_terminal(
                                execution=execution,
                                notification_config=(
                                    execution.job.notification_config or {}
                                ),
                            )
                            if notification_status is not None:
                                repository.update_notification_status(
                                    execution_id=execution.id,
                                    notification_status=notification_status,
                                )
                        except Exception as exc:
                            try:
                                session.rollback()
                            except Exception:
                                pass
                            logger.warning(
                                "Automation notification handling failed for execution %s: %s",
                                execution.id,
                                type(exc).__name__,
                            )
                    processed += int(execution is not None)
                except Exception as exc:
                    session.rollback()
                    logger.warning(
                        "Automation scheduler skipped job %s: %s",
                        job_id,
                        type(exc).__name__,
                    )
        return processed

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self._wait_for_poll()
            if self._stop_event.is_set():
                break
            try:
                await asyncio.to_thread(self.run_once)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Automation scheduler scan failed: %s",
                    type(exc).__name__,
                )

    async def _wait_for_poll(self) -> None:
        if self._poll_waiter is not None:
            await self._poll_waiter()
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_seconds)
        except asyncio.TimeoutError:
            return


__all__ = ["AutomationScheduler"]
