from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.agent_session.services.tools.acp import connection_manager as cm_module


@pytest.mark.asyncio
async def test_get_or_create_reuses_alive_connection_and_replaces_dead_one(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = cm_module.AcpConnectionManager()
    alive = cm_module.AcpConnection(
        session_id="session-1",
        tool_type="codex",
        connection=object(),
        process=SimpleNamespace(returncode=None),
        context_manager=object(),
        client_impl=object(),
    )
    dead = cm_module.AcpConnection(
        session_id="session-1",
        tool_type="codex",
        connection=object(),
        process=SimpleNamespace(returncode=1),
        context_manager=object(),
        client_impl=object(),
    )
    created = cm_module.AcpConnection(
        session_id="session-1",
        tool_type="codex",
        connection=object(),
        process=SimpleNamespace(returncode=None),
        context_manager=object(),
        client_impl=object(),
    )

    manager._connections["session-1"] = alive
    assert (
        await manager.get_or_create("session-1", "codex", "cmd", [], [], None, "/tmp")
        is alive
    )

    manager._connections["session-1"] = dead
    close_mock = AsyncMock()
    create_mock = AsyncMock(return_value=created)
    monkeypatch.setattr(manager, "_close_connection", close_mock)
    monkeypatch.setattr(manager, "_create_connection", create_mock)

    result = await manager.get_or_create("session-1", "codex", "cmd", ["a"], ["--noop"], {"X": "1"}, "/tmp")

    assert result is created
    close_mock.assert_awaited_once_with(dead)
    create_mock.assert_awaited_once()
    assert manager.get_existing("session-1") is created


@pytest.mark.asyncio
async def test_close_and_close_all_cleanup_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = cm_module.AcpConnectionManager()
    conn1 = cm_module.AcpConnection("s1", "codex", object(), SimpleNamespace(returncode=None), object(), object())
    conn2 = cm_module.AcpConnection("s2", "gemini", object(), SimpleNamespace(returncode=None), object(), object())
    manager._connections = {"s1": conn1, "s2": conn2}
    close_mock = AsyncMock()
    monkeypatch.setattr(manager, "_close_connection", close_mock)

    await manager.close("s1")
    await manager.close_all()

    assert "s1" not in manager._connections
    assert manager._connections == {}
    assert close_mock.await_count == 2


@pytest.mark.asyncio
async def test_create_connection_initializes_and_handles_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = cm_module.AcpConnectionManager()
    entered_connection = object()
    process = SimpleNamespace(returncode=None)
    context_manager = SimpleNamespace(
        __aenter__=AsyncMock(return_value=(entered_connection, process)),
        __aexit__=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(cm_module, "spawn_agent_process", lambda *args, **kwargs: context_manager)
    init_mock = AsyncMock()
    monkeypatch.setattr(manager, "_initialize_connection", init_mock)

    connection = await manager._create_connection("session-1", "codex", "cmd", ["a"], ["--noop"], {"X": "1"}, "/tmp")

    assert connection.connection is entered_connection
    assert connection.process is process
    init_mock.assert_awaited_once()

    failing_context = SimpleNamespace(
        __aenter__=AsyncMock(side_effect=RuntimeError("spawn failed")),
        __aexit__=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(cm_module, "spawn_agent_process", lambda *args, **kwargs: failing_context)
    with pytest.raises(RuntimeError, match="spawn failed"):
        await manager._create_connection("session-1", "codex", "cmd", [], [], None, "/tmp")
    failing_context.__aexit__.assert_awaited_once()

    context_manager2 = SimpleNamespace(
        __aenter__=AsyncMock(return_value=(entered_connection, process)),
        __aexit__=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(cm_module, "spawn_agent_process", lambda *args, **kwargs: context_manager2)
    monkeypatch.setattr(manager, "_initialize_connection", AsyncMock(side_effect=RuntimeError("init failed")))
    close_mock = AsyncMock()
    monkeypatch.setattr(manager, "_close_connection", close_mock)
    with pytest.raises(RuntimeError, match="init failed"):
        await manager._create_connection("session-1", "codex", "cmd", [], [], None, "/tmp")
    close_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_and_close_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = cm_module.AcpConnectionManager()
    initialize = AsyncMock()
    context_manager = SimpleNamespace(__aexit__=AsyncMock(side_effect=RuntimeError("close failed")))
    unregister_calls: list[str] = []
    monkeypatch.setattr(
        cm_module,
        "global_tool_decision_manager",
        SimpleNamespace(unregister_hooks=lambda session_id: unregister_calls.append(session_id)),
    )
    conn = cm_module.AcpConnection(
        session_id="session-1",
        tool_type="codex",
        connection=SimpleNamespace(initialize=initialize),
        process=SimpleNamespace(returncode=None),
        context_manager=context_manager,
        client_impl=object(),
    )

    await manager._initialize_connection(conn, supports_terminal=False)
    await manager._initialize_connection(conn, supports_terminal=False)
    await manager._close_connection(conn)

    initialize.assert_awaited_once()
    assert conn.initialized is True
    assert unregister_calls == ["session-1"]


def test_extract_gemini_spawned_with() -> None:
    assert cm_module.AcpConnectionManager._extract_gemini_spawned_with(
        "gemini",
        ["--approval-mode", "auto_edit"],
    ) == "auto_edit"
    assert cm_module.AcpConnectionManager._extract_gemini_spawned_with(
        "gemini",
        [],
    ) is None
    assert cm_module.AcpConnectionManager._extract_gemini_spawned_with(
        "codex",
        ["--approval-mode", "yolo"],
    ) is None
