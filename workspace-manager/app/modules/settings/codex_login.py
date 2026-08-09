"""Manager-owned Codex login orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CodexLoginError(RuntimeError):
    """Codex login failure with an i18n-compatible error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class CodexLoginSession:
    user_id: str
    login_id: str
    codex_bin: str
    codex_home: Path
    process: asyncio.subprocess.Process
    stderr_task: asyncio.Task[None]


class CodexAppServerClient:
    """Small async JSON-RPC client for Codex app-server login calls."""

    def __init__(self, *, codex_bin: str, codex_home: Path) -> None:
        self.codex_bin = codex_bin
        self.codex_home = codex_home
        self.process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.codex_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.codex_home.chmod(0o700)
        self.process = await asyncio.create_subprocess_exec(
            self.codex_bin,
            "app-server",
            "--listen",
            "stdio://",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
            env={**os.environ, "CODEX_HOME": str(self.codex_home)},
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        await self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "aileron_workspace_manager",
                    "title": "Aileron Workspace Manager",
                    "version": "1.0.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await self.notify("initialized", None)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
        ):
            raise CodexLoginError(
                "codex_login_service_unavailable", "Codex app-server is not running"
            )

        request_id = str(uuid.uuid4())
        payload = {"id": request_id, "method": method, "params": params or {}}
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise CodexLoginError(
                    "codex_login_service_unavailable", "Codex app-server closed stdout"
                )
            message = json.loads(line.decode("utf-8"))
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                raise CodexLoginError(
                    "codex_login_provider_error",
                    (
                        error.get("message", "Codex app-server request failed")
                        if isinstance(error, dict)
                        else str(error)
                    ),
                )
            return message.get("result")

    async def notify(self, method: str, params: dict[str, Any] | None) -> None:
        if self.process is None or self.process.stdin is None:
            raise CodexLoginError(
                "codex_login_service_unavailable", "Codex app-server is not running"
            )
        self.process.stdin.write(
            (json.dumps({"method": method, "params": params or {}}) + "\n").encode(
                "utf-8"
            )
        )
        await self.process.stdin.drain()

    async def close(self) -> None:
        if self.process is None:
            return
        process = self.process
        self.process = None
        if process.stdin:
            process.stdin.close()
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        if self._stderr_task:
            self._stderr_task.cancel()

    async def _drain_stderr(self) -> None:
        if self.process is None or self.process.stderr is None:
            return
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return
            logger.debug(
                "Codex app-server stderr: %s",
                line.decode("utf-8", errors="replace").strip(),
            )


