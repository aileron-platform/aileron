"""Authoritative Codex app-server client for lifecycle hook trust metadata."""

from __future__ import annotations

import json
import selectors
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.modules.cli_settings.cache import ProcessTTLCache


@dataclass(frozen=True)
class CodexAuthoritativeHook:
    """One unmanaged plugin command hook returned by ``hooks/list``."""

    plugin_id: str
    source_path: Path
    key: str
    current_hash: str
    enabled: bool
    trust_status: str


_hooks_cache: ProcessTTLCache[
    tuple[str, str, float],
    tuple[CodexAuthoritativeHook, ...],
] = ProcessTTLCache()


class CodexHooksListClient:
    """Query hook keys and hashes from Codex instead of reproducing internals."""

    def __init__(
        self,
        *,
        executable: str = "codex",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def list_hooks(self, cwd: Path) -> tuple[CodexAuthoritativeHook, ...]:
        """Return strictly validated plugin command hook metadata."""

        key = (
            self._executable,
            str(cwd.resolve(strict=False)),
            self._timeout_seconds,
        )
        return _hooks_cache.get_or_load(key, lambda: self._list_hooks_uncached(cwd))

    def _list_hooks_uncached(
        self,
        cwd: Path,
    ) -> tuple[CodexAuthoritativeHook, ...]:
        """Execute one authoritative hook discovery."""

        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                [self._executable, "app-server", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                cwd=cwd,
            )
            self._send(
                process,
                {
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "clientInfo": {
                            "name": "aileron_runtime",
                            "title": "Aileron Runtime",
                            "version": "1",
                        }
                    },
                },
            )
            initialized = self._read_response(process, request_id=1)
            if not isinstance(initialized.get("result"), dict):
                raise ValueError("Codex app-server initialization failed")
            self._send(process, {"method": "initialized"})
            self._send(
                process,
                {
                    "method": "hooks/list",
                    "id": 2,
                    "params": {"cwds": [str(cwd.resolve(strict=False))]},
                },
            )
            response = self._read_response(process, request_id=2)
            return self._parse_response(response)
        except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"errorCode": "marketplace.settings.plugin_hook_trust_invalid"},
            ) from exc
        finally:
            if process is not None:
                with suppress(OSError, subprocess.SubprocessError):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=1)

    @staticmethod
    def _send(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise ValueError("Codex app-server stdin is unavailable")
        process.stdin.write(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        process.stdin.flush()

    def _read_response(
        self,
        process: subprocess.Popen[str],
        *,
        request_id: int,
    ) -> dict[str, Any]:
        if process.stdout is None:
            raise ValueError("Codex app-server stdout is unavailable")
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + self._timeout_seconds
        try:
            while time.monotonic() < deadline:
                remaining = max(0.0, deadline - time.monotonic())
                if not selector.select(remaining):
                    break
                line = process.stdout.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError("Codex app-server returned invalid JSON") from exc
                if not isinstance(message, dict) or message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise ValueError("Codex app-server request failed")
                return message
        finally:
            selector.close()
        raise ValueError("Codex app-server request timed out")

    @staticmethod
    def _parse_response(
        response: dict[str, Any],
    ) -> tuple[CodexAuthoritativeHook, ...]:
        result = response.get("result")
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError("Codex hooks/list response is invalid")
        entry = data[0]
        if not isinstance(entry, dict):
            raise ValueError("Codex hooks/list entry is invalid")
        if entry.get("errors") not in ([], None):
            raise ValueError("Codex hooks/list reported discovery errors")
        raw_hooks = entry.get("hooks")
        if not isinstance(raw_hooks, list):
            raise ValueError("Codex hooks/list hooks are invalid")
        hooks: list[CodexAuthoritativeHook] = []
        for raw in raw_hooks:
            if (
                not isinstance(raw, dict)
                or raw.get("source") != "plugin"
                or raw.get("handlerType") != "command"
                or raw.get("isManaged") is not False
            ):
                continue
            plugin_id = raw.get("pluginId")
            source_path = raw.get("sourcePath")
            key = raw.get("key")
            current_hash = raw.get("currentHash")
            trust_status = raw.get("trustStatus")
            if (
                not isinstance(plugin_id, str)
                or not plugin_id
                or not isinstance(source_path, str)
                or not Path(source_path).is_absolute()
                or not isinstance(key, str)
                or not key
                or not isinstance(current_hash, str)
                or not current_hash.startswith("sha256:")
                or trust_status not in {"trusted", "untrusted", "modified"}
                or not isinstance(raw.get("enabled"), bool)
            ):
                raise ValueError("Codex plugin hook metadata is invalid")
            hooks.append(
                CodexAuthoritativeHook(
                    plugin_id=plugin_id,
                    source_path=Path(source_path).resolve(strict=False),
                    key=key,
                    current_hash=current_hash,
                    enabled=raw["enabled"],
                    trust_status=trust_status,
                )
            )
        return tuple(sorted(hooks, key=lambda item: item.key))


def clear_codex_hooks_cache(cwd: Path | None = None) -> None:
    """Clear completed Codex app-server hook discovery results."""

    if cwd is None:
        _hooks_cache.clear()
        return
    identity = str(cwd.resolve(strict=False))
    _hooks_cache.clear(lambda key: key[1] == identity)
