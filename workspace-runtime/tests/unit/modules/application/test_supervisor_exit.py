import signal
from unittest.mock import Mock, patch

import pytest

from scripts.supervisor_exit_on_fastapi_failure import FastAPIExitListener


@pytest.mark.parametrize(
    "event_name,from_state",
    [
        ("PROCESS_STATE_EXITED", "RUNNING"),
        ("PROCESS_STATE_FATAL", "BACKOFF"),
    ],
)
def test_fastapi_exit_or_fatal_requests_supervisor_shutdown_once(
    event_name: str, from_state: str
) -> None:
    shutdown = Mock()
    listener = FastAPIExitListener(shutdown)
    payload = f"processname:fastapi groupname:fastapi from_state:{from_state}"

    assert listener.handle(event_name, payload) is True
    assert listener.handle(event_name, payload) is False

    shutdown.assert_called_once_with()


@pytest.mark.parametrize(
    "event_name,payload",
    [
        (
            "PROCESS_STATE_EXITED",
            "processname:terminal-service groupname:terminal-service "
            "from_state:RUNNING",
        ),
        (
            "PROCESS_STATE_FATAL",
            "processname:sshd groupname:sshd from_state:BACKOFF",
        ),
        (
            "PROCESS_STATE_BACKOFF",
            "processname:fastapi groupname:fastapi from_state:STARTING",
        ),
    ],
)
def test_unrelated_processes_and_backoff_do_not_shutdown(
    event_name: str, payload: str
) -> None:
    shutdown = Mock()
    listener = FastAPIExitListener(shutdown)

    assert listener.handle(event_name, payload) is False

    shutdown.assert_not_called()


def test_shutdown_rpc_failure_signals_supervisor_pid_one() -> None:
    shutdown = Mock(side_effect=RuntimeError("RPC unavailable"))
    listener = FastAPIExitListener(shutdown)
    payload = "processname:fastapi groupname:fastapi from_state:RUNNING"

    with patch("scripts.supervisor_exit_on_fastapi_failure.os.kill") as kill:
        assert listener.handle("PROCESS_STATE_EXITED", payload) is True

    shutdown.assert_called_once_with()
    kill.assert_called_once_with(1, signal.SIGTERM)
