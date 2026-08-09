"""Authenticated HTTP and WebSocket endpoints for the browser relay."""

from __future__ import annotations

import json
import logging
import uuid
import base64
import binascii
from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
    get_execution_grant_verifier,
)
from app.modules.auth.manager_assertion import (
    ManagerAssertionConflict,
    ManagerAssertionInvalid,
    get_manager_assertion_verifier,
)
from app.modules.runtime_control.state import RuntimeDrainingError

from .models import (
    CreatePageRequest,
    CreatePageResponse,
    DeletePageResponse,
    NamedPagesResponse,
    RelayHealthResponse,
    RelayStatusResponse,
)
from .relay import RelayService, get_relay_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client-browser-relay",
    tags=["Client Browser Relay"],
)


@router.get(
    "/health",
    response_model=RelayHealthResponse,
    summary="Browser relay health",
)
async def browser_relay_health() -> RelayHealthResponse:
    """Return no connection or workload metadata on the public endpoint."""

    return RelayHealthResponse()


@router.get(
    "",
    response_model=RelayStatusResponse,
    summary="Browser relay status",
    responses=build_responses(401, 403, 423, 500, 503),
)
async def get_relay_status(request: Request) -> RelayStatusResponse:
    settings = get_settings()
    service = get_relay_service()
    host_name, port = _request_host(request, settings.PORT)
    relay_status = service.get_status(host_name, port)
    return RelayStatusResponse(
        wsEndpoint=relay_status["wsEndpoint"],
        extensionConnected=relay_status["extensionConnected"],
        mode=relay_status["mode"],
        connectedTargetsCount=relay_status["connectedTargetsCount"],
        playwrightClientsCount=relay_status["playwrightClientsCount"],
    )


@router.get(
    "/pages",
    response_model=NamedPagesResponse,
)
async def list_named_pages() -> NamedPagesResponse:
    return NamedPagesResponse(pages=get_relay_service().get_named_pages())


@router.post(
    "/pages",
    response_model=CreatePageResponse,
    responses=build_responses(400, 401, 403, 423, 500, 503),
)
async def get_or_create_page(
    request: Request,
    body: CreatePageRequest,
) -> CreatePageResponse:
    settings = get_settings()
    service = get_relay_service()
    if not body.name:
        raise _relay_error(400, "BROWSER_PAGE_NAME_REQUIRED")
    if not service.extension_ws:
        raise _relay_error(503, "BROWSER_EXTENSION_NOT_CONNECTED")

    host_name, port = _request_host(request, settings.PORT)
    try:
        result = await service.get_or_create_named_page(body.name, host_name, port)
    except RuntimeDrainingError as exc:
        raise _relay_error(423, exc.error_code) from exc
    except Exception:
        logger.exception("Browser page creation failed")
        raise _relay_error(500, "BROWSER_PAGE_CREATE_FAILED") from None
    if not result:
        raise _relay_error(500, "BROWSER_PAGE_CREATE_FAILED")
    return CreatePageResponse(
        wsEndpoint=result["wsEndpoint"],
        name=result["name"],
        targetId=result["targetId"],
        url=result["url"],
    )


@router.delete(
    "/pages/{name}",
    response_model=DeletePageResponse,
)
async def delete_named_page(name: str) -> DeletePageResponse:
    deleted = await get_relay_service().delete_named_page(name)
    return DeletePageResponse(success=deleted)


@router.websocket("/cdp/{client_id}")
async def cdp_endpoint_with_id(websocket: WebSocket, client_id: str) -> None:
    await _handle_cdp_connection(websocket, client_id)


@router.websocket("/cdp")
async def cdp_endpoint(websocket: WebSocket) -> None:
    await _handle_cdp_connection(websocket, f"client-{uuid.uuid4().hex[:8]}")