class CodexLoginService:
    """Owns Codex login sessions for workspace-manager."""

    def __init__(self) -> None:
        settings = get_settings()
        self.codex_bin_setting = settings.CODEX_BIN
        self.state_root = Path(settings.CODEX_MANAGER_STATE_DIR)
        self._sessions: dict[str, CodexLoginSession] = {}
        self._lock = asyncio.Lock()

    async def start_login(self, user_id: str) -> dict[str, str]:
        async with self._lock:
            await self._close_user_sessions(user_id)
            login_flow_id = str(uuid.uuid4())
            codex_home = self.state_root / user_id / login_flow_id
            codex_bin = self._resolve_codex_bin(self.codex_bin_setting)
            client = CodexAppServerClient(
                codex_bin=codex_bin,
                codex_home=codex_home,
            )
            try:
                await client.start()
                result = await client.request(
                    "account/login/start", {"type": "chatgptDeviceCode"}
                )
            except CodexLoginError:
                await client.close()
                raise
            except Exception as exc:
                await client.close()
                raise CodexLoginError(
                    "codex_login_service_unavailable", str(exc)
                ) from exc

            login_id = self._extract_login_id(result)
            self._sessions[login_id] = CodexLoginSession(
                user_id=user_id,
                login_id=login_id,
                codex_bin=codex_bin,
                codex_home=codex_home,
                process=client.process,  # type: ignore[arg-type]
                stderr_task=client._stderr_task,  # type: ignore[arg-type]
            )
            client.process = None
            client._stderr_task = None
            logger.info("Started manager-owned Codex login for user %s", user_id)
            return {
                "loginId": login_id,
                "verificationUrl": self._extract_string(
                    result, "verificationUrl", "verification_url"
                ),
                "userCode": self._extract_string(result, "userCode", "user_code"),
                "type": self._extract_string(result, "type") or "chatgptDeviceCode",
            }

    async def get_status(
        self, user_id: str, login_id: str | None = None
    ) -> dict[str, Any]:
        session = self._find_session(user_id, login_id)
        if session:
            client = self._client_from_session(session)
            try:
                result = await client.request("account/read", {"refreshToken": True})
            except CodexLoginError:
                raise
            except Exception as exc:
                raise CodexLoginError("codex_login_status_failed", str(exc)) from exc
            account = self._extract_account(result)
            if account:
                await self._close_session(session.login_id)
                return {
                    "loginStatus": "connected",
                    "account": account,
                    "cliState": self.read_cli_state(session.codex_home),
                }
            return {"loginStatus": "pending", "account": None}

        cli_state = self._read_latest_user_cli_state(user_id)
        if cli_state.get("authJson"):
            return {"loginStatus": "connected", "account": None, "cliState": cli_state}
        return {"loginStatus": "notConnected", "account": None}

    async def cancel_login(self, user_id: str, login_id: str | None) -> dict[str, str]:
        session = self._find_session(user_id, login_id)
        if not session:
            return {"status": "notFound"}
        client = self._client_from_session(session)
        try:
            await client.request("account/login/cancel", {"loginId": session.login_id})
        except Exception as exc:
            logger.info("Codex login cancel returned non-fatal error: %s", exc)
        await self._close_session(session.login_id)
        return {"status": "canceled"}

    async def logout(self, user_id: str) -> None:
        async with self._lock:
            await self._close_user_sessions(user_id)
            user_root = self.state_root / user_id
            if user_root.exists():
                shutil.rmtree(user_root)

    @staticmethod
    def read_cli_state(codex_home: Path) -> dict[str, Any]:
        cli_state: dict[str, Any] = {}
        auth_path = codex_home / "auth.json"
        if auth_path.is_file():
            auth_json = json.loads(auth_path.read_text())
            if isinstance(auth_json, dict):
                cli_state["authJson"] = auth_json
        config_path = codex_home / "config.toml"
        if config_path.is_file():
            cli_state["configToml"] = config_path.read_text()
        installation_path = codex_home / "installation_id"
        if installation_path.is_file():
            cli_state["installationId"] = installation_path.read_text().strip()
        return cli_state

    async def _close_user_sessions(self, user_id: str) -> None:
        for login_id, session in list(self._sessions.items()):
            if session.user_id == user_id:
                await self._close_session(login_id)

    async def _close_session(self, login_id: str) -> None:
        session = self._sessions.pop(login_id, None)
        if not session:
            return
        client = self._client_from_session(session)
        await client.close()

    def _find_session(
        self, user_id: str, login_id: str | None
    ) -> CodexLoginSession | None:
        if login_id:
            session = self._sessions.get(login_id)
            if session and session.user_id == user_id:
                return session
            return None
        for session in self._sessions.values():
            if session.user_id == user_id:
                return session
        return None

    def _client_from_session(self, session: CodexLoginSession) -> CodexAppServerClient:
        client = CodexAppServerClient(
            codex_bin=session.codex_bin,
            codex_home=session.codex_home,
        )
        client.process = session.process
        client._stderr_task = session.stderr_task
        return client

    def _read_latest_user_cli_state(self, user_id: str) -> dict[str, Any]:
        user_root = self.state_root / user_id
        if not user_root.is_dir():
            return {}
        homes = sorted(
            (path for path in user_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for home in homes:
            cli_state = self.read_cli_state(home)
            if cli_state:
                return cli_state
        return {}

    @staticmethod
    def _resolve_codex_bin(codex_bin: str) -> str:
        if "/" not in codex_bin:
            resolved = shutil.which(codex_bin)
            if resolved:
                return resolved
            raise CodexLoginError(
                "codex_login_service_unavailable", "Codex binary is not available"
            )
        if not Path(codex_bin).exists():
            raise CodexLoginError(
                "codex_login_service_unavailable", "Codex binary is not available"
            )
        return codex_bin

    @staticmethod
    def _extract_login_id(result: Any) -> str:
        login_id = CodexLoginService._extract_string(result, "loginId", "login_id")
        if not login_id:
            raise CodexLoginError(
                "codex_login_provider_error",
                "Codex login response did not include loginId",
            )
        return login_id

    @staticmethod
    def _extract_string(result: Any, *keys: str) -> str:
        if isinstance(result, dict):
            candidates = [result]
            if isinstance(result.get("root"), dict):
                candidates.insert(0, result["root"])
            for candidate in candidates:
                for key in keys:
                    value = candidate.get(key)
                    if isinstance(value, str):
                        return value
        return ""

    @staticmethod
    def _extract_account(result: Any) -> dict[str, Any] | None:
        if not isinstance(result, dict):
            return None
        account = result.get("account")
        if isinstance(account, dict) and isinstance(account.get("root"), dict):
            account = account["root"]
        if not isinstance(account, dict):
            return None
        account_type = account.get("type")
        if account_type != "chatgpt":
            return {"type": account_type}
        plan_type = account.get("planType") or account.get("plan_type")
        if isinstance(plan_type, dict):
            plan_type = plan_type.get("value")
        return {
            "email": account.get("email"),
            "planType": plan_type,
            "accountId": account.get("accountId") or account.get("account_id"),
        }


_codex_login_service: CodexLoginService | None = None


def get_codex_login_service() -> CodexLoginService:
    global _codex_login_service
    if _codex_login_service is None:
        _codex_login_service = CodexLoginService()
    return _codex_login_service
