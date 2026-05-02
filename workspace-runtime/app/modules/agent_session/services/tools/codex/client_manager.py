"""Codex SDK client lifecycle management."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_app_server import AsyncCodex, AsyncThread, AsyncTurnHandle
from codex_app_server._version import __version__ as SDK_VERSION
from codex_app_server.client import AppServerConfig
from codex_app_server.generated.v2_all import GetAccountResponse, LoginAccountResponse

from app.database import async_session_scope
from app.modules.agent_session.repositories.agent_session_repository import (
    AgentSessionRepository,
)

from .approval_handler import CodexApprovalHandler, default_decline_response
from .permission_mapper import to_thread_resume_kwargs
from .sdk_compat import assert_sdk_structure

logger = logging.getLogger(__name__)

CODEX_BIN = "/home/developer/.npm-global/bin/codex"
CODEX_HOME = "/home/developer/.codex"
CODEX_SESSION_STATE_ROOT = "/home/developer/.codex-sessions"
CODEX_AUTH_METHOD_ENV = "CODEX_AUTH_METHOD"
CODEX_SYNCED_KEYS_ENV = "CODEX_SYNCED_KEYS"


class CodexAuthenticationRequiredError(RuntimeError):
    """Codex authentication is required before starting a session."""


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
                env=self._build_codex_env(session_id),
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
            if not await self._ensure_codex_auth(codex):
                await codex.close()
                raise CodexAuthenticationRequiredError("Codex CLI login is not available")

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

    async def _ensure_codex_auth(self, codex: AsyncCodex) -> bool:
        """Verify app-server can see the persisted CLI login or apply fallback tokens."""
        if os.environ.get(CODEX_AUTH_METHOD_ENV) == "apikey":
            synced_keys = self._synced_codex_env_keys()
            if any(os.environ.get(key) for key in synced_keys):
                logger.info("Codex API key authentication configured with synced environment variables")
                return True

        account = await self._read_account(codex)
        if account.account is not None:
            logger.info("Codex account available from persisted CLI login")
            return True

        token_payload = self._load_fallback_token_payload()
        if not token_payload:
            logger.info("Codex account not connected and no fallback tokens are configured")
            return False

        try:
            await codex._client.request(
                "account/login/start",
                token_payload,
                response_model=LoginAccountResponse,
            )
        except Exception as exc:
            logger.warning("Codex fallback token login failed: %s", exc)
            return False

        account = await self._read_account(codex)
        if account.account is None:
            logger.warning("Codex fallback token login did not produce an account")
            return False

        logger.info("Codex account available after fallback token login")
        return True

    async def _read_account(self, codex: AsyncCodex) -> GetAccountResponse:
        await codex._ensure_initialized()
        return await codex._client.request(
            "account/read",
            {"refreshToken": True},
            response_model=GetAccountResponse,
        )

    def _load_fallback_token_payload(self) -> dict[str, Any] | None:
        auth_path = Path(CODEX_HOME) / "auth.json"
        if not auth_path.is_file():
            return None

        try:
            auth_data = json.loads(auth_path.read_text())
        except Exception as exc:
            logger.warning("Failed to read Codex auth fallback file: %s", exc)
            return None

        tokens = auth_data.get("tokens") if isinstance(auth_data, dict) else None
        access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
        if not access_token:
            return None

        return {
            "type": "chatgptAuthTokens",
            "accessToken": access_token,
            "chatgptAccountId": auth_data.get("chatgpt_account_id") or "default",
            "chatgptPlanType": auth_data.get("chatgpt_plan_type"),
        }

    def _build_codex_env(self, session_id: str) -> dict[str, str]:
        env = {
            "CODEX_HOME": CODEX_HOME,
            "AILERON_CODEX_SESSION_STATE_DIR": f"{CODEX_SESSION_STATE_ROOT}/{session_id}",
        }
        for key in self._synced_codex_env_keys():
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
        model = os.environ.get("CODEX_MODEL")
        if model:
            env["CODEX_MODEL"] = model
        return env

    def _synced_codex_env_keys(self) -> list[str]:
        return [
            key.strip()
            for key in os.environ.get(CODEX_SYNCED_KEYS_ENV, "").split(",")
            if key.strip()
        ]

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
