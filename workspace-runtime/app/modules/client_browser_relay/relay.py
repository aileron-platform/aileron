"""
Client Browser Relay Service

CDP Relay service core logic, acting as a bridge layer between Playwright clients and Chrome extensions
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from fastapi import WebSocket

from app.modules.runtime_control.state import get_runtime_admission_state

if TYPE_CHECKING:
    from app.modules.auth.manager_assertion import BrowserPairingClaims

from .models import (
    ConnectedTarget,
    PlaywrightClient,
    TargetInfo,
)

logger = logging.getLogger(__name__)


class RelayService:
    """CDP Relay service core logic"""

    def __init__(self) -> None:
        # Connected targets (sessionId -> ConnectedTarget)
        self.connected_targets: dict[str, ConnectedTarget] = {}
        # Named page mapping (name -> sessionId)
        self.named_pages: dict[str, str] = {}
        # Playwright client connections (clientId -> PlaywrightClient)
        self.playwright_clients: dict[str, PlaywrightClient] = {}
        # Playwright WebSocket connections (clientId -> WebSocket)
        self.playwright_websockets: dict[str, WebSocket] = {}
        # Chrome extension WebSocket connection
        self.extension_ws: Optional[WebSocket] = None
        # Manager-signed identity bound to the current extension socket
        self.extension_pairing: BrowserPairingClaims | None = None
        # Pending futures for extension requests
        self.extension_pending_requests: dict[int, asyncio.Future] = {}
        # Message ID counter
        self._message_id = 0
        # Futures waiting for target attached (targetId -> asyncio.Future)
        self._target_attachment_futures: dict[str, asyncio.Future] = {}
        # Concurrency protection lock: protect access to shared state
        self._lock = asyncio.Lock()

    def _log(self, *args: Any) -> None:
        """Log output"""
        logger.info("[relay] %s", " ".join(str(a) for a in args))

    # ============================================================================
    # Playwright Client Management
    # ============================================================================

    async def register_playwright_client(self, client_id: str, ws: WebSocket) -> bool:
        """Register Playwright client"""
        get_runtime_admission_state().require_accepting()
        async with self._lock:
            get_runtime_admission_state().require_accepting()
            if client_id in self.playwright_clients:
                self._log(f"Rejecting duplicate client ID: {client_id}")
                return False

            self.playwright_clients[client_id] = PlaywrightClient(id=client_id)
            self.playwright_websockets[client_id] = ws
            self._log(f"Playwright client connected: {client_id}")
            return True

    async def unregister_playwright_client(self, client_id: str) -> None:
        """Unregister Playwright client"""
        async with self._lock:
            self.playwright_clients.pop(client_id, None)
            self.playwright_websockets.pop(client_id, None)
            self._log(f"Playwright client disconnected: {client_id}")

    async def send_to_playwright(
        self, message: dict[str, Any], client_id: Optional[str] = None
    ) -> None:
        """Send message to Playwright client"""
        message_str = json.dumps(message)

        if client_id:
            ws = self.playwright_websockets.get(client_id)
            if ws:
                try:
                    await ws.send_text(message_str)
                except Exception as e:
                    self._log(f"Error sending to client {client_id}: {e}")
        else:
            # Broadcast to all clients
            for cid, ws in list(self.playwright_websockets.items()):
                try:
                    await ws.send_text(message_str)
                except Exception as e:
                    self._log(f"Error broadcasting to client {cid}: {e}")

    async def send_attached_to_target(
        self,
        target: ConnectedTarget,
        client_id: Optional[str] = None,
        waiting_for_debugger: bool = False,
    ) -> None:
        """Send Target.attachedToTarget event (with deduplication)"""
        event = {
            "method": "Target.attachedToTarget",
            "params": {
                "sessionId": target.session_id,
                "targetInfo": {
                    "targetId": target.target_info.target_id,
                    "type": target.target_info.type,
                    "title": target.target_info.title,
                    "url": target.target_info.url,
                    "attached": True,
                    "browserContextId": target.target_info.browser_context_id,
                },
                "waitingForDebugger": waiting_for_debugger,
            },
        }

        async with self._lock:
            if client_id:
                client = self.playwright_clients.get(client_id)
                if client and target.target_id not in client.known_targets:
                    client.known_targets.add(target.target_id)
                    await self.send_to_playwright(event, client_id)
            else:
                # Broadcast to all clients that don't know about this target
                for cid, client in self.playwright_clients.items():
                    if target.target_id not in client.known_targets:
                        client.known_targets.add(target.target_id)
                        await self.send_to_playwright(event, cid)

    # ============================================================================
    # Chrome Extension Management
    # ============================================================================

    async def register_extension(
        self,
        ws: WebSocket,
        pairing: BrowserPairingClaims,
    ) -> None:
        """Register Chrome extension connection"""
        get_runtime_admission_state().require_accepting()
        self._log(
            f"register_extension called, existing ws: {id(self.extension_ws) if self.extension_ws else 'None'}, new ws: {id(ws)}"
        )

        async with self._lock:
            get_runtime_admission_state().require_accepting()
            if self.extension_ws:
                self._log(
                    f"Closing existing extension connection (ws id: {id(self.extension_ws)})"
                )
                try:
                    await self.extension_ws.close(
                        code=4001, reason="Extension Replaced"
                    )
                    self._log("Existing connection closed successfully")
                except Exception as e:
                    self._log(f"Error closing existing connection: {e}")

                # Clean up state
                self.connected_targets.clear()
                self.named_pages.clear()
                for future in self.extension_pending_requests.values():
                    if not future.done():
                        future.set_exception(Exception("Extension connection replaced"))
                self.extension_pending_requests.clear()

            self.extension_ws = ws
            self.extension_pairing = pairing
            self._log(f"Extension connected (ws id: {id(ws)})")

    async def unregister_extension(self) -> None:
        """Unregister Chrome extension"""
        self._log("Extension disconnected")

        async with self._lock:
            # Reject all pending requests
            for future in self.extension_pending_requests.values():
                if not future.done():
                    future.set_exception(Exception("Extension connection closed"))
            self.extension_pending_requests.clear()

            self.extension_ws = None
            self.extension_pairing = None
            self.connected_targets.clear()
            self.named_pages.clear()

            # Close all Playwright clients
            for client_id, ws in list(self.playwright_websockets.items()):
                try:
                    await ws.close(code=1000, reason="Extension disconnected")
                except Exception:
                    pass
            self.playwright_clients.clear()
            self.playwright_websockets.clear()

    async def send_to_extension(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send command to extension and wait for response"""
        get_runtime_admission_state().require_accepting()
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        async with self._lock:
            get_runtime_admission_state().require_accepting()
            extension = self.extension_ws
            if extension is None or self.extension_pairing is None:
                raise Exception("Extension not connected")
            self._message_id += 1
            msg_id = self._message_id
            self.extension_pending_requests[msg_id] = future

        message = {"id": msg_id, "method": method, "params": params or {}}
        try:
            await extension.send_text(json.dumps(message))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise Exception(f"Extension request timeout after {timeout}s: {method}")
        finally:
            async with self._lock:
                if self.extension_pending_requests.get(msg_id) is future:
                    self.extension_pending_requests.pop(msg_id, None)

    def handle_extension_response(
        self, msg_id: int, result: Any, error: Optional[str]
    ) -> None:
        """Handle extension response"""
        # Note: This is a synchronous method but modifies extension_pending_requests
        # Since this is called in on_message callback and cannot be changed to async
        # We need to ensure the operation is atomic (dict.pop is atomic)
        future = self.extension_pending_requests.pop(msg_id, None)
        if not future:
            self._log(f"Unexpected response with id: {msg_id}")
            return

        if error:
            future.set_exception(Exception(error))
        else:
            future.set_result(result)

    # ============================================================================
    # CDP Command Routing
    # ============================================================================

    async def route_cdp_command(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Any:
        """Route CDP command"""
        params = params or {}

        # Handle some local CDP commands
        match method:
            case "Browser.getVersion":
                return {
                    "protocolVersion": "1.3",
                    "product": "Chrome/Extension-Bridge",
                    "revision": "1.0.0",
                    "userAgent": "client-browser-relay/1.0.0",
                    "jsVersion": "V8",
                }

            case "Browser.setDownloadBehavior":
                return {}

            case "Target.setAutoAttach":
                if session_id:
                    # Forward to extension for child frames
                    pass
                else:
                    return {}

            case "Target.setDiscoverTargets":
                return {}

            case "Target.attachToBrowserTarget":
                # Browser-level session - return a fake session
                return {"sessionId": "browser"}

            case "Target.detachFromTarget":
                if session_id == "browser" or params.get("sessionId") == "browser":
                    return {}
                # Otherwise forward to extension

            case "Target.attachToTarget":
                target_id = params.get("targetId")
                if not target_id:
                    raise Exception("targetId is required for Target.attachToTarget")

                async with self._lock:
                    for target in self.connected_targets.values():
                        if target.target_id == target_id:
                            return {"sessionId": target.session_id}

                raise Exception(f"Target {target_id} not found in connected targets")

            case "Target.getTargetInfo":
                target_id = params.get("targetId")

                async with self._lock:
                    if target_id:
                        for target in self.connected_targets.values():
                            if target.target_id == target_id:
                                return {
                                    "targetInfo": self._target_info_to_dict(
                                        target.target_info
                                    )
                                }

                    if session_id:
                        session_target = self.connected_targets.get(session_id)
                        if session_target:
                            return {
                                "targetInfo": self._target_info_to_dict(
                                    session_target.target_info
                                )
                            }

                    # Return first target if no specific one requested
                    if self.connected_targets:
                        first_target = next(iter(self.connected_targets.values()))
                        return {
                            "targetInfo": self._target_info_to_dict(
                                first_target.target_info
                            )
                        }

                return {"targetInfo": None}

            case "Target.getTargets":
                async with self._lock:
                    return {
                        "targetInfos": [
                            {
                                **self._target_info_to_dict(t.target_info),
                                "attached": True,
                            }
                            for t in self.connected_targets.values()
                        ]
                    }

            case "Target.createTarget" | "Target.closeTarget":
                # Forward to extension
                return await self.send_to_extension(
                    "forwardCDPCommand",
                    {"method": method, "params": params},
                )

        # Forward all other commands to extension
        return await self.send_to_extension(
            "forwardCDPCommand",
            {"sessionId": session_id, "method": method, "params": params},
        )

    def _target_info_to_dict(self, info: TargetInfo) -> dict[str, Any]:
        """Convert TargetInfo to dictionary"""
        return {
            "targetId": info.target_id,
            "type": info.type,
            "title": info.title,
            "url": info.url,
            "attached": info.attached,
            "browserContextId": info.browser_context_id,
        }

    # ============================================================================
    # Target Lifecycle Event Handling
    # ============================================================================

    async def handle_target_attached(
        self, session_id: str, target_info_dict: dict[str, Any]
    ) -> None:
        """Handle Target.attachedToTarget event"""
        target_info = TargetInfo(
            targetId=target_info_dict.get("targetId", ""),
            type=target_info_dict.get("type", "page"),
            title=target_info_dict.get("title", ""),
            url=target_info_dict.get("url", ""),
            attached=True,
            browserContextId=target_info_dict.get("browserContextId", "default"),
        )

        target = ConnectedTarget(
            session_id=session_id,
            target_id=target_info.target_id,
            target_info=target_info,
        )

        async with self._lock:
            self.connected_targets[session_id] = target

        self._log(f"Target attached: {target_info.url} ({session_id})")

        # Resolve future waiting for this target (if exists)
        future = self._target_attachment_futures.pop(target_info.target_id, None)
        if future and not future.done():
            future.set_result(session_id)

        # Send event with deduplication
        await self.send_attached_to_target(target)

    async def handle_target_detached(self, session_id: str) -> None:
        """Handle Target.detachedFromTarget event"""
        async with self._lock:
            self.connected_targets.pop(session_id, None)

            # Remove named page mapping
            for name, sid in list(self.named_pages.items()):
                if sid == session_id:
                    del self.named_pages[name]

        self._log(f"Target detached: {session_id}")

        await self.send_to_playwright(
            {
                "method": "Target.detachedFromTarget",
                "params": {"sessionId": session_id},
            }
        )

    async def handle_target_info_changed(
        self, target_info_dict: dict[str, Any]
    ) -> None:
        """Handle Target.targetInfoChanged event"""
        target_id = target_info_dict.get("targetId")

        async with self._lock:
            for target in self.connected_targets.values():
                if target.target_id == target_id:
                    target.target_info = TargetInfo(
                        targetId=target_info_dict.get("targetId", ""),
                        type=target_info_dict.get("type", "page"),
                        title=target_info_dict.get("title", ""),
                        url=target_info_dict.get("url", ""),
                        attached=target_info_dict.get("attached", True),
                        browserContextId=target_info_dict.get(
                            "browserContextId", "default"
                        ),
                    )
                    break

        await self.send_to_playwright(
            {
                "method": "Target.targetInfoChanged",
                "params": {"targetInfo": target_info_dict},
            }
        )

    # ============================================================================
    # Named Page Management
    # ============================================================================

    def get_named_pages(self) -> list[str]:
        """Get all named pages"""
        return list(self.named_pages.keys())

    async def get_or_create_named_page(
        self, name: str, host: str, port: int
    ) -> Optional[dict[str, Any]]:
        """Get or create named page"""
        get_runtime_admission_state().require_accepting()
        existing_target: ConnectedTarget | None = None
        async with self._lock:
            get_runtime_admission_state().require_accepting()
            existing_session_id = self.named_pages.get(name)
            if existing_session_id:
                existing_target = self.connected_targets.get(existing_session_id)
                if existing_target is None:
                    del self.named_pages[name]

        if existing_target is not None:
            await self._activate_target(existing_target.target_id)
            return self._named_page_response(
                name=name,
                host=host,
                port=port,
                target=existing_target,
            )

        result = await self.send_to_extension(
            "forwardCDPCommand",
            {"method": "Target.createTarget", "params": {"url": "about:blank"}},
        )

        target_id = result.get("targetId") if isinstance(result, dict) else None
        if not target_id:
            return None

        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        target: ConnectedTarget | None = None
        async with self._lock:
            get_runtime_admission_state().require_accepting()
            target = next(
                (
                    candidate
                    for candidate in self.connected_targets.values()
                    if candidate.target_id == target_id
                ),
                None,
            )
            if target is None:
                self._target_attachment_futures[target_id] = future

        try:
            if target is None:
                session_id = await asyncio.wait_for(future, timeout=2.0)
                async with self._lock:
                    get_runtime_admission_state().require_accepting()
                    target = self.connected_targets.get(session_id)
            if target is None or target.target_id != target_id:
                return None
            async with self._lock:
                get_runtime_admission_state().require_accepting()
                self.named_pages[name] = target.session_id
            await self._activate_target(target_id)
            return self._named_page_response(
                name=name,
                host=host,
                port=port,
                target=target,
            )
        except asyncio.TimeoutError:
            self._log(f"Target {target_id} attachment timed out")
        finally:
            async with self._lock:
                if self._target_attachment_futures.get(target_id) is future:
                    self._target_attachment_futures.pop(target_id, None)

        return None

    async def _activate_target(self, target_id: str) -> None:
        await self.send_to_extension(
            "forwardCDPCommand",
            {
                "method": "Target.activateTarget",
                "params": {"targetId": target_id},
            },
        )

    @staticmethod
    def _named_page_response(
        *,
        name: str,
        host: str,
        port: int,
        target: ConnectedTarget,
    ) -> dict[str, Any]:
        return {
            "wsEndpoint": f"ws://{host}:{port}/api/v1/client-browser-relay/cdp",
            "name": name,
            "targetId": target.target_id,
            "url": target.target_info.url,
        }

    async def delete_named_page(self, name: str) -> bool:
        """Delete named page (only removes name, does not close tab)"""
        async with self._lock:
            return self.named_pages.pop(name, None) is not None

    # ============================================================================
    # Status Query
    # ============================================================================

    def get_status(self, host: str, port: int) -> dict[str, Any]:
        """Get Relay Server status"""
        return {
            "wsEndpoint": f"ws://{host}:{port}/api/v1/client-browser-relay/cdp",
            "extensionConnected": (
                self.extension_ws is not None and self.extension_pairing is not None
            ),
            "mode": "extension",
            "connectedTargetsCount": len(self.connected_targets),
            "playwrightClientsCount": len(self.playwright_clients),
        }

    async def full_drain(self) -> None:
        """Close extension and every user CDP connection for this generation."""

        async with self._lock:
            extension = self.extension_ws
            playwright_websockets = list(self.playwright_websockets.values())
            pending_requests = list(self.extension_pending_requests.values())
            attachment_futures = list(self._target_attachment_futures.values())
            self.extension_ws = None
            self.extension_pairing = None
            self.connected_targets.clear()
            self.named_pages.clear()
            self.playwright_clients.clear()
            self.playwright_websockets.clear()
            self.extension_pending_requests.clear()
            self._target_attachment_futures.clear()

        for future in [*pending_requests, *attachment_futures]:
            if not future.done():
                future.set_exception(RuntimeError("WORKSPACE_RUNTIME_DRAINING"))
        sockets = [*playwright_websockets]
        if extension is not None:
            sockets.append(extension)
        results = await asyncio.gather(
            *(
                socket.close(
                    code=1012,
                    reason="WORKSPACE_RUNTIME_DRAINING",
                )
                for socket in sockets
            ),
            return_exceptions=True,
        )
        if any(isinstance(result, BaseException) for result in results):
            raise RuntimeError("browser_relay_drain_incomplete")


# Global singleton instance
_relay_service: Optional[RelayService] = None


def get_relay_service() -> RelayService:
    """Get RelayService singleton instance"""
    global _relay_service
    if _relay_service is None:
        _relay_service = RelayService()
    return _relay_service
