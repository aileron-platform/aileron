from collections.abc import Callable
import os
import signal
import sys

from supervisor import childutils


SHUTDOWN_EVENTS = {"PROCESS_STATE_EXITED", "PROCESS_STATE_FATAL"}


class FastAPIExitListener:
    def __init__(self, shutdown: Callable[[], None]) -> None:
        self._shutdown = shutdown
        self._shutdown_requested = False

    def handle(self, event_name: str, payload: str) -> bool:
        if self._shutdown_requested or event_name not in SHUTDOWN_EVENTS:
            return False

        fields = dict(item.split(":", 1) for item in payload.split() if ":" in item)
        if fields.get("processname") != "fastapi":
            return False

        self._shutdown_requested = True
        try:
            self._shutdown()
        except Exception as exc:
            print(
                f"Supervisor shutdown RPC failed; signaling PID 1: {exc}",
                file=sys.stderr,
                flush=True,
            )
            os.kill(1, signal.SIGTERM)
        return True


def main() -> None:
    rpc = childutils.getRPCInterface(os.environ)
    listener = FastAPIExitListener(rpc.supervisor.shutdown)

    while True:
        headers, payload = childutils.listener.wait()
        try:
            listener.handle(headers.get("eventname", ""), payload)
        except Exception as exc:
            print(
                f"Failed to request Supervisor shutdown: {exc}",
                file=sys.stderr,
                flush=True,
            )
        finally:
            childutils.listener.ok()


if __name__ == "__main__":
    main()
