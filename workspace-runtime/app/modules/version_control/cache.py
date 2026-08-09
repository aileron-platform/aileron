"""Git operation caching layer"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Optional


@dataclass(frozen=True)
class _CacheEntry:
    value: str
    expires_at: float


class GitCache:
    """Bounded process-local cache for immutable Git query results."""

    def __init__(
        self,
        ttl: int = 300,
        enabled: bool = True,
        max_entries: int = 1024,
    ) -> None:
        if ttl <= 0 or max_entries <= 0:
            raise ValueError("Git cache limits must be positive")
        self.ttl = ttl
        self.enabled = enabled
        self.max_entries = max_entries
        self.prefix = "git:cache:"
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = RLock()

    def _make_key(self, workspace_id: str, operation: str, **params: Any) -> str:
        """Generate cache key

        Args:
            workspace_id: Workspace ID
            operation: Operation name (e.g., 'changes', 'commits', 'status')
            **params: Additional parameters (will be serialized and hashed)

        Returns:
            Cache key string
        """
        # Sort and serialize parameters to ensure same parameters generate same key
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
        return f"{self.prefix}{workspace_id}:{operation}:{param_hash}"

    def get(self, workspace_id: str, operation: str, **params: Any) -> Optional[Any]:
        """Get cached data

        Args:
            workspace_id: Workspace ID
            operation: Operation name
            **params: Additional parameters

        Returns:
            Cached data, returns None if not exists or expired
        """
        if not self.enabled:
            return None

        key = self._make_key(workspace_id, operation, **params)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
        try:
            return json.loads(entry.value)
        except json.JSONDecodeError:
            with self._lock:
                self._entries.pop(key, None)
            return None

    def set(
        self,
        workspace_id: str,
        operation: str,
        data: Any,
        ttl: Optional[int] = None,
        **params: Any,
    ) -> bool:
        """Set cached data

        Args:
            workspace_id: Workspace ID
            operation: Operation name
            data: Data to cache (must be JSON serializable)
            ttl: Cache TTL in seconds, uses default if None
            **params: Additional parameters

        Returns:
            Whether cache was successfully set
        """
        if not self.enabled:
            return False

        resolved_ttl = self.ttl if ttl is None else ttl
        if resolved_ttl <= 0:
            return False
        try:
            serialized = json.dumps(data, default=str)
        except (TypeError, ValueError):
            return False
        key = self._make_key(workspace_id, operation, **params)
        now = time.monotonic()
        with self._lock:
            self._discard_expired(now)
            if key not in self._entries and len(self._entries) >= self.max_entries:
                oldest_key = min(
                    self._entries,
                    key=lambda candidate: self._entries[candidate].expires_at,
                )
                self._entries.pop(oldest_key, None)
            self._entries[key] = _CacheEntry(
                value=serialized,
                expires_at=now + resolved_ttl,
            )
        return True

    def invalidate(self, workspace_id: str, pattern: str = "*") -> int:
        """Invalidate cache

        Args:
            workspace_id: Workspace ID
            pattern: Match pattern (supports * wildcard)

        Returns:
            Number of deleted keys
        """
        if not self.enabled:
            return 0

        if "*" not in pattern:
            pattern = f"{pattern}:*"
        search_pattern = f"{self.prefix}{workspace_id}:{pattern}"
        with self._lock:
            keys = [
                key for key in self._entries if fnmatch.fnmatchcase(key, search_pattern)
            ]
            for key in keys:
                self._entries.pop(key, None)
        return len(keys)

    def invalidate_all(self, workspace_id: str) -> int:
        """Invalidate all cache

        Args:
            workspace_id: Workspace ID

        Returns:
            Number of deleted keys
        """
        return self.invalidate(workspace_id, "*")

    def get_stats(self, workspace_id: str) -> dict[str, Any]:
        """Get cache statistics

        Args:
            workspace_id: Workspace ID

        Returns:
            Dictionary containing cache statistics
        """
        if not self.enabled:
            return {"enabled": False, "total_keys": 0, "memory_usage": 0}

        now = time.monotonic()
        prefix = f"{self.prefix}{workspace_id}:"
        with self._lock:
            self._discard_expired(now)
            entries = [
                (key, entry)
                for key, entry in self._entries.items()
                if key.startswith(prefix)
            ]
        return {
            "enabled": True,
            "total_keys": len(entries),
            "memory_usage": sum(
                len(key.encode("utf-8")) + len(entry.value.encode("utf-8"))
                for key, entry in entries
            ),
            "prefix": self.prefix,
        }

    def clear_all(self) -> int:
        """Clear all Git cache (dangerous operation)

        Returns:
            Number of deleted keys
        """
        if not self.enabled:
            return 0

        with self._lock:
            deleted = len(self._entries)
            self._entries.clear()
        return deleted

    def _discard_expired(self, now: float) -> None:
        for key, entry in list(self._entries.items()):
            if entry.expires_at <= now:
                self._entries.pop(key, None)


# Cache key constants
class CacheKeys:
    """Cache key name constants"""

    CHANGES = "changes"
    WORKING_TREE_SNAPSHOT = "working_tree_snapshot"
    STATUS = "status"
    BRANCHES = "branches"
    CONTEXT_PATH = "context_path"
    COMMITS = "commits"
    COMMIT_DETAIL = "commit_detail"
    COMMIT_FILES = "commit_files"
    DIFF = "diff"
    BLOB = "blob"


# Cache TTL constants (seconds)
class CacheTTL:
    """Cache TTL constants"""

    VERY_SHORT = 10  # 10 seconds - frequently changing data (e.g., changes, status)
    SHORT = 30  # 30 seconds - normal data
    MEDIUM = 300  # 5 minutes - relatively stable data (e.g., branches)
    LONG = 1800  # 30 minutes - rarely changing data (e.g., commit history)
    VERY_LONG = 3600  # 1 hour - almost static data (e.g., commit detail, blob)


class WorkspaceGitCacheEffects:
    """Workspace Git cache effect presets."""

    FILE_CONTENT = [
        CacheKeys.CHANGES,
        CacheKeys.STATUS,
        CacheKeys.WORKING_TREE_SNAPSHOT,
        CacheKeys.DIFF,
        CacheKeys.BLOB,
    ]
    LOCAL_MUTATION = FILE_CONTENT
    HISTORY_MUTATION = [
        CacheKeys.CHANGES,
        CacheKeys.STATUS,
        CacheKeys.WORKING_TREE_SNAPSHOT,
        CacheKeys.DIFF,
        CacheKeys.BLOB,
        CacheKeys.COMMITS,
    ]
    WORKING_TREE_SWITCH = [
        CacheKeys.CHANGES,
        CacheKeys.STATUS,
        CacheKeys.WORKING_TREE_SNAPSHOT,
        CacheKeys.BRANCHES,
        CacheKeys.COMMITS,
        CacheKeys.DIFF,
        CacheKeys.BLOB,
    ]
    INITIALIZE_REPOSITORY = [
        *WORKING_TREE_SWITCH,
        CacheKeys.CONTEXT_PATH,
    ]
    CLONE_REPOSITORY = INITIALIZE_REPOSITORY
    REMOTE_REF_MUTATION = [
        CacheKeys.STATUS,
        CacheKeys.WORKING_TREE_SNAPSHOT,
        CacheKeys.BRANCHES,
        CacheKeys.COMMITS,
    ]

    _BY_OPERATION = {
        "stage": LOCAL_MUTATION,
        "unstage": LOCAL_MUTATION,
        "discard": FILE_CONTENT,
        "commit": HISTORY_MUTATION,
        "checkout": WORKING_TREE_SWITCH,
        "clone_repository": CLONE_REPOSITORY,
        "initialize_repository": INITIALIZE_REPOSITORY,
        "pull": WORKING_TREE_SWITCH,
        "fetch": REMOTE_REF_MUTATION,
        "push": REMOTE_REF_MUTATION,
        "remote_settings": REMOTE_REF_MUTATION,
        "set_remote_settings": REMOTE_REF_MUTATION,
        "file_write": FILE_CONTENT,
    }

    @classmethod
    def for_operation(cls, operation_name: str) -> list[str]:
        return list(cls._BY_OPERATION.get(operation_name, []))


class GitCacheInvalidator:
    """Single invalidation entry point for workspace Git cache."""

    def __init__(self, cache: Optional[GitCache] = None) -> None:
        self._cache = cache

    def invalidate_effects(self, workspace_id: str, effects: list[str]) -> int:
        if self._cache is None:
            return 0

        deleted = 0
        seen: set[str] = set()
        for effect in effects:
            if effect in seen:
                continue
            seen.add(effect)
            deleted += self._cache.invalidate(workspace_id, effect)
        return deleted

    def invalidate_operation(self, workspace_id: str, operation_name: str) -> int:
        return self.invalidate_effects(
            workspace_id,
            WorkspaceGitCacheEffects.for_operation(operation_name),
        )


def create_git_cache(*, enabled: bool = True) -> GitCache:
    """Create a bounded process-local Git cache."""

    return GitCache(enabled=enabled)
