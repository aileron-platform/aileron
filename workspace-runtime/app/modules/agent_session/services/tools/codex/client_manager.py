"""Codex SDK client lifecycle management."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from codex_app_server import AsyncCodex, AsyncThread, AsyncTurnHandle
from codex_app_server._version import __version__ as SDK_VERSION
from codex_app_server.client import AppServerConfig

from app.database import async_session_scope
from app.modules.agent_session.repositories.agent_session_repository import (
    AgentSessionRepository,
)

from .approval_handler import CodexApprovalHandler, default_decline_response
from .permission_mapper import to_thread_resume_kwargs
from .sdk_compat import assert_sdk_structure

logger = logging.getLogger(__name__)

CODEX_BIN = "/home/developer/.npm-global/bin/codex"
CODEX_HOME_ROOT = "/home/developer/.codex-sessions"


class CodexSessionApprovalDispatcher:
    """Stable SDK callback object whose current handler can be swapped."""

    def __init__(self) -> None:
        self._current: CodexApprovalHandler | None = None

    def set_current(self, handler: CodexApprovalHandler | None) -> None:
        self._current = handler

    def __call__(self, method: str, params: dict | None) -> dict[str, Any]:
        handler = self._current
        if handler is None:
            return default_decline_response(method)
        return handler.sync_approval_callback(method, params)


@dataclass(slots=True)
class SessionState:
    codex: AsyncCodex
    dispatcher: CodexSessionApprovalDispatcher
    thread: AsyncThread | None = None
    active_turn: AsyncTurnHandle | None = None


class CodexClientManager:
    """Create and reuse one Codex SDK process per agent session."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._map_lock = asyncio.Lock()
        self._structure_checked = False

    async def get_or_create(
        self,
        session_id: str,
        cwd: str,
        sdk_session_id: str | None = None,
        permission_config=None,
    ) -> SessionState:
        if not self._structure_checked:
            assert_sdk_structure()
            self._structure_checked = True

        async with self._map_lock:
            existing = self._sessions.get(session_id)
            if existing:
                return existing
            session_lock = self._session_locks.setdefault(session_id, asyncio.Lock())

        async with session_lock:
            async with self._map_lock:
                existing = self._sessions.get(session_id)
                if existing:
                    return existing

            dispatcher = CodexSessionApprovalDispatcher()
            config = AppServerConfig(
                codex_bin=CODEX_BIN,
                cwd=cwd,
                env={"CODEX_HOME": f"{CODEX_HOME_ROOT}/{session_id}"},
            )
            codex = AsyncCodex(config=config)
            codex._client._sync._approval_handler = dispatcher
            if codex._client._sync._approval_handler is not dispatcher:
                raise RuntimeError("Codex approval handler patch did not stick")

            state = SessionState(codex=codex, dispatcher=dispatcher)
            if sdk_session_id:
                try:
                    state.thread = await codex.thread_resume(
                        sdk_session_id,
                        **to_thread_resume_kwargs(permission_config, cwd),
                    )
                except Exception as exc:
                    logger.warning(
                        "Codex thread_resume failed session=%s: %s",
                        session_id[:8],
                        exc,
                    )
                    await self._clear_persisted_thread_id(session_id)

            await self._log_server_version(codex)

            async with self._map_lock:
                self._sessions[session_id] = state
            return state

    async def _log_server_version(self, codex: AsyncCodex) -> None:
        try:
            await codex._ensure_initialized()
            version = codex.metadata.serverInfo.version if codex.metadata.serverInfo else None
            logger.info("Codex app-server version=%s", version)
            if version and ".".join(version.split(".")[:2]) != ".".join(SDK_VERSION.split(".")[:2]):
                logger.warning(
                    "Codex SDK/server version mismatch sdk=%s server=%s",
                    SDK_VERSION,
                    version,
                )
        except Exception:
            await codex.close()
            raise

    async def _clear_persisted_thread_id(self, session_id: str) -> None:
        async with async_session_scope() as db:
            repo = AgentSessionRepository(db)
            await repo.clear_sdk_session_id(session_id)

    async def get_state(self, session_id: str) -> SessionState | None:
        async with self._map_lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        async with self._map_lock:
            state = self._sessions.pop(session_id, None)
            self._session_locks.pop(session_id, None)
        if state:
            await state.codex.close()


_manager: CodexClientManager | None = None


def get_codex_client_manager() -> CodexClientManager:
    """Return the process-wide Codex client manager."""
    global _manager
    if _manager is None:
        _manager = CodexClientManager()
    return _manager
