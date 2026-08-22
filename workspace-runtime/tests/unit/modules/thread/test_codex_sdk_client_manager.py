from __future__ import annotations

import asyncio
import json
import sys
import threading
from dataclasses import dataclass, field
from typing import Any

import pytest
from openai_codex import ApprovalMode, Sandbox

import app.modules.thread.codex_sdk_client_manager as codex_sdk_client_manager
from app.modules.thread.codex_sdk_client_manager import CodexSdkClientManager
from app.modules.thread.mcp.config import AILERON_MCP_SERVER_PATH


@dataclass
class FakeTurn:
    id: str = "turn-1"
    interrupted: bool = False

    async def interrupt(self) -> None:
        self.interrupted = True


@dataclass
class FakeThread:
    id: str
    turns: list[FakeTurn] = field(default_factory=list)
    turn_inputs: list[object] = field(default_factory=list)
    turn_kwargs: list[dict[str, Any]] = field(default_factory=list)

    async def turn(self, input, **kwargs):
        turn = FakeTurn(id=f"turn-{len(self.turns) + 1}")
        self.turns.append(turn)
        self.turn_inputs.append(input)
        self.turn_kwargs.append(kwargs)
        return turn


@dataclass
class FakeCodex:
    started_threads: list[FakeThread] = field(default_factory=list)
    resumed_threads: list[str] = field(default_factory=list)
    start_kwargs: list[dict[str, Any]] = field(default_factory=list)
    resume_kwargs: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    async def thread_start(self, **kwargs):
        thread = FakeThread(id="019f507e-2fe8-7c12-a9fc-48f3d316b569")
        self.start_kwargs.append(kwargs)
        self.started_threads.append(thread)
        return thread

    async def thread_resume(self, thread_id: str, **kwargs):
        self.resumed_threads.append(thread_id)
        self.resume_kwargs.append(kwargs)
        return FakeThread(id=thread_id)

    async def close(self) -> None:
        self.closed = True


def fake_codex_factory() -> FakeCodex:
    return FakeCodex()


class BlockingStartCodex(FakeCodex):
    def __init__(self, *, close_error: BaseException | None = None) -> None:
        super().__init__()
        self.start_entered = asyncio.Event()
        self.release_start = asyncio.Event()
        self.close_error = close_error
        self.close_calls = 0

    async def thread_start(self, **kwargs):
        self.start_entered.set()
        await self.release_start.wait()
        return await super().thread_start(**kwargs)

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class LateMaterializingStartCodex(FakeCodex):
    def __init__(self) -> None:
        super().__init__()
        self.start_entered = asyncio.Event()
        self.release_start = asyncio.Event()
        self.close_calls = 0
        self.transport_open = False

    async def thread_start(self, **kwargs):
        self.start_entered.set()
        await self.release_start.wait()
        self.closed = False
        self.transport_open = True
        return await super().thread_start(**kwargs)

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        self.transport_open = False


class NonCancellableLateMaterializingCodex(FakeCodex):
    def __init__(self) -> None:
        super().__init__()
        self.start_entered = asyncio.Event()
        self.release_materialization = threading.Event()
        self.final_close = asyncio.Event()
        self.close_calls = 0
        self.transport_open = False

    def _materialize_transport(self) -> None:
        self.release_materialization.wait(timeout=5)
        self.closed = False
        self.transport_open = True

    async def _wait_for_materialization(self) -> None:
        self.start_entered.set()
        await asyncio.to_thread(self._materialize_transport)

    async def thread_start(self, **kwargs):
        await self._wait_for_materialization()
        return await super().thread_start(**kwargs)

    async def thread_resume(self, thread_id: str, **kwargs):
        await self._wait_for_materialization()
        return await super().thread_resume(thread_id, **kwargs)

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        self.transport_open = False
        if self.close_calls >= 2:
            self.final_close.set()


class BlockingCloseCodex(FakeCodex):
    def __init__(self) -> None:
        super().__init__()
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        self.close_started.set()
        await self.release_close.wait()
        await super().close()


class FailingSecondTurnThread(FakeThread):
    def __init__(self, *, turn_error: BaseException) -> None:
        super().__init__(id="codex-thread-reused")
        self.turn_error = turn_error
        self.second_turn_entered = asyncio.Event()
        self.release_second_turn = asyncio.Event()

    async def turn(self, input, **kwargs):
        if self.turns:
            self.second_turn_entered.set()
            await self.release_second_turn.wait()
            raise self.turn_error
        return await super().turn(input, **kwargs)


