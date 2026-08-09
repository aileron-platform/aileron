from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from app.modules.resource_telemetry.models import CapacityMeasurement, TelemetryBatch
from app.modules.resource_telemetry.reporter import ResourceTelemetryReporter


class MemoryOutbox:
    def __init__(self) -> None:
        self.items: dict[str, TelemetryBatch] = {}
        self.failed: list[str] = []

    async def enqueue(self, batch: TelemetryBatch) -> None:
        self.items[batch.batch_id] = batch

    async def pending(self, *, limit: int) -> Sequence[TelemetryBatch]:
        return list(self.items.values())[:limit]

    async def mark_sent(self, batch_id: str) -> None:
        self.items.pop(batch_id, None)

    async def mark_failed(self, batch_id: str) -> None:
        self.failed.append(batch_id)


class RecordingSink:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.batch_ids: list[str] = []
        self.batches: list[TelemetryBatch] = []
        self.closed = False

    async def publish_batch(self, batch: TelemetryBatch) -> None:
        self.batch_ids.append(batch.batch_id)
        self.batches.append(batch)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("manager unavailable")

    async def close(self) -> None:
        self.closed = True


class BlockingProbe:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def measure(self) -> tuple[CapacityMeasurement, ...]:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        now = datetime.now(timezone.utc)
        return (
            CapacityMeasurement(
                storage_kind="workspace_data",
                used_bytes=1,
                capacity_bytes=10,
                available_bytes=9,
                observed_at=now,
            ),
        )


def build_reporter(
    *, probe, outbox, sink, delayed_seconds: float = 0.01, batch_limit: int = 25
):
    return ResourceTelemetryReporter(
        probe=probe,
        outbox=outbox,
        sink=sink,
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        interval_seconds=900,
        retry_interval_seconds=900,
        delayed_probe_seconds=delayed_seconds,
        shutdown_timeout_seconds=1,
        batch_limit=batch_limit,
    )


@pytest.mark.asyncio
async def test_reporter_skips_overlapping_probe_without_blocking_caller() -> None:
    probe = BlockingProbe()
    outbox = MemoryOutbox()
    reporter = build_reporter(probe=probe, outbox=outbox, sink=RecordingSink())

    first = asyncio.create_task(reporter.capture_capacity())
    await probe.started.wait()

    assert await reporter.capture_capacity() is False
    probe.release.set()
    assert await first is True
    assert probe.calls == 1
    assert len(outbox.items) == 1
    assert reporter.metrics.snapshot()["capacity_probe_skipped_total"] == 1


@pytest.mark.asyncio
async def test_reporter_is_fail_open_when_probe_fails() -> None:
    class FailingProbe:
        async def measure(self):
            raise OSError("filesystem unavailable")

    reporter = build_reporter(
        probe=FailingProbe(), outbox=MemoryOutbox(), sink=RecordingSink()
    )

    assert await reporter.capture_capacity() is False
    assert reporter.metrics.snapshot()["capacity_measurement_failure_total"] == 1


@pytest.mark.asyncio
async def test_start_does_not_wait_for_the_startup_probe() -> None:
    probe = BlockingProbe()
    reporter = build_reporter(
        probe=probe, outbox=MemoryOutbox(), sink=RecordingSink()
    )

    await asyncio.wait_for(reporter.start(), timeout=0.05)
    await probe.started.wait()
    probe.release.set()
    await reporter.stop()


@pytest.mark.asyncio
async def test_runtime_started_event_is_durable_when_capacity_probe_fails() -> None:
    class FailingProbe:
        async def measure(self):
            raise OSError("filesystem unavailable")

    outbox = MemoryOutbox()
    sink = RecordingSink()
    reporter = build_reporter(probe=FailingProbe(), outbox=outbox, sink=sink)

    await reporter.start()
    await asyncio.sleep(0)
    await reporter.stop()

    assert any(
        event.event_type == "runtime_started"
        for batch in sink.batches
        for event in batch.events
    )


@pytest.mark.asyncio
async def test_scheduled_agent_activity_is_published_without_caller_waiting() -> None:
    class ImmediateProbe:
        async def measure(self) -> tuple[CapacityMeasurement, ...]:
            return ()

    sink = RecordingSink()
    reporter = build_reporter(
        probe=ImmediateProbe(), outbox=MemoryOutbox(), sink=sink
    )
    await reporter.start()
    reporter.schedule_activity("agent_execution_started")
    await asyncio.sleep(0.01)
    await reporter.stop()

    assert any(
        event.event_type == "agent_execution_started"
        for batch in sink.batches
        for event in batch.events
    )


@pytest.mark.asyncio
async def test_dispatch_retries_the_same_durable_batch_identifier() -> None:
    outbox = MemoryOutbox()
    batch = TelemetryBatch(
        batch_id="stable-batch",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        observed_at=datetime.now(timezone.utc),
        events=(),
        capacity_measurements=(),
    )
    await outbox.enqueue(batch)
    sink = RecordingSink(failures=1)
    reporter = build_reporter(probe=BlockingProbe(), outbox=outbox, sink=sink)

    assert await reporter.dispatch_pending() == 0
    assert set(outbox.items) == {"stable-batch"}
    assert await reporter.dispatch_pending() == 1

    assert sink.batch_ids == ["stable-batch", "stable-batch"]
    assert outbox.items == {}
    assert outbox.failed == ["stable-batch"]


@pytest.mark.asyncio
async def test_shutdown_drains_all_pending_batches_before_closing_sink() -> None:
    outbox = MemoryOutbox()
    for index in range(5):
        await outbox.enqueue(
            TelemetryBatch(
                batch_id=f"pending-{index}",
                workspace_id="workspace-1",
                runtime_instance_id="11111111-1111-4111-8111-111111111111",
                observed_at=datetime.now(timezone.utc),
                events=(),
                capacity_measurements=(),
            )
        )
    sink = RecordingSink()
    reporter = build_reporter(
        probe=BlockingProbe(),
        outbox=outbox,
        sink=sink,
        batch_limit=2,
    )

    await reporter.stop()

    assert outbox.items == {}
    assert sink.batch_ids == [f"pending-{index}" for index in range(5)]
    assert sink.closed is True


@pytest.mark.asyncio
async def test_startup_and_debounced_trigger_capture_then_shutdown_cleanly() -> None:
    class ImmediateProbe:
        def __init__(self) -> None:
            self.calls = 0

        async def measure(self) -> tuple[CapacityMeasurement, ...]:
            self.calls += 1
            now = datetime.now(timezone.utc)
            return (
                CapacityMeasurement(
                    storage_kind="runtime_home",
                    used_bytes=2,
                    capacity_bytes=10,
                    available_bytes=8,
                    observed_at=now,
                ),
            )

    probe = ImmediateProbe()
    outbox = MemoryOutbox()
    sink = RecordingSink()
    reporter = build_reporter(probe=probe, outbox=outbox, sink=sink)

    await reporter.start()
    reporter.schedule_delayed_probe()
    reporter.schedule_delayed_probe()
    await asyncio.sleep(0.03)
    await reporter.stop()

    assert probe.calls == 2
    assert sink.closed is True
    assert len(sink.batch_ids) == 3
    startup_batches = [
        batch
        for batch in sink.batches
        if batch.events and batch.events[0].event_type == "runtime_started"
    ]
    assert len(startup_batches) == 1
