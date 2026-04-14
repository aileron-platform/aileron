"""ACP connection manager."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from acp import PROTOCOL_VERSION, spawn_agent_process
from acp.schema import ClientCapabilities, FileSystemCapability, Implementation

from app.modules.agent_session.services.tool_decision_manager import global_tool_decision_manager

from .client import AcpClient

logger = logging.getLogger(__name__)


@dataclass
class AcpConnection:
    """Holds ACP connection state."""

    session_id: str
    tool_type: str
    connection: Any
    process: asyncio.subprocess.Process
    context_manager: Any
    client_impl: AcpClient
    sdk_session_id: Optional[str] = None
    initialized: bool = False


class AcpConnectionManager:
    """Manage ACP stdio connections per runtime session."""

    def __init__(self) -> None:
        self._connections: Dict[str, AcpConnection] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        session_id: str,
        tool_type: str,
        command: str,
        args: list[str],
        env: Optional[dict[str, str]],
        cwd: str,
        supports_terminal: bool = True,
    ) -> AcpConnection:
        async with self._lock:
            existing = self._connections.get(session_id)
            if existing and existing.process.returncode is None:
                return existing

            if existing:
                await self._close_connection(existing)

            connection = await self._create_connection(
                session_id=session_id,
                tool_type=tool_type,
                command=command,
                args=args,
                env=env,
                cwd=cwd,
                supports_terminal=supports_terminal,
            )
            self._connections[session_id] = connection
            return connection

    def get_existing(self, session_id: str) -> Optional[AcpConnection]:
        return self._connections.get(session_id)

    async def close(self, session_id: str) -> None:
        async with self._lock:
            connection = self._connections.pop(session_id, None)
        if connection:
            await self._close_connection(connection)

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for conn in connections:
            await self._close_connection(conn)

    async def _create_connection(
        self,
        session_id: str,
        tool_type: str,
        command: str,
        args: list[str],
        env: Optional[dict[str, str]],
        cwd: str,
        supports_terminal: bool = True,
    ) -> AcpConnection:
        client_impl = AcpClient(runtime_session_id=session_id, workspace_path=cwd)
        context_manager = spawn_agent_process(client_impl, command, *args, env=env, cwd=cwd)
        try:
            connection, process = await context_manager.__aenter__()
        except Exception:
            logger.exception("Failed to spawn ACP agent process")
            await context_manager.__aexit__(None, None, None)
            raise

        acp_conn = AcpConnection(
            session_id=session_id,
            tool_type=tool_type,
            connection=connection,
            process=process,
            context_manager=context_manager,
            client_impl=client_impl,
        )

        try:
            await self._initialize_connection(acp_conn, supports_terminal=supports_terminal)
        except Exception:
            logger.exception("Failed to initialize ACP connection")
            await self._close_connection(acp_conn)
            raise

        return acp_conn

    async def _initialize_connection(self, conn: AcpConnection, supports_terminal: bool = True) -> None:
        if conn.initialized:
            return

        capabilities = ClientCapabilities(
            fs=FileSystemCapability(read_text_file=True, write_text_file=True),
            terminal=supports_terminal,
        )
        client_info = Implementation(
            name="aileron",
            title="Aileron",
            version="0.1.0",
        )

        await conn.connection.initialize(
            protocol_version=PROTOCOL_VERSION,
            client_capabilities=capabilities,
            client_info=client_info,
        )
        conn.initialized = True

    async def _close_connection(self, conn: AcpConnection) -> None:
        try:
            await conn.context_manager.__aexit__(None, None, None)
        except Exception:
            logger.exception("Failed to close ACP connection")
        finally:
            # Remove stale decision hooks when a runtime session disconnects.
            global_tool_decision_manager.unregister_hooks(conn.session_id)


__all__ = ["AcpConnectionManager", "AcpConnection"]
