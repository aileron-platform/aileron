"""Core 模組整合測試共用工具"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

from app.main import app


@contextmanager
def override_dependency(dependency: Callable[..., Any], provider: Callable[[], Any]):
    """暫時覆寫 FastAPI 依賴"""

    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependency, None)


@contextmanager
def override_multiple_dependencies(dependencies: dict[Callable[..., Any], Callable[[], Any]]):
    """同時覆寫多個 FastAPI 依賴"""

    # 儲存原始依賴
    original_overrides = {}
    for dependency in dependencies:
        if dependency in app.dependency_overrides:
            original_overrides[dependency] = app.dependency_overrides[dependency]

    # 設置新的依賴覆寫
    for dependency, provider in dependencies.items():
        app.dependency_overrides[dependency] = provider

    try:
        yield
    finally:
        # 恢復原始依賴
        for dependency, provider in dependencies.items():
            app.dependency_overrides.pop(dependency, None)

        # 恢復原始的覆寫（如果有的話）
        for dependency, provider in original_overrides.items():
            app.dependency_overrides[dependency] = provider


def create_websocket_test_overrides():
    """建立 WebSocket 測試的依賴覆寫"""
    from .websocket_test_helpers import StubWebSocketManager
    from .test_sessions_websocket import (
        StubSessionLifecycleService,
        StubSessionRepository,
        StubToolApprovalService
    )
    from .test_terminal_websocket import StubTerminalService

    return {
        # WebSocket 相關依賴
        "get_websocket_manager": lambda: StubWebSocketManager(),

        # Sessions 相關依賴
        "get_session_lifecycle_service": lambda: StubSessionLifecycleService(),
        "get_session_repository": lambda: StubSessionRepository(),
        "get_tool_approval_service": lambda: StubToolApprovalService(),

        # Terminal 相關依賴
        "get_container_management_service": lambda: StubTerminalService(),
    }