class ReusedThreadCodex(FakeCodex):
    def __init__(
        self,
        *,
        thread: FailingSecondTurnThread,
        close_error: BaseException | None = None,
    ) -> None:
        super().__init__()
        self.thread = thread
        self.close_error = close_error

    async def thread_start(self, **kwargs):
        self.start_kwargs.append(kwargs)
        self.started_threads.append(self.thread)
        return self.thread

    async def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


@pytest.mark.asyncio
async def test_startup_claim_prevents_eviction_and_concurrent_start() -> None:
    codex = BlockingStartCodex()
    manager = CodexSdkClientManager(
        codex_factory=lambda: codex,
        idle_ttl_seconds=10,
    )
    execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=execution_id,
            prompt="hello",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
            now=100,
        )
    )
    await asyncio.wait_for(codex.start_entered.wait(), timeout=1)

    assert manager.is_alive(execution_id) is True
    assert manager._execution_to_thread == {execution_id: "aileron-thread-1"}
    assert await manager.evict_idle(now=1_000) == 0
    assert codex.closed is False

    competing_execution_id = manager.reserve()
    with pytest.raises(ValueError, match="thread_execution_active"):
        await manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=competing_execution_id,
            prompt="competing",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    assert manager.is_alive(competing_execution_id) is False

    codex.release_start.set()
    started = await start_task
    assert started.codex is codex
    assert manager.is_alive(execution_id) is True

    await manager.finish_execution(execution_id, now=100)
    assert await manager.evict_idle(now=109) == 0
    assert await manager.evict_idle(now=110) == 1
    assert codex.closed is True


@pytest.mark.asyncio
async def test_reused_thread_turn_failure_rolls_back_without_masking_error() -> None:
    turn_error = RuntimeError("turn startup failed")
    thread = FailingSecondTurnThread(turn_error=turn_error)
    codex = ReusedThreadCodex(
        thread=thread,
        close_error=RuntimeError("close failed"),
    )
    manager = CodexSdkClientManager(
        codex_factory=lambda: codex,
        idle_ttl_seconds=10,
    )
    first_execution_id = manager.reserve()
    await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=first_execution_id,
        prompt="first",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
        now=10,
    )
    await manager.finish_execution(first_execution_id, now=20)

    second_execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=second_execution_id,
            prompt="second",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    )
    await asyncio.wait_for(thread.second_turn_entered.wait(), timeout=1)

    assert await manager.evict_idle(now=1_000) == 0
    assert codex.closed is False

    thread.release_second_turn.set()
    with pytest.raises(RuntimeError, match="turn startup failed") as raised:
        await start_task
    assert raised.value is turn_error
    assert codex.closed is True
    assert manager.is_alive(second_execution_id) is False
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager._reserved == set()


@pytest.mark.asyncio
async def test_cancelled_thread_start_rolls_back_and_closes_transport() -> None:
    codex = BlockingStartCodex(close_error=RuntimeError("close failed"))
    manager = CodexSdkClientManager(codex_factory=lambda: codex)
    execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=execution_id,
            prompt="hello",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    )
    await asyncio.wait_for(codex.start_entered.wait(), timeout=1)

    start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start_task

    finalizers = set(manager._startup_finalizers)
    assert codex.close_calls == 1
    assert finalizers
    assert codex.closed is True
    assert manager.is_alive(execution_id) is False
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager._reserved == set()

    codex.release_start.set()
    await asyncio.wait_for(asyncio.gather(*finalizers), timeout=1)
    await asyncio.sleep(0)

    assert codex.close_calls == 2
    assert manager._startup_finalizers == set()


@pytest.mark.asyncio
async def test_stop_during_thread_start_prevents_state_resurrection() -> None:
    codex = BlockingStartCodex()
    manager = CodexSdkClientManager(codex_factory=lambda: codex)
    execution_id = manager.reserve()
    start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=execution_id,
            prompt="hello",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    )
    await asyncio.wait_for(codex.start_entered.wait(), timeout=1)
    startup_state = manager._states["aileron-thread-1"]

    await manager.stop_execution(execution_id)
    codex.release_start.set()
    with pytest.raises(RuntimeError, match="execution_stopped_during_startup"):
        await start_task

    assert codex.closed is True
    assert startup_state.active_execution_id is None
    assert manager.is_alive(execution_id) is False
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager._reserved == set()


