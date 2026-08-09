"""Supervisor topology tests for one worker and one beat."""

from __future__ import annotations

import shlex
from configparser import ConfigParser
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "config_name",
    ["supervisord.conf", "supervisord.dev.conf", "supervisord.kubernetes.conf"],
)
def test_supervisor_has_exactly_one_worker_and_one_beat(config_name: str) -> None:
    root = Path(__file__).resolve().parents[4]
    parser = ConfigParser(interpolation=None)
    parser.read(root / config_name)

    sections = parser.sections()
    assert sections.count("program:celery-worker") == 1
    assert sections.count("program:celery-beat") == 1
    worker_command = parser["program:celery-worker"]["command"]
    beat_command = parser["program:celery-beat"]["command"]
    worker_tokens = shlex.split(worker_command)
    beat_tokens = shlex.split(beat_command)
    assert "celery" in {Path(token).name for token in worker_tokens}
    assert "worker" in worker_tokens
    assert "--queues=celery" in worker_command
    assert "--without-heartbeat" not in worker_tokens
    assert "default" not in worker_command
    assert "beat" in beat_tokens


@pytest.mark.parametrize(
    "config_name",
    ["supervisord.conf", "supervisord.dev.conf"],
)
def test_fastapi_restart_tears_down_its_whole_process_group(config_name: str) -> None:
    # `uv run uvicorn ... --reload` (dev) nests a reloader/worker process
    # under the tracked pid. Without stopasgroup/killasgroup, a
    # `supervisorctl restart fastapi` (or autorestart after a crash) only
    # signals the tracked pid: a wedged reloader can survive holding the
    # port, so the respawned process fails with "Address already in use"
    # and the API stays down until someone finds and kills the orphan by
    # hand.
    root = Path(__file__).resolve().parents[4]
    parser = ConfigParser(interpolation=None)
    parser.read(root / config_name)

    fastapi_section = parser["program:fastapi"]
    assert fastapi_section.get("stopasgroup") == "true"
    assert fastapi_section.get("killasgroup") == "true"


@pytest.mark.parametrize(
    "config_name",
    ["supervisord.conf", "supervisord.dev.conf"],
)
def test_runtime_terminal_supervisor_does_not_restore_removed_session_state(
    config_name: str,
) -> None:
    mounted_repo_root = Path("/repo-root")
    repo_root = (
        mounted_repo_root
        if mounted_repo_root.is_dir()
        else Path(__file__).resolve().parents[5]
    )
    parser = ConfigParser(interpolation=None)
    parser.read(repo_root / "workspace-runtime" / config_name)

    terminal_environment = parser["program:terminal-service"]["environment"]
    for removed_name in (
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "MAX_TABS_PER_WORKSPACE",
        "SESSION_TIMEOUT",
        "PTY_BUFFER_SIZE",
    ):
        assert removed_name not in terminal_environment
