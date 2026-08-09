"""Claude Code integration test shared utilities"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

from app.main import app


WORKSPACE_ID = "ws-integration"


@contextmanager
def override_dependency(dependency: Callable[..., Any], provider: Callable[[], Any]):
    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependency, None)
