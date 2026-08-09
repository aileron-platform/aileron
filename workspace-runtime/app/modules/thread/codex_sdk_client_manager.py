from __future__ import annotations

import time
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai_codex import (
    ApprovalMode,
    AsyncCodex,
    ImageInput,
    LocalImageInput,
    Sandbox,
    TextInput,
)
from openai_codex.client import CodexConfig

from app.modules.cli_settings.user_scope.paths import get_codex_path_resolver
from app.modules.thread.mcp.agent_policy import AILERON_MCP_POLICY_PROMPT
from app.modules.thread.mcp.config import (
    codex_aileron_mcp_thread_config,
    codex_aileron_mcp_config_overrides,
)


CODEX_AILERON_MCP_PROMPT = AILERON_MCP_POLICY_PROMPT


@dataclass(slots=True)
class CodexThreadState:
    codex: Any
    thread: Any | None = None
    codex_thread_id: str | None = None
    active_turn: Any | None = None
    active_execution_id: str | None = None
    last_used_at: float = 0.0


@dataclass(slots=True)
class CodexTurnStart:
    codex: Any
    thread: Any
    turn: Any
    codex_thread_id: str


class CodexSdkClientManager:
    """Manage Codex SDK app-server state keyed by Aileron thread id."""

    def __init__(
        self,
        *,
        codex_factory: Callable[[], Any] | None = None,
        codex_bin: str | None = None,
        codex_home: str | None = None,
        idle_ttl_seconds: int = 900,
    ) -> None:
        self._codex_factory = codex_factory
        self._codex_bin = codex_bin or shutil.which("codex") or "codex"
        self._codex_home = codex_home or str(get_codex_path_resolver().codex_home)
        self._idle_ttl_seconds = idle_ttl_seconds
        self._states: dict[str, CodexThreadState] = {}
        self._execution_to_thread: dict[str, str] = {}
        self._reserved: set[str] = set()

    def reserve(self) -> str:
        execution_id = str(uuid4())
        self._reserved.add(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self._reserved.add(execution_id)

    async def start_turn(
        self,
        *,
        thread_id: str,
        execution_id: str,
        prompt: str,
        attachments: list[dict[str, Any]],
        cwd: str,
        resume_session_id: str | None,
        model: str | None,
        now: float | None = None,
    ) -> CodexTurnStart:
        if execution_id not in self._reserved:
            raise ValueError("execution_not_reserved")
        state = self._states.get(thread_id)
        if state is None:
            state = CodexThreadState(codex=self._create_codex(cwd))
            self._states[thread_id] = state

        if state.thread is None:
            if resume_session_id:
                state.thread = await state.codex.thread_resume(
                    resume_session_id,
                    cwd=cwd,
                    sandbox=Sandbox.full_access,
                    approval_mode=ApprovalMode.deny_all,
                    model=model,
                    config=codex_aileron_mcp_thread_config(),
                    developer_instructions=CODEX_AILERON_MCP_PROMPT,
                )
            else:
                state.thread = await state.codex.thread_start(
                    cwd=cwd,
                    sandbox=Sandbox.full_access,
                    approval_mode=ApprovalMode.deny_all,
                    model=model,
                    config=codex_aileron_mcp_thread_config(),
                    developer_instructions=CODEX_AILERON_MCP_PROMPT,
                )
            state.codex_thread_id = state.thread.id

        turn = await state.thread.turn(
            self._run_input(prompt, attachments),
            cwd=cwd,
            sandbox=Sandbox.full_access,
            approval_mode=ApprovalMode.deny_all,
            model=model,
        )
        state.active_turn = turn
        state.active_execution_id = execution_id
        state.last_used_at = time.monotonic() if now is None else now
        self._execution_to_thread[execution_id] = thread_id
        self._reserved.discard(execution_id)
        return CodexTurnStart(
            codex=state.codex,
            thread=state.thread,
            turn=turn,
            codex_thread_id=str(state.codex_thread_id),
        )

    async def stop_execution(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        state = self._state_for_execution(execution_id)
        if state and state.active_turn is not None:
            await state.active_turn.interrupt()

    def is_alive(self, execution_id: str) -> bool:
        if execution_id in self._reserved:
            return True
        state = self._state_for_execution(execution_id)
        return bool(state and state.active_execution_id == execution_id)

    async def finish_execution(
        self,
        execution_id: str,
        *,
        now: float | None = None,
    ) -> None:
        self._reserved.discard(execution_id)
        thread_id = self._execution_to_thread.pop(execution_id, None)
        if thread_id is None:
            return
        state = self._states.get(thread_id)
        if state and state.active_execution_id == execution_id:
            state.active_execution_id = None
            state.active_turn = None
            state.last_used_at = time.monotonic() if now is None else now

    async def destroy_thread(self, thread_id: str) -> None:
        state = self._states.pop(thread_id, None)
        if state is None:
            return
        for execution_id, mapped_thread_id in list(self._execution_to_thread.items()):
            if mapped_thread_id == thread_id:
                self._execution_to_thread.pop(execution_id, None)
                self._reserved.discard(execution_id)
        await state.codex.close()

    async def evict_idle(self, *, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        evicted = 0
        for thread_id, state in list(self._states.items()):
            if state.active_execution_id is not None:
                continue
            if current - state.last_used_at < self._idle_ttl_seconds:
                continue
            await self.destroy_thread(thread_id)
            evicted += 1
        return evicted

    def _create_codex(self, cwd: str) -> Any:
        if self._codex_factory is not None:
            return self._codex_factory()
        return AsyncCodex(
            config=CodexConfig(
                codex_bin=self._codex_bin,
                config_overrides=codex_aileron_mcp_config_overrides(),
                cwd=cwd,
                env={
                    "CODEX_HOME": self._codex_home,
                    "AILERON_CODEX_SESSION_STATE_DIR": str(
                        Path(self._codex_home) / ".aileron-sdk-sessions"
                    ),
                },
            )
        )

    def _run_input(self, prompt: str, attachments: list[dict[str, Any]]) -> list[Any]:
        items: list[Any] = [TextInput(prompt)]
        for attachment in attachments:
            path = str(attachment.get("path") or "")
            if not path:
                continue
            mime_type = str(attachment.get("mimeType") or "")
            name = str(attachment.get("name") or Path(path).name)
            if mime_type.startswith("image/"):
                if path.startswith(("http://", "https://")):
                    items.append(ImageInput(path))
                else:
                    items.append(LocalImageInput(path))
                continue
            items.append(TextInput(f"Attached file: {name} ({path})"))
        return items

    def _state_for_execution(self, execution_id: str) -> CodexThreadState | None:
        thread_id = self._execution_to_thread.get(execution_id)
        return self._states.get(thread_id) if thread_id else None
