"""第三方整合測試共用工具"""

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
