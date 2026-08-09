"""Lifecycle contract for the single Automation scheduler loop."""

from __future__ import annotations

import asyncio
import importlib
import threading
from contextlib import suppress

import pytest


def _scheduler_type():
    module = importlib.import_module("app.modules.automation.scheduler")
    scheduler_type = getattr(module, "AutomationScheduler", None)
    assert scheduler_type is not None, "missing AutomationScheduler"
    return scheduler_type


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_awaits_single_loop() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def wait_for_poll() -> None:
        entered.set()
        await release.wait()

    scheduler = _scheduler_type()(
        session_factory=lambda: None,
        poll_seconds=5,
        poll_waiter=wait_for_poll,
    )
    await scheduler.start()
    first_task = scheduler.task
    await scheduler.start()
    assert scheduler.task is first_task
    assert len([task for task in asyncio.all_tasks() if task is first_task]) == 1
    await entered.wait()
    release.set()
    await scheduler.stop()
    assert first_task.done()
    assert scheduler.task is None


@pytest.mark.asyncio
async def test_loop_runs_blocking_scan_in_worker_thread(monkeypatch) -> None:
    called = asyncio.Event()

    async def fake_to_thread(_function):
        called.set()
        await asyncio.sleep(0)
        return 0

    async def immediate_poll() -> None:
        return None

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    scheduler = _scheduler_type()(
        session_factory=lambda: None,
        poll_seconds=0,
        poll_waiter=immediate_poll,
    )
    await scheduler.start()
    await called.wait()
    await scheduler.stop()
    assert called.is_set()


@pytest.mark.asyncio
async def test_stop_waits_for_in_flight_database_scan() -> None:
    started = threading.Event()
    release = threading.Event()

    async def immediate_poll() -> None:
        await asyncio.sleep(0)

    scheduler = _scheduler_type()(
        session_factory=lambda: None,
        poll_seconds=5,
        poll_waiter=immediate_poll,
    )

    def blocking_run_once() -> int:
        started.set()
        release.wait()
        return 0

    scheduler.run_once = blocking_run_once
    await scheduler.start()
    await asyncio.to_thread(started.wait)
    stop_task = asyncio.create_task(scheduler.stop())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(stop_task), timeout=0.05)
    finally:
        release.set()
    await stop_task
    assert scheduler.task is None


@pytest.mark.asyncio
async def test_transient_scan_failure_does_not_kill_scheduler_loop() -> None:
    attempts = 0
    recovered = asyncio.Event()
    loop = asyncio.get_running_loop()

    async def immediate_poll() -> None:
        await asyncio.sleep(0)

    scheduler = _scheduler_type()(
        session_factory=lambda: None,
        poll_seconds=5,
        poll_waiter=immediate_poll,
    )

    def flaky_run_once() -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient database failure")
        loop.call_soon_threadsafe(recovered.set)
        return 0

    scheduler.run_once = flaky_run_once
    await scheduler.start()
    try:
        await asyncio.wait_for(recovered.wait(), timeout=0.5)
        await scheduler.stop()
    finally:
        if scheduler.task is not None:
            with suppress(RuntimeError):
                await scheduler.stop()
    assert attempts >= 2
    assert scheduler.task is None
