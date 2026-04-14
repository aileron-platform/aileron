"""版本控制模組依賴注入"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .cache import create_git_cache
from .service import GitService


MOCK_GIT_ROOT = Path(__file__).resolve().parents[3] / "tests" / "git_workspaces"
WORKSPACE_ROOT = Path("/workspace")


@lru_cache()
def get_git_service() -> GitService:
    """取得 Git 版本控制服務實例（優化版 - 整合 Redis 快取）"""

    # 使用環境變數決定是否使用實際工作區路徑
    if os.getenv("NODE_ENV") == "development" or os.path.exists("/workspace"):
        base_path = WORKSPACE_ROOT
    else:
        base_path = MOCK_GIT_ROOT

    # 建立 Redis 快取（必須啟用）
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_flag = os.getenv("GIT_CACHE_ENABLED")
    if cache_flag and cache_flag.lower() != "true":
        raise RuntimeError("Git 版本控制需要 Redis 快取，請將 GIT_CACHE_ENABLED 設為 true")

    cache = create_git_cache(redis_url=redis_url, enabled=True)

    return GitService(base_path=base_path, cache=cache)


__all__ = ["get_git_service", "MOCK_GIT_ROOT"]
