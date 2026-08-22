import json
import sqlite3
from pathlib import Path

from app.modules.claude_code.documents import DocumentScope, resolve_scope_root
from app.modules.claude_code.memory.documents import MemoryService
from app.modules.cli_settings.user_scope.models import CodexLayer, CodexResource
from app.modules.cli_settings.user_scope.paths import (
    CodexPathResolver,
    runtime_user_home,
)
from app.modules.internal.commands import InternalService
from app.modules.thread.codex_sdk_client_manager import CodexSdkClientManager
from app.modules.thread.opencode_acp_event_mapper import (
    OpenCodeAcpEventMapper,
)


def test_runtime_paths_follow_dynamic_home(monkeypatch, tmp_path: Path) -> None:
    managed_home = tmp_path / "uid-1000860000"
    monkeypatch.setenv("HOME", str(managed_home))
    monkeypatch.setenv("PATH", str(tmp_path / "path-codex-bin"))
    monkeypatch.delenv("OPENCODE_DB_PATH", raising=False)
    opencode_db = managed_home / ".local" / "share" / "opencode" / "opencode.db"
    opencode_db.parent.mkdir(parents=True)
    with sqlite3.connect(opencode_db) as connection:
        connection.execute(
            "create table part (session_id text, time_created integer, data text)"
        )
        connection.execute(
            "insert into part (session_id, time_created, data) values (?, ?, ?)",
            (
                "session-1",
                1,
                json.dumps(
                    {
                        "type": "tool",
                        "callID": "tool-1",
                        "state": {"input": {"command": "pwd"}},
                    }
                ),
            ),
        )
    connection.close()

    resolver = CodexPathResolver(user_home=runtime_user_home())
    manager = CodexSdkClientManager()
    memory = MemoryService()
    internal = InternalService()
    opencode_input = OpenCodeAcpEventMapper()._opencode_state_input(
        "session-1",
        "tool-1",
    )

    assert resolver.resolve(CodexLayer.USER, CodexResource.CONFIG) == (
        managed_home / ".codex" / "config.toml"
    )
    assert resolve_scope_root("workspace-id", DocumentScope.USER) == (
        managed_home / ".claude"
    )
    assert memory._memory_dir == (
        managed_home / ".claude" / "projects" / "-workspace" / "memory"
    )
    assert manager._codex_bin is None
    assert manager._codex_home == str(managed_home / ".codex")
    assert internal.home_dir == managed_home
    assert internal.ssh_dir == managed_home / ".ssh"
    assert internal.claude_dir == managed_home / ".claude"
    assert internal.codex_auth_dir == managed_home / ".codex"
    assert internal.codex_sessions_dir == managed_home / ".codex-sessions"
    assert opencode_input == {"command": "pwd"}


def test_kubernetes_runtime_process_config_uses_standard_home() -> None:
    runtime_root = Path(__file__).resolve().parents[4]
    inspected_paths = [
        runtime_root / "app",
        runtime_root / "supervisord.kubernetes.conf",
        runtime_root / "start_services.kubernetes.sh",
    ]

    for inspected_path in inspected_paths:
        files = (
            inspected_path.rglob("*.py")
            if inspected_path.is_dir()
            else [inspected_path]
        )
        for file_path in files:
            source = file_path.read_text(encoding="utf-8")
            assert "/home/aileron" not in source, file_path
            assert "/runtime-state" not in source, file_path
            assert "user=developer" not in source, file_path
            assert "user=root" not in source, file_path


def test_kubernetes_startup_does_not_mutate_image_or_start_sshd() -> None:
    runtime_root = Path(__file__).resolve().parents[4]
    startup = (runtime_root / "start_services.kubernetes.sh").read_text(
        encoding="utf-8"
    )

    for forbidden in ("uv sync", "chown", "useradd", "sshd", "dockerd"):
        assert forbidden not in startup
