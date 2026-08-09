from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.config.settings import get_settings
from app.modules.thread.invalidation_emitter import (
    get_thread_connection_manager,
)
from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
    get_execution_grant_verifier,
)
from app.modules.runtime_control.state import RuntimeDrainingError

router = APIRouter(prefix="/threads", tags=["thread-websocket"])

_THREAD_WEBSOCKET_PROTOCOL = "aileron-thread-v1"
_BEARER_PROTOCOL_PREFIX = "bearer."


@dataclass(frozen=True)
class _AuthenticatedWebSocket:
    user_id: str
    subprotocol: str | None


@router.websocket("/events")
async def websocket_thread_events_endpoint(websocket: WebSocket) -> None:
    authenticated = await _authenticate_websocket(websocket)
    if authenticated is None:
        return

    settings = get_settings()
    manager = get_thread_connection_manager()
    try:
        connection_id = await manager.connect(
            websocket,
            workspace_id=settings.AILERON_WORKSPACE_ID,
            user_id=authenticated.user_id,
            subprotocol=authenticated.subprotocol,
        )
    except RuntimeDrainingError:
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
    except Exception:
        await manager.disconnect(connection_id)


async def _authenticate_websocket(
    websocket: WebSocket,
) -> _AuthenticatedWebSocket | None:
    if any(name in websocket.query_params for name in ("token", "access_token")):
        await websocket.close(code=4401, reason="THREAD_AUTH_TOKEN_QUERY_REJECTED")
        return None
    if not _origin_allowed(websocket):
        await websocket.close(code=4403, reason="THREAD_ORIGIN_INVALID")
        return None
    authorization = websocket.headers.get("authorization", "")
    offered_protocols = _offered_protocols(websocket)
    if authorization:
        await websocket.close(code=4401, reason="THREAD_AUTH_HEADER_REJECTED")
        return None
    if not offered_protocols:
        await websocket.close(code=4401, reason="THREAD_AUTH_TOKEN_MISSING")
        return None
    try:
        token = _decode_protocol_bearer(offered_protocols)
        subprotocol = _THREAD_WEBSOCKET_PROTOCOL
    except ValueError:
        await websocket.close(code=4401, reason="THREAD_AUTH_TOKEN_INVALID")
        return None

    try:
        claims = get_execution_grant_verifier().verify(token, action="agent")
    except ExecutionGrantConflict as exc:
        await websocket.close(code=4423, reason=exc.error_code)
        return None
    except ExecutionGrantInvalid as exc:
        await websocket.close(code=4401, reason=exc.error_code)
        return None
    if not claims.subject:
        await websocket.close(code=4401, reason="THREAD_AUTH_TOKEN_INVALID")
        return None

    return _AuthenticatedWebSocket(
        user_id=claims.subject,
        subprotocol=subprotocol,
    )


def _origin_allowed(websocket: WebSocket) -> bool:
    settings = get_settings()
    origins = settings.effective_allowed_origins
    return len(origins) == 1 and websocket.headers.get("origin") == origins[0]


def _offered_protocols(websocket: WebSocket) -> list[str]:
    raw_value = websocket.headers.get("sec-websocket-protocol", "")
    if not raw_value:
        return []
    return [protocol.strip() for protocol in raw_value.split(",")]


def _decode_protocol_bearer(protocols: list[str]) -> str:
    if protocols.count(_THREAD_WEBSOCKET_PROTOCOL) != 1:
        raise ValueError("thread_protocol_missing")
    bearer_protocols = [
        protocol
        for protocol in protocols
        if protocol.startswith(_BEARER_PROTOCOL_PREFIX)
    ]
    if len(bearer_protocols) != 1 or len(protocols) != 2:
        raise ValueError("bearer_protocol_invalid")

    encoded = bearer_protocols[0][len(_BEARER_PROTOCOL_PREFIX) :]
    if not encoded or "=" in encoded:
        raise ValueError("bearer_protocol_invalid")
    try:
        encoded_bytes = encoded.encode("ascii")
        decoded = base64.urlsafe_b64decode(
            encoded_bytes + b"=" * (-len(encoded_bytes) % 4)
        )
        token = decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise ValueError("bearer_protocol_invalid") from None
    if base64.urlsafe_b64encode(decoded).rstrip(
        b"="
    ) != encoded_bytes or not _is_canonical_bearer(token):
        raise ValueError("bearer_protocol_invalid")
    return token


def _is_canonical_bearer(token: str) -> bool:
    return bool(
        token
        and token == token.strip()
        and not any(character.isspace() or character == "\x00" for character in token)
    )