@pytest.mark.asyncio
async def test_replaced_state_rollback_removes_only_original_execution_mapping() -> (
    None
):
    original_codex = BlockingStartCodex()
    replacement_codex = FakeCodex()
    codex_clients = iter([original_codex, replacement_codex])
    manager = CodexSdkClientManager(codex_factory=lambda: next(codex_clients))
    original_execution_id = manager.reserve()
    original_start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=original_execution_id,
            prompt="original",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    )
    await asyncio.wait_for(original_codex.start_entered.wait(), timeout=1)

    original_state = manager._states.pop("aileron-thread-1")
    await original_codex.close()
    replacement_execution_id = manager.reserve()
    replacement_start = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=replacement_execution_id,
        prompt="replacement",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )
    replacement_state = manager._states["aileron-thread-1"]
    assert manager._execution_to_thread == {
        original_execution_id: "aileron-thread-1",
        replacement_execution_id: "aileron-thread-1",
    }

    original_codex.release_start.set()
    with pytest.raises(
        RuntimeError, match="execution_stopped_during_startup"
    ) as raised:
        await original_start_task

    assert str(raised.value) == "execution_stopped_during_startup"
    assert manager._states == {"aileron-thread-1": replacement_state}
    assert manager._execution_to_thread == {
        replacement_execution_id: "aileron-thread-1"
    }
    assert original_state.active_execution_id is None
    assert replacement_state.active_execution_id == replacement_execution_id
    assert replacement_start.codex is replacement_codex
    assert replacement_codex.closed is False
    assert manager.is_alive(original_execution_id) is False
    assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.asyncio
async def test_stop_during_start_recleans_original_and_preserves_successor() -> None:
    original_codex = LateMaterializingStartCodex()
    replacement_codex = FakeCodex()
    codex_clients = iter([original_codex, replacement_codex])
    manager = CodexSdkClientManager(codex_factory=lambda: next(codex_clients))
    original_execution_id = manager.reserve()
    original_start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=original_execution_id,
            prompt="original",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
        )
    )
    await asyncio.wait_for(original_codex.start_entered.wait(), timeout=1)
    original_state = manager._states["aileron-thread-1"]

    await manager.stop_execution(original_execution_id)
    assert original_codex.close_calls == 1
    assert original_codex.transport_open is False

    replacement_execution_id = manager.reserve()
    replacement_start = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=replacement_execution_id,
        prompt="replacement",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )
    replacement_state = manager._states["aileron-thread-1"]

    original_codex.release_start.set()
    with pytest.raises(RuntimeError, match="execution_stopped_during_startup"):
        await original_start_task

    assert original_codex.close_calls == 2
    assert original_codex.transport_open is False
    assert original_codex.closed is True
    assert original_state.active_execution_id is None
    assert manager._states == {"aileron-thread-1": replacement_state}
    assert manager._execution_to_thread == {
        replacement_execution_id: "aileron-thread-1"
    }
    assert replacement_state.active_execution_id == replacement_execution_id
    assert replacement_start.codex is replacement_codex
    assert replacement_codex.closed is False
    assert manager.is_alive(original_execution_id) is False
    assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.parametrize("resume_session_id", [None, "codex-thread-existing"])
@pytest.mark.asyncio
async def test_cancelled_non_cancellable_startup_is_finally_closed_without_harming_successor(
    resume_session_id: str | None,
) -> None:
    original_codex = NonCancellableLateMaterializingCodex()
    replacement_codex = FakeCodex()
    codex_clients = iter([original_codex, replacement_codex])
    manager = CodexSdkClientManager(codex_factory=lambda: next(codex_clients))
    original_execution_id = manager.reserve()
    original_start_task = asyncio.create_task(
        manager.start_turn(
            thread_id="aileron-thread-1",
            execution_id=original_execution_id,
            prompt="original",
            attachments=[],
            cwd="/workspace",
            resume_session_id=resume_session_id,
            model=None,
        )
    )
    await asyncio.wait_for(original_codex.start_entered.wait(), timeout=1)
    original_state = manager._states["aileron-thread-1"]

    original_start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(original_start_task, timeout=1)

    assert original_codex.close_calls == 1
    assert original_codex.transport_open is False
    assert manager._startup_finalizers
    assert manager._states == {}
    assert manager._execution_to_thread == {}
    assert manager.is_alive(original_execution_id) is False

    replacement_execution_id = manager.reserve()
    replacement_start = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=replacement_execution_id,
        prompt="replacement",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )
    replacement_state = manager._states["aileron-thread-1"]

    original_codex.release_materialization.set()
    await asyncio.wait_for(original_codex.final_close.wait(), timeout=1)
    await asyncio.sleep(0)

    assert original_codex.close_calls == 2
    assert original_codex.transport_open is False
    assert original_codex.closed is True
    assert original_state.active_execution_id is None
    assert manager._startup_finalizers == set()
    assert manager._states == {"aileron-thread-1": replacement_state}
    assert manager._execution_to_thread == {
        replacement_execution_id: "aileron-thread-1"
    }
    assert replacement_state.active_execution_id == replacement_execution_id
    assert replacement_start.codex is replacement_codex
    assert replacement_codex.closed is False
    assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.asyncio
