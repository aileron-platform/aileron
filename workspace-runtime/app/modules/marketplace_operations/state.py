"""Target client mutation locks and user-copy state helpers."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import time
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator, Mapping

from .errors import MarketplaceOperationError


def canonical_digest(value: Mapping[str, Any]) -> str:
    """Hash one JSON-safe value with stable ordering."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def fsync_directory(path: Path) -> None:
    """Persist one directory entry update."""

    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    """Write a private JSON document through an atomic rename."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class MarketplaceMutationStore:
    """Shared target_client mutation lock and one-shot user-copy recovery root."""

    def __init__(self, root: Path, *, lock_timeout_seconds: float = 10.0) -> None:
        self.root = root
        self.locks_root = root / "locks"
        self.lock_timeout_seconds = lock_timeout_seconds

    def ensure(self) -> None:
        for path in (self.root, self.locks_root):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise MarketplaceOperationError(
                    "marketplace.install.target_client_state_not_isolated",
                    http_status=503,
                )
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(path, 0o700)

    @contextmanager
    def target_client_lock(
        self,
        *,
        target_client: str,
    ) -> Iterator[None]:
        """Serialize all target_client settings and CLI mutations."""

        if target_client not in {"claude-code", "codex"}:
            raise MarketplaceOperationError(
                "marketplace.install.target_client_invalid",
                http_status=422,
            )
        self.ensure()
        key = f"target_client:{target_client}"
        lock_path = self.locks_root / (
            f"{sha256(key.encode('utf-8')).hexdigest()}.lock"
        )
        handle = lock_path.open("a+", encoding="utf-8")
        os.chmod(lock_path, 0o600)
        try:
            deadline = time.monotonic() + self.lock_timeout_seconds
            while True:
                try:
                    fcntl.flock(
                        handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise MarketplaceOperationError(
                            "marketplace.install.lock_timeout",
                            http_status=409,
                        )
                    time.sleep(0.05)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketplaceOperationError(
                "marketplace.install.target_client_state_not_isolated",
                http_status=503,
            ) from exc
        if not isinstance(value, dict):
            raise MarketplaceOperationError(
                "marketplace.install.target_client_state_not_isolated",
                http_status=503,
            )
        return value

__all__ = [
    "MarketplaceMutationStore",
    "canonical_digest",
    "fsync_directory",
    "write_json_atomic",
]
