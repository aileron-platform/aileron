from configparser import RawConfigParser
from pathlib import Path

import pytest
from supervisor.options import ServerOptions


RUNTIME_ROOT = Path("/workspace-runtime")
MOUNTED_SOURCE_ROOT = Path("/app")


def supervisor_config_path(config_name: str) -> Path:
    mounted_source = MOUNTED_SOURCE_ROOT / config_name
    if mounted_source.exists():
        return mounted_source
    return RUNTIME_ROOT / config_name


@pytest.mark.parametrize(
    "config_name",
    ["supervisord.conf", "supervisord.dev.conf", "supervisord.kubernetes.conf"],
)
def test_fastapi_failure_stops_supervisor_process_group(config_name: str) -> None:
    config = RawConfigParser()
    config.read(supervisor_config_path(config_name))

    fastapi = config["program:fastapi"]
    assert fastapi.getboolean("autorestart") is False
    assert fastapi.getboolean("stopasgroup") is True
    assert fastapi.getboolean("killasgroup") is True
    assert fastapi.getint("stopwaitsecs") == 120

    listener = config["eventlistener:fastapi-exit-listener"]
    assert listener["events"] == "PROCESS_STATE_EXITED,PROCESS_STATE_FATAL"
    assert listener["command"] == (
        "/workspace-runtime/.venv/bin/python "
        "/workspace-runtime/scripts/supervisor_exit_on_fastapi_failure.py"
    )
    assert listener.getboolean("redirect_stderr", fallback=False) is False


@pytest.mark.parametrize(
    "config_name",
    ["supervisord.conf", "supervisord.dev.conf", "supervisord.kubernetes.conf"],
)
def test_supervisor_config_is_accepted_by_supervisord(
    config_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Path("/tmp/supervisor").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", "/home/developer")
    monkeypatch.setenv("CODEX_HOME", "/home/developer/.codex")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/developer/.config")
    monkeypatch.setenv("XDG_DATA_HOME", "/home/developer/.local/share")
    monkeypatch.setenv("XDG_STATE_HOME", "/home/developer/.local/state")
    monkeypatch.setenv(
        "MARKETPLACE_OPERATION_JOURNAL_DIR",
        "/home/developer/.local/state/aileron/marketplace-operations",
    )
    monkeypatch.setenv("NPM_CONFIG_PREFIX", "/home/developer/.local")
    monkeypatch.setenv("NPM_CONFIG_CACHE", "/tmp/npm-cache")
    monkeypatch.setenv("UV_CACHE_DIR", "/tmp/uv-cache")

    options = ServerOptions()
    options.realize(
        args=["-c", str(supervisor_config_path(config_name))],
        progname="supervisord",
    )