async def _handle_cdp_connection(websocket: WebSocket, client_id: str) -> None:
    authenticated, subprotocol = await _authorize_user_websocket(websocket)
    if not authenticated:
        return
    service = get_relay_service()
    await websocket.accept(subprotocol=subprotocol)
    try:
        registered = await service.register_playwright_client(client_id, websocket)
    except RuntimeDrainingError as exc:
        await websocket.close(code=4423, reason=exc.error_code)
        return
    if not registered:
        await websocket.close(code=4409, reason="BROWSER_CLIENT_ID_CONFLICT")
        return

    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                continue
            except WebSocketDisconnect:
                break
            await _route_cdp_message(service, client_id, message)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Browser CDP WebSocket failed")
    finally:
        await service.unregister_playwright_client(client_id)


async def _route_cdp_message(
    service: RelayService, client_id: str, message: dict[str, Any]
) -> None:
    msg_id = message.get("id")
    session_id = message.get("sessionId")
    method = message.get("method", "")
    params = message.get("params", {})
    if not service.extension_ws:
        await service.send_to_playwright(
            {
                "id": msg_id,
                "sessionId": session_id,
                "error": {"code": "BROWSER_EXTENSION_NOT_CONNECTED"},
            },
            client_id,
        )
        return
    try:
        result = await service.route_cdp_command(method, params, session_id)
        if method == "Target.setAutoAttach" and not session_id:
            for target in service.connected_targets.values():
                await service.send_attached_to_target(target, client_id)
        if method == "Target.setDiscoverTargets" and params.get("discover"):
            for target in service.connected_targets.values():
                await service.send_to_playwright(
                    {
                        "method": "Target.targetCreated",
                        "params": {
                            "targetInfo": {
                                "targetId": target.target_info.target_id,
                                "type": target.target_info.type,
                                "title": target.target_info.title,
                                "url": target.target_info.url,
                                "attached": True,
                            }
                        },
                    },
                    client_id,
                )
        if (
            method == "Target.attachToTarget"
            and isinstance(result, dict)
            and result.get("sessionId")
        ):
            target_id = params.get("targetId")
            for target in service.connected_targets.values():
                if target.target_id == target_id:
                    await service.send_attached_to_target(target, client_id)
                    break
        await service.send_to_playwright(
            {"id": msg_id, "sessionId": session_id, "result": result},
            client_id,
        )
    except Exception:
        logger.exception("Browser CDP command failed", extra={"method": method})
        await service.send_to_playwright(
            {
                "id": msg_id,
                "sessionId": session_id,
                "error": {"code": "BROWSER_CDP_COMMAND_FAILED"},
            },
            client_id,
        )


@router.websocket("/extension")
async def extension_endpoint(websocket: WebSocket) -> None:
    if websocket.query_params:
        await websocket.close(code=4401, reason="BROWSER_PAIRING_QUERY_REJECTED")
        return
    assertion = _pairing_assertion_from_protocol(websocket)
    if assertion is None:
        await websocket.close(code=4401, reason="BROWSER_PAIRING_ASSERTION_MISSING")
        return
    try:
        pairing = get_manager_assertion_verifier().verify_browser_pairing(assertion)
    except ManagerAssertionInvalid as exc:
        await websocket.close(code=4401, reason=exc.error_code)
        return
    except ManagerAssertionConflict as exc:
        await websocket.close(code=4409, reason=exc.error_code)
        return

    service = get_relay_service()
    await websocket.accept(subprotocol="aileron-browser-extension")
    try:
        await service.register_extension(websocket, pairing)
    except RuntimeDrainingError as exc:
        await websocket.close(code=4423, reason=exc.error_code)
        return
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.close(
                    code=4400, reason="BROWSER_EXTENSION_MESSAGE_INVALID"
                )
                return
            except WebSocketDisconnect:
                break
            await _handle_extension_message(service, message)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Browser extension WebSocket failed")
    finally:
        if service.extension_ws == websocket:
            await service.unregister_extension()


