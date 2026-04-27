"""Claude Code integration test shared utilities"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

from app.main import app


WORKSPACE_ID = "ws-integration"


@contextmanager
def override_dependency(
    dependency: Callable[..., Any], provider: Callable[[], Any]
):
    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependency, None)


@contextmanager
def patch_file_collection_service(stub: Any, *, target_router):
    original_cls = target_router.FileCollectionService

    def _factory(*_: Any, **__: Any) -> Any:
        return stub

    target_router.FileCollectionService = _factory
    try:
        yield
    finally:
        target_router.FileCollectionService = original_cls