async def test_codex_config_defaults_to_sdk_bundled_binary(
    tmp_path,
    monkeypatch,
) -> None:
    captured_configs: list[Any] = []

    class CapturingCodex(FakeCodex):
        def __init__(self, *, config: Any) -> None:
            super().__init__()
            captured_configs.append(config)

    monkeypatch.setenv("PATH", str(tmp_path / "path-codex-bin"))
    monkeypatch.setattr(codex_sdk_client_manager, "AsyncCodex", CapturingCodex)
    manager = CodexSdkClientManager(
        codex_home=str(tmp_path / "codex-home"),
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert captured_configs[0].codex_bin is None


@pytest.mark.asyncio
async def test_explicit_codex_binary_override_is_preserved_and_enables_mcp(
    tmp_path,
    monkeypatch,
) -> None:
    captured_configs: list[Any] = []

    class CapturingCodex(FakeCodex):
        def __init__(self, *, config: Any) -> None:
            super().__init__()
            captured_configs.append(config)

    monkeypatch.setattr(codex_sdk_client_manager, "AsyncCodex", CapturingCodex)
    manager = CodexSdkClientManager(
        codex_bin="/usr/local/bin/codex",
        codex_home=str(tmp_path / "codex-home"),
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert captured_configs
    assert captured_configs[0].codex_bin == "/usr/local/bin/codex"
    config_overrides = captured_configs[0].config_overrides
    assert (
        f"mcp_servers.aileron.command={json.dumps(sys.executable)}" in config_overrides
    )
    assert (
        "mcp_servers.aileron.args="
        f"[{json.dumps(str(AILERON_MCP_SERVER_PATH))}]" in config_overrides
    )
    assert AILERON_MCP_SERVER_PATH.exists()


@pytest.mark.asyncio
async def test_adopt_reservation_allows_external_execution_id() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    manager.adopt_reservation("external-exec")

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id="external-exec",
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert started.codex_thread_id == "019f507e-2fe8-7c12-a9fc-48f3d316b569"


@pytest.mark.asyncio
async def test_start_turn_starts_new_thread_and_tracks_execution() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model="gpt-5.6-sol",
    )

    assert started.codex_thread_id == "019f507e-2fe8-7c12-a9fc-48f3d316b569"
    assert len(started.codex_thread_id) <= 64
    assert started.codex.start_kwargs[0]["sandbox"] is Sandbox.full_access
    assert started.codex.start_kwargs[0]["approval_mode"] is ApprovalMode.deny_all
    assert started.thread.turn_kwargs[0]["sandbox"] is Sandbox.full_access
    assert started.thread.turn_kwargs[0]["approval_mode"] is ApprovalMode.deny_all
    assert manager.is_alive(execution_id) is True


@pytest.mark.asyncio
async def test_start_turn_resumes_existing_thread_id() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id="codex-thread-existing",
        model=None,
    )

    assert started.codex_thread_id == "codex-thread-existing"


@pytest.mark.asyncio
async def test_stop_interrupts_active_turn_without_closing_codex() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    await manager.stop_execution(execution_id)

    assert started.turn.interrupted is True
    assert started.codex.closed is False


@pytest.mark.asyncio
async def test_destroy_thread_closes_codex_and_clears_execution() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    await manager.destroy_thread("aileron-thread-1")

    assert started.codex.closed is True
    assert manager.is_alive(execution_id) is False


@pytest.mark.asyncio
async def test_evict_idle_closes_inactive_state() -> None:
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=10,
    )
    execution_id = manager.reserve()
    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
        now=100,
    )
    await manager.finish_execution(execution_id, now=100)

    evicted = await manager.evict_idle(now=111)

    assert evicted == 1
    assert started.codex.closed is True


