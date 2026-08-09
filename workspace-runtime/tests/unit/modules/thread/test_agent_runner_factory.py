from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from app.modules.thread import agent_runner_factory
from app.modules.thread.composite_agent_runner import CompositeAgentRunner


class FakeRunner:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def reserve(self) -> str:
        return "fake"

    def adopt_reservation(self, execution_id: str) -> None:
        return None

    async def start(self, request: Any, on_event: Any, execution_id: str) -> None:
        return None

    async def stop(self, execution_id: str) -> None:
        return None

    async def wait(self, execution_id: str) -> None:
        return None

    def is_alive(self, execution_id: str) -> bool:
        return False

    async def destroy_thread(self, thread_id: str) -> None:
        return None

    async def evict_idle(self) -> int:
        return 0


def _install_runner_module(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    class_name: str,
) -> None:
    module = types.ModuleType(module_name)
    setattr(module, class_name, FakeRunner)
    monkeypatch.setitem(sys.modules, module_name, module)


def test_get_agent_runner_returns_cached_composite_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_runner_factory._runners.clear()
    _install_runner_module(
        monkeypatch,
        "app.modules.thread.claude_sdk_agent_runner",
        "ClaudeSdkAgentRunner",
    )
    _install_runner_module(
        monkeypatch,
        "app.modules.thread.codex_sdk_agent_runner",
        "CodexSdkAgentRunner",
    )
    _install_runner_module(
        monkeypatch,
        "app.modules.thread.opencode_acp_agent_runner",
        "OpenCodeAcpAgentRunner",
    )

    first = agent_runner_factory.get_agent_runner("ws-1")
    second = agent_runner_factory.get_agent_runner("ws-1")

    assert isinstance(first, CompositeAgentRunner)
    assert first is second
    for method_name in (
        "reserve",
        "adopt_reservation",
        "start",
        "wait",
        "stop",
        "is_alive",
        "destroy_thread",
    ):
        assert callable(getattr(first, method_name))


@pytest.mark.asyncio
async def test_evict_idle_agent_runners_sums_cached_runners() -> None:
    class FakeCachedRunner:
        async def evict_idle(self) -> int:
            return 3

    agent_runner_factory._runners.clear()
    agent_runner_factory._runners["ws-1"] = FakeCachedRunner()
    agent_runner_factory._runners["ws-2"] = FakeCachedRunner()

    assert await agent_runner_factory.evict_idle_agent_runners() == 6