async def _handle_extension_message(
    service: RelayService, message: dict[str, Any]
) -> None:
    if "id" in message and isinstance(message.get("id"), int):
        service.handle_extension_response(
            message["id"], message.get("result"), message.get("error")
        )
        return
    if message.get("method") == "log":
        params = message.get("params", {})
        logger.info(
            "Browser extension log",
            extra={"extension_level": params.get("level", "info")},
        )
        return
    if message.get("method") != "forwardCDPEvent":
        return
    event_params = message.get("params", {})
    method = event_params.get("method", "")
    params = event_params.get("params", {})
    session_id = event_params.get("sessionId")
    if method == "Target.attachedToTarget":
        await service.handle_target_attached(
            params.get("sessionId", ""), params.get("targetInfo", {})
        )
    elif method == "Target.detachedFromTarget":
        await service.handle_target_detached(params.get("sessionId", ""))
    elif method == "Target.targetInfoChanged":
        await service.handle_target_info_changed(params.get("targetInfo", {}))
    else:
        await service.send_to_playwright(
            {"sessionId": session_id, "method": method, "params": params}
        )


async def _authorize_user_websocket(websocket: WebSocket) -> tuple[bool, str | None]:
    if any(name in websocket.query_params for name in ("token", "access_token")):
        await websocket.close(code=4401, reason="BROWSER_USER_TOKEN_QUERY_REJECTED")
        return False, None
    settings = get_settings()
    origins = settings.effective_allowed_origins
    if len(origins) != 1 or websocket.headers.get("origin") != origins[0]:
        await websocket.close(code=4403, reason="BROWSER_USER_ORIGIN_INVALID")
        return False, None
    authorization = websocket.headers.get("authorization", "")
    protocols = [
        value.strip()
        for value in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if value.strip()
    ]
    if authorization:
        await websocket.close(code=4401, reason="BROWSER_USER_AUTH_HEADER_REJECTED")
        return False, None
    subprotocol = None
    if len(protocols) == 2 and protocols.count("aileron-browser-cdp-v1") == 1:
        bearer = [item for item in protocols if item.startswith("bearer.")]
        if len(bearer) != 1:
            await websocket.close(code=4401, reason="BROWSER_USER_TOKEN_MISSING")
            return False, None
        encoded = bearer[0][7:]
        try:
            raw = encoded.encode("ascii")
            decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
            token = decoded.decode("utf-8")
            if base64.urlsafe_b64encode(decoded).rstrip(b"=") != raw:
                raise ValueError
        except (binascii.Error, UnicodeDecodeError, ValueError):
            await websocket.close(code=4401, reason="BROWSER_USER_TOKEN_INVALID")
            return False, None
        subprotocol = "aileron-browser-cdp-v1"
    else:
        await websocket.close(code=4401, reason="BROWSER_USER_TOKEN_MISSING")
        return False, None
    if not token or token != token.strip() or any(character.isspace() for character in token):
        await websocket.close(code=4401, reason="BROWSER_USER_TOKEN_INVALID")
        return False, None
    try:
        get_execution_grant_verifier().verify(token, action="browser_automation")
    except ExecutionGrantConflict as exc:
        await websocket.close(code=4423, reason=exc.error_code)
        return False, None
    except ExecutionGrantInvalid as exc:
        await websocket.close(code=4401, reason=exc.error_code)
        return False, None
    return True, subprotocol


def _pairing_assertion_from_protocol(websocket: WebSocket) -> str | None:
    protocols = [
        value.strip()
        for value in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if value.strip()
    ]
    if "aileron-browser-extension" not in protocols:
        return None
    assertions = [
        value.removeprefix("assertion.")
        for value in protocols
        if value.startswith("assertion.")
    ]
    if len(assertions) != 1 or not assertions[0]:
        return None
    return assertions[0]


def _request_host(request: Request, default_port: int) -> tuple[str, int]:
    host = request.headers.get("host", f"localhost:{default_port}")
    if ":" not in host:
        return host, default_port
    host_name, port_value = host.rsplit(":", 1)
    try:
        return host_name, int(port_value)
    except ValueError:
        return host_name, default_port


def _relay_error(status_code: int, error_code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"errorCode": error_code})


__all__ = ["router"]