@pytest.mark.asyncio
async def test_evict_idle_repeatedly_skips_replaced_later_snapshot_state() -> None:
    for _ in range(25):
        first_codex = BlockingCloseCodex()
        stale_later_codex = FakeCodex()
        replacement_codex = FakeCodex()
        codex_clients = iter([first_codex, stale_later_codex, replacement_codex])
        manager = CodexSdkClientManager(
            codex_factory=lambda: next(codex_clients),
            idle_ttl_seconds=10,
        )

        first_execution_id = manager.reserve()
        await manager.start_turn(
            thread_id="thread-first",
            execution_id=first_execution_id,
            prompt="first",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
            now=0,
        )
        await manager.finish_execution(first_execution_id, now=0)

        later_execution_id = manager.reserve()
        await manager.start_turn(
            thread_id="thread-later",
            execution_id=later_execution_id,
            prompt="later",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
            now=0,
        )
        await manager.finish_execution(later_execution_id, now=0)

        eviction_task = asyncio.create_task(manager.evict_idle(now=100))
        await asyncio.wait_for(first_codex.close_started.wait(), timeout=1)

        await manager.destroy_thread("thread-later")
        replacement_execution_id = manager.reserve()
        replacement_start = await manager.start_turn(
            thread_id="thread-later",
            execution_id=replacement_execution_id,
            prompt="replacement",
            attachments=[],
            cwd="/workspace",
            resume_session_id=None,
            model=None,
            now=100,
        )
        replacement_state = manager._states["thread-later"]

        first_codex.release_close.set()
        assert await asyncio.wait_for(eviction_task, timeout=1) == 1

        assert first_codex.close_calls == 1
        assert first_codex.closed is True
        assert stale_later_codex.closed is True
        assert replacement_start.codex is replacement_codex
        assert replacement_codex.closed is False
        assert manager._states == {"thread-later": replacement_state}
        assert manager._execution_to_thread == {
            replacement_execution_id: "thread-later"
        }
        assert manager.is_alive(replacement_execution_id) is True


@pytest.mark.asyncio
async def test_start_turn_preserves_prompt_and_supported_attachments_in_run_input() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="inspect these",
        attachments=[
            {
                "name": "screen.png",
                "mimeType": "image/png",
                "path": "/workspace/.aileron/uploads/screen.png",
            },
            {
                "name": "notes.txt",
                "mimeType": "text/plain",
                "path": "/workspace/.aileron/uploads/notes.txt",
            },
        ],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    run_input = started.thread.turn_inputs[0]
    assert [type(item).__name__ for item in run_input] == [
        "TextInput",
        "LocalImageInput",
        "TextInput",
    ]
    assert run_input[0].text == "inspect these"
    assert run_input[1].path == "/workspace/.aileron/uploads/screen.png"
    assert run_input[2].text == (
        "Attached file: notes.txt (/workspace/.aileron/uploads/notes.txt)"
    )


@pytest.mark.asyncio
async def test_start_turn_passes_aileron_canvas_developer_instructions_on_new_thread() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id=None,
        model=None,
    )

    assert (
        started.codex.start_kwargs[0]["developer_instructions"]
        == codex_sdk_client_manager.CODEX_AILERON_MCP_PROMPT
    )
    assert (
        "clarifying question" in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "expects the user to answer"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Do not use AskUserQuestion"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "end the turn immediately"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Never infer, invent, or fabricate user answers"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "the aileron-web-canvas skill owns the workflow"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Completion condition"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert "is not delivery" in started.codex.start_kwargs[0]["developer_instructions"]
    assert (
        "Hard cap: 5 questions"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert (
        "Set each question's default"
        in started.codex.start_kwargs[0]["developer_instructions"]
    )
    assert started.codex.start_kwargs[0]["config"] == {
        "mcp_servers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }


@pytest.mark.asyncio
async def test_start_turn_passes_aileron_canvas_developer_instructions_on_resume() -> (
    None
):
    manager = CodexSdkClientManager(
        codex_factory=fake_codex_factory,
        idle_ttl_seconds=60,
    )
    execution_id = manager.reserve()

    started = await manager.start_turn(
        thread_id="aileron-thread-1",
        execution_id=execution_id,
        prompt="hello",
        attachments=[],
        cwd="/workspace",
        resume_session_id="codex-thread-existing",
        model=None,
    )

    assert (
        started.codex.resume_kwargs[0]["developer_instructions"]
        == codex_sdk_client_manager.CODEX_AILERON_MCP_PROMPT
    )
    assert (
        "clarifying question"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "expects the user to answer"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Do not use AskUserQuestion"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "end the turn immediately"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Never infer, invent, or fabricate user answers"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "the aileron-web-canvas skill owns the workflow"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Completion condition"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert "is not delivery" in started.codex.resume_kwargs[0]["developer_instructions"]
    assert (
        "Hard cap: 5 questions"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert (
        "Set each question's default"
        in started.codex.resume_kwargs[0]["developer_instructions"]
    )
    assert started.codex.resume_kwargs[0]["config"] == {
        "mcp_servers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }
