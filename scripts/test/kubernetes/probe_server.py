from __future__ import annotations

import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        payload = json.dumps(
            {
                "status": "healthy",
                "terminal_service": {"status": "ready"},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), ProbeHandler)
    server.serve_forever()


def main() -> None:
    for port in (3002, 3003, 3004, 3013, 6080, 9223):
        threading.Thread(target=serve, args=(port,), daemon=True).start()

    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    stopped.wait()


if __name__ == "__main__":
    main()
