"""Provider mutation locks and user-copy state helpers."""

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
    """Shared provider mutation lock and one-shot user-copy recovery root."""

    def __init__(self, root: Path, *, lock_timeout_seconds: float = 10.0) -> None:
        self.root = root
        self.locks_root = root / "locks"
        self.lock_timeout_seconds = lock_timeout_seconds

    def ensure(self) -> None:
        for path in (self.root, self.locks_root):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise MarketplaceOperationError(
                    "marketplace.install.provider_state_not_isolated",
                    http_status=503,
                )
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(path, 0o700)

    @property
    def provider_state_root_id(self) -> str:
        """Return the opaque identity used by the user-copy stale-plan proof."""

        self.ensure()
        identity_path = self.root / "identity.json"
        if identity_path.is_symlink():
            raise MarketplaceOperationError(
                "marketplace.install.provider_state_not_isolated",
                http_status=503,
            )
        if identity_path.exists():
            return self._read_provider_state_root_id(identity_path)
        root_id = f"psr_{secrets.token_hex(32)}"
        temporary = identity_path.with_name(
            f".{identity_path.name}.{secrets.token_hex(8)}.tmp"
        )
        payload = {
            "identityVersion": 1,
            "providerStateRootId": root_id,
        }
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                )
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, identity_path)
            except FileExistsError:
                return self._read_provider_state_root_id(identity_path)
            os.chmod(identity_path, 0o600)
            fsync_directory(identity_path.parent)
            return root_id
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def provider_lock(
        self,
        *,
        provider: str,
    ) -> Iterator[None]:
        """Serialize all provider settings and CLI mutations."""

        if provider not in {"claude-code", "codex"}:
            raise MarketplaceOperationError(
                "marketplace.install.provider_invalid",
                http_status=422,
            )
        self.ensure()
        key = f"provider:{provider}"
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
                "marketplace.install.provider_state_not_isolated",
                http_status=503,
            ) from exc
        if not isinstance(value, dict):
            raise MarketplaceOperationError(
                "marketplace.install.provider_state_not_isolated",
                http_status=503,
            )
        return value

    @classmethod
    def _read_provider_state_root_id(cls, path: Path) -> str:
        identity = cls._read_json(path)
        root_id = identity.get("providerStateRootId")
        if (
            identity.get("identityVersion") == 1
            and isinstance(root_id, str)
            and root_id.startswith("psr_")
            and len(root_id) == 68
            and all(
                character in "0123456789abcdef"
                for character in root_id.removeprefix("psr_")
            )
        ):
            return root_id
        raise MarketplaceOperationError(
            "marketplace.install.provider_state_not_isolated",
            http_status=503,
        )


__all__ = [
    "MarketplaceMutationStore",
    "canonical_digest",
    "fsync_directory",
    "write_json_atomic",
]
