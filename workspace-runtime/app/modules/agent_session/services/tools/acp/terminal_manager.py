"""ACP Terminal process manager."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4


@dataclass
class TerminalSession:
    process: asyncio.subprocess.Process
    output: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    output_limit: Optional[int] = None
    readers: list[asyncio.Task] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def append_output(self, data: bytes) -> None:
        if self.output_limit is None:
            self.output.extend(data)
            return

        remaining = self.output_limit - len(self.output)
        if remaining <= 0:
            self.truncated = True
            return

        if len(data) > remaining:
            self.output.extend(data[:remaining])
            self.truncated = True
        else:
            self.output.extend(data)


class TerminalProcessManager:
    """Manage terminal subprocesses for ACP."""

    def __init__(self, workspace_path: str) -> None:
        self.workspace_path = Path(workspace_path).resolve()
        self.sessions: Dict[str, TerminalSession] = {}

    def _resolve_cwd(self, cwd: Optional[str]) -> Path:
        if not cwd:
            return self.workspace_path
        cwd_path = Path(cwd).expanduser().resolve()
        if self.workspace_path not in cwd_path.parents and cwd_path != self.workspace_path:
            return self.workspace_path
        return cwd_path

    async def create_terminal(
        self,
        command: str,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        output_byte_limit: Optional[int] = None,
    ) -> str:
        terminal_id = str(uuid4())
        working_dir = self._resolve_cwd(cwd)

        process = await asyncio.create_subprocess_exec(
            command,
            *(args or []),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir),
            env=env,
        )

        session = TerminalSession(process=process, output_limit=output_byte_limit)
        self.sessions[terminal_id] = session

        if process.stdout:
            session.readers.append(asyncio.create_task(self._read_stream(process.stdout, session)))
        if process.stderr:
            session.readers.append(asyncio.create_task(self._read_stream(process.stderr, session)))

        return terminal_id

    async def _read_stream(self, stream: asyncio.StreamReader, session: TerminalSession) -> None:
        while True:
            data = await stream.read(1024)
            if not data:
                break
            async with session.lock:
                session.append_output(data)

    async def get_output(self, terminal_id: str) -> tuple[str, bool, Optional[int]]:
        session = self.sessions.get(terminal_id)
        if not session:
            return "", False, None
        async with session.lock:
            output_text = session.output.decode("utf-8", errors="replace")
            truncated = session.truncated
        exit_code = session.process.returncode
        return output_text, truncated, exit_code

    async def wait_for_exit(self, terminal_id: str) -> Optional[int]:
        session = self.sessions.get(terminal_id)
        if not session:
            return None
        return await session.process.wait()

    async def kill(self, terminal_id: str) -> None:
        session = self.sessions.get(terminal_id)
        if not session:
            return
        session.process.kill()
        await session.process.wait()

    async def release(self, terminal_id: str) -> None:
        session = self.sessions.pop(terminal_id, None)
        if not session:
            return
        for task in session.readers:
            task.cancel()
        session.readers.clear()
