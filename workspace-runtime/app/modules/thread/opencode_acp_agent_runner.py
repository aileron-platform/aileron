from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from acp import PROTOCOL_VERSION
from acp import RequestError
from acp import spawn_agent_process
from acp.helpers import text_block
from acp.schema import (
    AllowedOutcome,
    ClientCapabilities,
    CreateTerminalResponse,
    DeniedOutcome,
    FileSystemCapability,
    Implementation,
    ReadTextFileResponse,
    RequestPermissionResponse,
    TerminalExitStatus,
    TerminalOutputResponse,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from app.modules.thread.mcp.agent_policy import AILERON_OPENCODE_POLICY_PROMPT
from app.modules.thread.mcp.config import acp_aileron_mcp_servers
from app.modules.thread.opencode_acp_event_mapper import OpenCodeAcpEventMapper
from app.modules.thread.execution import AgentEvent
from app.modules.thread.execution import AgentExecutionRequest
from app.modules.version_control.repository import GitUtils
from app.modules.version_control.worktree_config import get_worktree_subdir

EventCallback = Callable[[AgentEvent], Awaitable[None] | None]
CwdResolver = Callable[[str | None], Path | str]
SpawnAgent = Callable[..., Any]


@dataclass
class TerminalState:
    process: asyncio.subprocess.Process
    output_byte_limit: int | None = None
    output: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    wait_task: asyncio.Task[None] | None = None


class OpenCodeAcpClient:
    """ACP client callbacks used by OpenCode."""

    def __init__(
        self,
        *,
        cwd: Path,
        permission_mode: str | None,
        on_event: EventCallback,
    ) -> None:
        self.cwd = cwd.resolve()
        self.permission_mode = permission_mode
        self.on_event = on_event
        self._terminal_counter = 0
        self._terminals: dict[str, TerminalState] = {}
        self.mapper: OpenCodeAcpEventMapper | None = None

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        if self.mapper is None:
            return None
        for event in self.mapper.map_session_update(update, session_id=session_id):
            await self._emit(event)
        return None

    async def request_permission(
        self,
        options: list[Any],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        del tool_call
        allow = self.permission_mode is None or self.permission_mode in {
            "bypassPermissions",
            "allow",
            "allow_once",
        }
        chosen = (
            self._option_id(options, {"allow_once", "allow_always"}) if allow else None
        )
        if chosen is None and not allow:
            chosen = self._option_id(options, {"reject_once", "reject_always"})
        if chosen is None and options:
            chosen = getattr(options[0], "option_id", None)
        if chosen is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=chosen)
        )

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        resolved = self._resolve_workspace_path(path)
        content = resolved.read_text(encoding="utf-8")
        if line is not None:
            lines = content.splitlines()
            content = "\n".join(lines[max(line - 1, 0) :])
        if limit is not None:
            content = "\n".join(content.splitlines()[:limit])
        return ReadTextFileResponse(content=content)

    async def write_text_file(
        self,
        content: str,
        path: str,
        session_id: str,
        **kwargs: Any,
    ) -> WriteTextFileResponse:
        resolved = self._resolve_workspace_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return WriteTextFileResponse()

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: Any = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        self._terminal_counter += 1
        terminal_id = f"opencode-term-{self._terminal_counter}"
        terminal_cwd = self._resolve_workspace_path(cwd) if cwd else self.cwd
        process = await asyncio.create_subprocess_exec(
            command,
            *(args or []),
            cwd=terminal_cwd,
            env={**os.environ, **self._env_mapping(env)},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        state = TerminalState(
            process=process,
            output_byte_limit=output_byte_limit,
        )
        state.wait_task = asyncio.create_task(
            self._collect_terminal_output(state),
            name=f"opencode-acp-terminal:{terminal_id}",
        )
        self._terminals[terminal_id] = state
        return CreateTerminalResponse(terminal_id=terminal_id)

    async def terminal_output(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> TerminalOutputResponse:
        state = self._terminal(terminal_id)
        exit_status = (
            TerminalExitStatus(exit_code=state.process.returncode)
            if state.process.returncode is not None
            else None
        )
        return TerminalOutputResponse(
            output=bytes(state.output).decode("utf-8", "replace"),
            truncated=state.truncated,
            exit_status=exit_status,
        )

    async def wait_for_terminal_exit(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> WaitForTerminalExitResponse:
        state = self._terminal(terminal_id)
        if state.wait_task is not None:
            await state.wait_task
        exit_code = state.process.returncode
        if exit_code is None:
            exit_code = await state.process.wait()
        return WaitForTerminalExitResponse(exit_code=exit_code)

    async def release_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> None:
        state = self._terminals.pop(terminal_id, None)
        if state is not None and state.process.returncode is None:
            state.process.terminate()
            await state.process.wait()

    async def kill_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> None:
        state = self._terminal(terminal_id)
        if state.process.returncode is None:
            state.process.kill()
            await state.process.wait()
        if state.wait_task is not None:
            await state.wait_task

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None

    def on_connect(self, conn: Any) -> None:
        del conn
        return None

    async def _emit(self, event: AgentEvent) -> None:
        result = self.on_event(event)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _option_id(options: list[Any], kinds: set[str]) -> str | None:
        for option in options:
            kind = getattr(getattr(option, "kind", None), "value", None)
            kind = kind or str(getattr(option, "kind", "") or "")
            if kind in kinds:
                value = getattr(option, "option_id", None)
                return str(value) if value is not None else None
        return None

    def _resolve_workspace_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.cwd / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.cwd):
            raise PermissionError("path_outside_workspace")
        return resolved

    def _terminal(self, terminal_id: str) -> TerminalState:
        state = self._terminals.get(terminal_id)
        if state is None:
            raise KeyError(f"terminal_not_found:{terminal_id}")
        return state

    @staticmethod
    def _env_mapping(env: Any) -> dict[str, str]:
        if env is None:
            return {}
        if isinstance(env, dict):
            return {str(key): str(value) for key, value in env.items()}
        values: dict[str, str] = {}
        for item in env:
            name = getattr(item, "name", None)
            value = getattr(item, "value", None)
            if name is not None and value is not None:
                values[str(name)] = str(value)
        return values

    @staticmethod
    async def _collect_terminal_output(state: TerminalState) -> None:
        assert state.process.stdout is not None
        while chunk := await state.process.stdout.read(4096):
            if state.output_byte_limit is None:
                state.output.extend(chunk)
                continue
            remaining = state.output_byte_limit - len(state.output)
            if remaining > 0:
                state.output.extend(chunk[:remaining])
            if len(chunk) > remaining:
                state.truncated = True
        await state.process.wait()


class OpenCodeAcpAgentRunner:
    """Run OpenCode turns through the ACP protocol."""

    def __init__(
        self,
        *,
        workspace_id: str,
        spawn_agent: SpawnAgent | None = None,
        cwd_resolver: CwdResolver | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self._spawn_agent = spawn_agent or spawn_agent_process
        self._cwd_resolver = cwd_resolver or self._resolve_cwd
        self._reserved: set[str] = set()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._connections: dict[str, Any] = {}
        self._sessions: dict[str, str] = {}
        self._execution_threads: dict[str, str] = {}

    def reserve(self) -> str:
        execution_id = str(uuid4())
        self._reserved.add(execution_id)
        return execution_id

    def adopt_reservation(self, execution_id: str) -> None:
        self._reserved.add(execution_id)

    async def start(
        self,
        request: AgentExecutionRequest,
        on_event: EventCallback,
        execution_id: str,
    ) -> None:
        if execution_id not in self._reserved:
            raise ValueError("execution_not_reserved")
        self._reserved.discard(execution_id)
        self._execution_threads[execution_id] = request.thread_id
        cwd = str(self._cwd_resolver(request.git_context_id))
        task = asyncio.create_task(
            self._run_turn(
                execution_id=execution_id,
                request=request,
                cwd=cwd,
                on_event=on_event,
            ),
            name=f"opencode-acp-runner:{execution_id}",
        )
        self._tasks[execution_id] = task

        def discard_completed(completed: asyncio.Task[None]) -> None:
            self._discard_task(execution_id, completed)

        task.add_done_callback(discard_completed)

    async def stop(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        connection = self._connections.get(execution_id)
        session_id = self._sessions.get(execution_id)
        if connection is not None and session_id is not None:
            with contextlib.suppress(Exception):
                await connection.cancel(session_id=session_id)
        task = self._tasks.get(execution_id)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._cleanup_execution(execution_id)
        self._tasks.pop(execution_id, None)

    def is_alive(self, execution_id: str) -> bool:
        if execution_id in self._reserved:
            return True
        task = self._tasks.get(execution_id)
        return task is not None and not task.done()

    async def wait(self, execution_id: str) -> None:
        task = self._tasks.get(execution_id)
        if task is None:
            return
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.cancelled():
                raise
        finally:
            if task.done():
                self._tasks.pop(execution_id, None)

    async def destroy_thread(self, thread_id: str) -> None:
        for execution_id, mapped_thread_id in list(self._execution_threads.items()):
            if mapped_thread_id == thread_id:
                await self.stop(execution_id)

    async def evict_idle(self) -> int:
        return 0

    async def _run_turn(
        self,
        *,
        execution_id: str,
        request: AgentExecutionRequest,
        cwd: str,
        on_event: EventCallback,
    ) -> None:
        mapper = OpenCodeAcpEventMapper()
        client = OpenCodeAcpClient(
            cwd=Path(cwd),
            permission_mode=request.permission_mode,
            on_event=on_event,
        )
        client.mapper = mapper
        ctx = self._spawn_agent(
            client, "opencode", "acp", env=dict(os.environ), cwd=cwd
        )
        try:
            async with ctx as (connection, _process):
                self._connections[execution_id] = connection
                await connection.initialize(
                    protocol_version=PROTOCOL_VERSION,
                    client_capabilities=ClientCapabilities(
                        fs=FileSystemCapability(
                            read_text_file=True,
                            write_text_file=True,
                        ),
                        terminal=True,
                    ),
                    client_info=Implementation(
                        name="aileron-opencode-acp",
                        title="Aileron OpenCode ACP",
                        version="0.1.0",
                    ),
                )
                session_id = await self._open_session(connection, request, cwd)
                self._sessions[execution_id] = session_id
                await self._emit(
                    on_event,
                    AgentEvent(
                        type="system_init",
                        content={
                            "agentResumeId": session_id,
                            "model": request.model,
                            "cwd": cwd,
                            "tools": [],
                            "mcpServers": [],
                        },
                    ),
                )
                with contextlib.suppress(Exception):
                    await connection.set_session_model(
                        session_id=session_id,
                        model_id=request.model,
                    )
                response = await connection.prompt(
                    session_id=session_id,
                    prompt=[text_block(self._prompt(request))],
                )
                await self._handle_prompt_response(
                    response,
                    mapper,
                    on_event,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            for event in mapper.flush_events():
                await self._emit(on_event, event)
            await self._emit_error(on_event, exc, phase="run")
        finally:
            self._cleanup_execution(execution_id)

    async def _open_session(
        self,
        connection: Any,
        request: AgentExecutionRequest,
        cwd: str,
    ) -> str:
        mcp_servers = acp_aileron_mcp_servers()
        if request.agent_resume_id:
            try:
                await connection.resume_session(
                    cwd=cwd,
                    session_id=request.agent_resume_id,
                    mcp_servers=mcp_servers,
                )
            except Exception:
                await connection.load_session(
                    cwd=cwd,
                    mcp_servers=mcp_servers,
                    session_id=request.agent_resume_id,
                )
            return request.agent_resume_id
        session = await connection.new_session(cwd=cwd, mcp_servers=mcp_servers)
        return str(session.session_id)

    async def _handle_prompt_response(
        self,
        response: Any,
        mapper: OpenCodeAcpEventMapper,
        on_event: EventCallback,
    ) -> None:
        for event in mapper.flush_events():
            await self._emit(on_event, event)
        stop_reason = str(getattr(response, "stop_reason", "") or "")
        if stop_reason == "cancelled":
            return
        if stop_reason and stop_reason != "end_turn":
            message = f"OpenCode stopped with {stop_reason}"
            await self._emit(
                on_event,
                AgentEvent(
                    type="error",
                    content={
                        "text": message,
                        "parts": [{"type": "text", "text": message}],
                    },
                    error_code="opencode_execution_failed",
                    error_info={"message": stop_reason, "stop_reason": stop_reason},
                ),
            )
            return
        await self._emit(on_event, mapper.complete_event())

    async def _emit_error(
        self,
        on_event: EventCallback,
        exc: Exception,
        *,
        phase: str,
    ) -> None:
        message = str(exc) or type(exc).__name__
        error_info: dict[str, Any] = {
            "exception": type(exc).__name__,
            "message": message,
            "phase": phase,
        }
        if isinstance(exc, RequestError):
            error_info["code"] = exc.code
            error_info["data"] = getattr(exc, "data", None)
        await self._emit(
            on_event,
            AgentEvent(
                type="error",
                content={
                    "text": message,
                    "parts": [{"type": "text", "text": message}],
                },
                error_code=(
                    "prompt_too_long"
                    if self._is_prompt_too_long_error(message)
                    else "opencode_execution_failed"
                ),
                error_info=error_info,
            ),
        )

    @staticmethod
    async def _emit(on_event: EventCallback, event: AgentEvent) -> None:
        result = on_event(event)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _prompt(request: AgentExecutionRequest) -> str:
        if not request.attachments:
            user_prompt = request.prompt_text
        else:
            attachment_lines = "\n".join(
                OpenCodeAcpAgentRunner._attachment_prompt_line(attachment)
                for attachment in request.attachments
            )
            user_prompt = f"{request.prompt_text}\n\nAttachments:\n{attachment_lines}"
        return f"{AILERON_OPENCODE_POLICY_PROMPT}\n\nUser request:\n{user_prompt}"

    @staticmethod
    def _attachment_prompt_line(attachment: dict[str, Any]) -> str:
        attachment_type = str(attachment.get("type") or "file")
        name = str(attachment.get("name") or "unnamed")
        mime_type = str(attachment.get("mimeType") or "application/octet-stream")
        path = str(attachment.get("path") or "")
        if attachment_type == "text-file":
            return f"Attached text file {name} ({mime_type}): {path}"
        if attachment_type == "pdf":
            return f"Attached PDF {name} ({mime_type}): {path}"
        if attachment_type == "image":
            return f"Attached image {name} ({mime_type}): {path}"
        return f"Attached file {name} ({mime_type}): {path}"

    @staticmethod
    def _is_prompt_too_long_error(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "prompt is too long",
                "maximum context length",
                "context window",
            )
        )

    def _discard_task(self, execution_id: str, completed: asyncio.Task[None]) -> None:
        if self._tasks.get(execution_id) is completed:
            self._tasks.pop(execution_id, None)

    def _cleanup_execution(self, execution_id: str) -> None:
        self._reserved.discard(execution_id)
        self._connections.pop(execution_id, None)
        self._sessions.pop(execution_id, None)
        self._execution_threads.pop(execution_id, None)

    def _resolve_cwd(self, git_context_id: str | None) -> Path:
        workspace_root = Path("/workspace").resolve()
        utils = GitUtils(workspace_root, worktree_subdir=get_worktree_subdir())
        return utils.resolve_context_path(self.workspace_id, git_context_id)
