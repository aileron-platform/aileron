"""Core module integration test shared utilities"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

from app.main import app


@contextmanager
def override_dependency(dependency: Callable[..., Any], provider: Callable[[], Any]):
    """Temporarily override FastAPI dependency"""

    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependency, None)


@contextmanager
def override_multiple_dependencies(dependencies: dict[Callable[..., Any], Callable[[], Any]]):
    """Override multiple FastAPI dependencies simultaneously"""

    # Store original dependencies
    original_overrides = {}
    for dependency in dependencies:
        if dependency in app.dependency_overrides:
            original_overrides[dependency] = app.dependency_overrides[dependency]

    # Set up new dependency overrides
    for dependency, provider in dependencies.items():
        app.dependency_overrides[dependency] = provider

    try:
        yield
    finally:
        # Restore original dependencies
        for dependency, provider in dependencies.items():
            app.dependency_overrides.pop(dependency, None)

        # Restore original overrides (if any)
        for dependency, provider in original_overrides.items():
            app.dependency_overrides[dependency] = provider


def create_websocket_test_overrides():
    """Create dependency overrides for WebSocket testing"""
    from .websocket_test_helpers import StubWebSocketManager
    from .test_sessions_websocket import (
        StubSessionLifecycleService,
        StubSessionRepository,
        StubToolApprovalService
    )
    from .test_terminal_websocket import StubTerminalService

    return {
        # WebSocket related dependencies
        "get_websocket_manager": lambda: StubWebSocketManager(),

        # Sessions related dependencies
        "get_session_lifecycle_service": lambda: StubSessionLifecycleService(),
        "get_session_repository": lambda: StubSessionRepository(),
        "get_tool_approval_service": lambda: StubToolApprovalService(),

        # Terminal related dependencies
        "get_container_management_service": lambda: StubTerminalService(),
    }
