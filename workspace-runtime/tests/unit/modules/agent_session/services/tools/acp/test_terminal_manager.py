from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.modules.agent_session.services.tools.acp.terminal_manager import TerminalProcessManager, TerminalSession


class FakeProcess:
    def __init__(self, stdout=None, stderr=None, returncode=None) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.kill_calls = 0
        self.wait_calls = 0

    async def wait(self):
        self.wait_calls += 1
        return self.returncode

    def kill(self) -> None:
        self.kill_calls += 1


class FakeStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)

    async def read(self, _: int) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        return b""


def test_append_output_with_limit_truncates() -> None:
    session = TerminalSession(process=FakeProcess(), output_limit=5)

    session.append_output(b"abc")
    session.append_output(b"def")

    assert bytes(session.output) == b"abcde"
    assert session.truncated is True


@pytest.mark.asyncio
async def test_terminal_manager_create_get_wait_kill_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = TerminalProcessManager(str(tmp_path))
    stdout = FakeStream([b"hello ", b"world"])
    stderr = FakeStream([b"!"])
    process = FakeProcess(stdout=stdout, stderr=stderr, returncode=7)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    terminal_id = await manager.create_terminal(
        "echo",
        args=["hi"],
        cwd=str(tmp_path / "nested"),
        env={"A": "1"},
        output_byte_limit=20,
    )
    await asyncio.sleep(0)
    output, truncated, exit_code = await manager.get_output(terminal_id)
    waited = await manager.wait_for_exit(terminal_id)
    await manager.kill(terminal_id)
    await manager.release(terminal_id)

    assert output == "hello world!"
    assert truncated is False
    assert exit_code == 7
    assert waited == 7
    assert process.kill_calls == 1
    assert terminal_id not in manager.sessions
    assert await manager.wait_for_exit("missing") is None
    assert await manager.get_output("missing") == ("", False, None)


def test_resolve_cwd_stays_within_workspace(tmp_path: Path) -> None:
    manager = TerminalProcessManager(str(tmp_path))

    inside = manager._resolve_cwd(str(tmp_path / "a" / ".." / "b"))
    outside = manager._resolve_cwd("/tmp")

    assert inside == (tmp_path / "b").resolve()
    assert outside == tmp_path.resolve()
