from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


AILERON_MCP_SERVER_PATH = Path(__file__).resolve().parent / "server.py"


def codex_aileron_mcp_config_overrides() -> tuple[str, ...]:
    return (
        f"mcp_servers.aileron.command={json.dumps(sys.executable)}",
        "mcp_servers.aileron.args=" f"[{json.dumps(str(AILERON_MCP_SERVER_PATH))}]",
    )


def codex_aileron_mcp_thread_config() -> dict[str, Any]:
    return {
        "mcp_servers": {
            "aileron": {
                "command": sys.executable,
                "args": [str(AILERON_MCP_SERVER_PATH)],
            }
        }
    }


def acp_aileron_mcp_servers() -> list[Any]:
    from acp.schema import McpServerStdio

    return [
        McpServerStdio(
            name="aileron",
            command=sys.executable,
            args=[str(AILERON_MCP_SERVER_PATH)],
            env=[],
        )
    ]
