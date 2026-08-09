"""CLI settings integration dependency overrides."""

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
