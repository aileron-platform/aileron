"""Third-party integration test shared utilities"""

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
