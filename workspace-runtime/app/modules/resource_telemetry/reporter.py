"""Fail-open orchestration for capacity probes and telemetry delivery."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from contextlib import suppress
from datetime import datetime, timezone
from uuid import uuid4

from .capacity import CapacityProbe, CapacityProbeInProgress
from .models import ActivityType, ResourceActivityEvent, TelemetryBatch
from .outbox import TelemetryOutbox
from .sink import ResourceTelemetrySink

logger = logging.getLogger(__name__)


class ResourceTelemetryMetrics:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def increment(self, name: str) -> None:
        self._counts[name] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)


class ResourceTelemetryReporter:
    def __init__(
        self,
        *,
        probe: CapacityProbe,
        outbox: TelemetryOutbox,
        sink: ResourceTelemetrySink,
        workspace_id: str,
        runtime_instance_id: str,
        interval_seconds: float,
        retry_interval_seconds: float,
        delayed_probe_seconds: float,
        shutdown_timeout_seconds: float,
        batch_limit: int = 25,
    ) -> None:
        self._probe = probe
        self._outbox = outbox
        self._sink = sink
        self._workspace_id = workspace_id
        self._runtime_instance_id = runtime_instance_id
        self._interval_seconds = interval_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._delayed_probe_seconds = delayed_probe_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._batch_limit = batch_limit
        self._probe_lock = asyncio.Lock()
        self._dispatch_lock = asyncio.Lock()
        self._startup_task: asyncio.Task[None] | None = None
        self._periodic_task: asyncio.Task[None] | None = None
        self._dispatch_task: asyncio.Task[None] | None = None
        self._delayed_task: asyncio.Task[None] | None = None
        self._activity_tasks: set[asyncio.Task[None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False
        self._stopped = False
        self.metrics = ResourceTelemetryMetrics()

    async def start(self) -> None:
        if self._started:
            return
        self._loop = asyncio.get_running_loop()
        self._started = True
        self._stopped = False
        self._startup_task = asyncio.create_task(
            self._startup_cycle(), name="resource-telemetry-startup"
        )
        self._periodic_task = asyncio.create_task(
            self._periodic_loop(), name="resource-telemetry-capacity"
        )
        self._dispatch_task = asyncio.create_task(
            self._dispatch_loop(), name="resource-telemetry-outbox"
        )

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for task in (
            self._startup_task,
            self._periodic_task,
            self._dispatch_task,
            self._delayed_task,
        ):
            if task is not None:
                task.cancel()
        for task in (
            self._startup_task,
            self._periodic_task,
            self._dispatch_task,
            self._delayed_task,
        ):
            if task is not None:
                with suppress(asyncio.CancelledError):
                    await task
        activity_tasks = tuple(self._activity_tasks)
        if activity_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*activity_tasks),
                    timeout=self._shutdown_timeout_seconds,
                )
            except TimeoutError:
                for task in activity_tasks:
                    task.cancel()
                await asyncio.gather(*activity_tasks, return_exceptions=True)
        with suppress(Exception, TimeoutError):
            await asyncio.wait_for(
                self._drain_outbox(), timeout=self._shutdown_timeout_seconds
            )
        try:
            await self._sink.close()
        except Exception as exc:
            self.metrics.increment("telemetry_transport_close_failure_total")
            logger.warning(
                "Resource telemetry transport close failed type=%s",
                type(exc).__name__,
            )
        self._loop = None
        self._started = False

    async def _drain_outbox(self) -> None:
        while True:
            sent = await self.dispatch_pending()
            if sent == 0:
                return
            if sent < self._batch_limit:
                try:
                    pending = await self._outbox.pending(limit=1)
                except Exception as exc:
                    self.metrics.increment("telemetry_outbox_failure_total")
                    logger.warning(
                        "Failed to confirm resource telemetry outbox drain type=%s",
                        type(exc).__name__,
                    )
                    return
                if not pending:
                    return

    async def capture_capacity(self) -> bool:
        if self._probe_lock.locked():
            self.metrics.increment("capacity_probe_skipped_total")
            return False
        async with self._probe_lock:
            try:
                measurements = await self._probe.measure()
            except CapacityProbeInProgress:
                self.metrics.increment("capacity_probe_skipped_total")
                return False
            except TimeoutError:
                self.metrics.increment("capacity_measurement_timeout_total")
                logger.warning("Resource telemetry capacity probe timed out")
                return False
            except Exception as exc:
                self.metrics.increment("capacity_measurement_failure_total")
                logger.warning(
                    "Resource telemetry capacity probe failed type=%s",
                    type(exc).__name__,
                )
                return False

            observed_at = datetime.now(timezone.utc)
            batch = TelemetryBatch(
                batch_id=str(uuid4()),
                workspace_id=self._workspace_id,
                runtime_instance_id=self._runtime_instance_id,
                observed_at=observed_at,
                events=(),
                capacity_measurements=measurements,
            )
            try:
                await self._outbox.enqueue(batch)
            except Exception as exc:
                self.metrics.increment("telemetry_outbox_failure_total")
                logger.warning(
                    "Failed to persist resource telemetry batch type=%s",
                    type(exc).__name__,
                )
                return False
            self.metrics.increment("capacity_measurement_success_total")
            self.metrics.increment("telemetry_outbox_enqueued_total")
            return True

    async def record_activity(self, event_type: ActivityType) -> bool:
        occurred_at = datetime.now(timezone.utc)
        batch = TelemetryBatch(
            batch_id=str(uuid4()),
            workspace_id=self._workspace_id,
            runtime_instance_id=self._runtime_instance_id,
            observed_at=occurred_at,
            events=(
                ResourceActivityEvent(
                    event_id=str(uuid4()),
                    event_type=event_type,
                    occurred_at=occurred_at,
                ),
            ),
            capacity_measurements=(),
        )
        try:
            await self._outbox.enqueue(batch)
        except Exception as exc:
            self.metrics.increment("activity_event_rejected_total")
            logger.warning(
                "Failed to persist resource activity event type=%s",
                type(exc).__name__,
            )
            return False
        self.metrics.increment("activity_event_accepted_total")
        self.metrics.increment("telemetry_outbox_enqueued_total")
        return True

    async def dispatch_pending(self) -> int:
        if self._dispatch_lock.locked():
            return 0
        async with self._dispatch_lock:
            return await self._dispatch_pending_locked()

    async def _dispatch_pending_locked(self) -> int:
        try:
            pending = await self._outbox.pending(limit=self._batch_limit)
        except Exception as exc:
            self.metrics.increment("telemetry_outbox_failure_total")
            logger.warning(
                "Failed to read resource telemetry outbox type=%s",
                type(exc).__name__,
            )
            return 0

        sent = 0
        for batch in pending:
            try:
                await self._sink.publish_batch(batch)
                await self._outbox.mark_sent(batch.batch_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.increment("telemetry_publish_failure_total")
                logger.warning(
                    "Resource telemetry batch delivery failed",
                    exc_info=True,
                )
                with suppress(Exception):
                    await self._outbox.mark_failed(batch.batch_id)
                break
            self.metrics.increment("telemetry_publish_success_total")
            sent += 1
        return sent

    def schedule_delayed_probe(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._replace_delayed_task)

    def schedule_activity(self, event_type: ActivityType) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._create_activity_task, event_type)

    def _create_activity_task(self, event_type: ActivityType) -> None:
        task = asyncio.create_task(
            self._run_activity(event_type),
            name="resource-telemetry-activity",
        )
        self._activity_tasks.add(task)
        task.add_done_callback(self._activity_tasks.discard)

    async def _run_activity(self, event_type: ActivityType) -> None:
        if await self.record_activity(event_type):
            await self.dispatch_pending()

    def _replace_delayed_task(self) -> None:
        if self._delayed_task is not None:
            self._delayed_task.cancel()
        self._delayed_task = asyncio.create_task(
            self._run_delayed_probe(), name="resource-telemetry-delayed-capacity"
        )

    async def _run_delayed_probe(self) -> None:
        await asyncio.sleep(self._delayed_probe_seconds)
        if await self.capture_capacity():
            await self.dispatch_pending()

    async def _startup_cycle(self) -> None:
        await self.record_activity("runtime_started")
        await self.capture_capacity()
        await self.dispatch_pending()

    async def _periodic_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval_seconds)
            if await self.capture_capacity():
                await self.dispatch_pending()

    async def _dispatch_loop(self) -> None:
        while True:
            await asyncio.sleep(self._retry_interval_seconds)
            await self.dispatch_pending()


__all__ = ["ResourceTelemetryMetrics", "ResourceTelemetryReporter"]
