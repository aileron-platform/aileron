"""
Client Browser Relay Router

WebSocket and HTTP route endpoints
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.core.openapi import build_responses
from app.config.settings import get_settings

from .models import (
    CreatePageRequest,
    CreatePageResponse,
    DeletePageResponse,
    NamedPagesResponse,
    RelayStatusResponse,
)
from .service import get_relay_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client-browser-relay",
    tags=["Client Browser Relay"],
)


# ============================================================================
# HTTP Endpoints
# ============================================================================


@router.get(
    "/",
    response_model=RelayStatusResponse,
    summary="Health check and status information",
    description="Get relay server status information, including WebSocket endpoint and extension connection status",
    responses=build_responses(500),
)
async def get_relay_status(request: Request) -> RelayStatusResponse:
    """Health check and status information"""
    settings = get_settings()
    service = get_relay_service()

    # Get host from request
    host = request.headers.get("host", f"localhost:{settings.PORT}")
    if ":" in host:
        host_name, port_str = host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = settings.PORT
    else:
        host_name = host
        port = settings.PORT

    status = service.get_status(host_name, port)
    return RelayStatusResponse(
        ws_endpoint=status["wsEndpoint"],
        extension_connected=status["extensionConnected"],
        mode=status["mode"],
        connected_targets_count=status["connectedTargetsCount"],
        playwright_clients_count=status["playwrightClientsCount"],
    )


@router.get(
    "/pages",
    response_model=NamedPagesResponse,
    summary="List named pages",
    description="Get list of all named pages",
    responses=build_responses(500),
)
async def list_named_pages() -> NamedPagesResponse:
    """List named pages"""
    service = get_relay_service()
    return NamedPagesResponse(pages=service.get_named_pages())


@router.post(
    "/pages",
    response_model=CreatePageResponse,
    summary="Get or create named page",
    description="Get page with specified name, create new page if it doesn't exist",
    responses=build_responses(400, 500, 503),
)
async def get_or_create_page(
    request: Request,
    body: CreatePageRequest,
) -> CreatePageResponse:
    """Get or create named page"""
    settings = get_settings()
    service = get_relay_service()

    if not body.name:
        raise HTTPException(status_code=400, detail="name is required")

    # Get host from request
    host = request.headers.get("host", f"localhost:{settings.PORT}")
    if ":" in host:
        host_name, port_str = host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = settings.PORT
    else:
        host_name = host
        port = settings.PORT

    if not service.extension_ws:
        raise HTTPException(status_code=503, detail="Extension not connected")

    try:
        result = await service.get_or_create_named_page(body.name, host_name, port)
        if not result:
            raise HTTPException(
                status_code=500, detail="Target created but not found in registry"
            )
        return CreatePageResponse(
            ws_endpoint=result["wsEndpoint"],
            name=result["name"],
            target_id=result["targetId"],
            url=result["url"],
        )
    except Exception as e:
        logger.error(f"Error creating page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/pages/{name}",
    response_model=DeletePageResponse,
    summary="Delete named page",
    description="Remove page name mapping (does not close tab)",
    responses=build_responses(500),
)
async def delete_named_page(name: str) -> DeletePageResponse:
    """Delete named page"""
    service = get_relay_service()
    deleted = await service.delete_named_page(name)
    return DeletePageResponse(success=deleted)


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@router.websocket("/cdp/{client_id}")
async def cdp_endpoint_with_id(websocket: WebSocket, client_id: str) -> None:
    """Playwright client WebSocket endpoint (with client_id)"""
    await _handle_cdp_connection(websocket, client_id)


@router.websocket("/cdp")
async def cdp_endpoint(websocket: WebSocket) -> None:
    """Playwright client WebSocket endpoint"""
    client_id = f"client-{uuid.uuid4().hex[:8]}"
    await _handle_cdp_connection(websocket, client_id)


async def _handle_cdp_connection(websocket: WebSocket, client_id: str) -> None:
    """Handle Playwright client WebSocket connection"""
    service = get_relay_service()

    await websocket.accept()

    if not await service.register_playwright_client(client_id, websocket):
        await websocket.close(code=1000, reason="Client ID already connected")
        return

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            except WebSocketDisconnect:
                break

            msg_id = message.get("id")
            session_id = message.get("sessionId")
            method = message.get("method", "")
            params = message.get("params", {})

            if not service.extension_ws:
                await service.send_to_playwright(
                    {
                        "id": msg_id,
                        "sessionId": session_id,
                        "error": {"message": "Extension not connected"},
                    },
                    client_id,
                )
                continue

            try:
                result = await service.route_cdp_command(method, params, session_id)

                # After Target.setAutoAttach, send attachedToTarget for existing targets
                if method == "Target.setAutoAttach" and not session_id:
                    for target in service.connected_targets.values():
                        await service.send_attached_to_target(target, client_id)

                # After Target.setDiscoverTargets, send targetCreated events
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

                # After Target.attachToTarget, send attachedToTarget event
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

            except Exception as e:
                logger.error(f"Error handling CDP command {method}: {e}")
                await service.send_to_playwright(
                    {
                        "id": msg_id,
                        "sessionId": session_id,
                        "error": {"message": str(e)},
                    },
                    client_id,
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        await service.unregister_playwright_client(client_id)


@router.websocket("/extension")
async def extension_endpoint(websocket: WebSocket) -> None:
    """Chrome extension WebSocket endpoint"""
    import time
    connection_id = f"conn-{int(time.time() * 1000)}"
    logger.info(f"[{connection_id}] Extension WebSocket connection initiated")

    service = get_relay_service()

    logger.info(f"[{connection_id}] Accepting WebSocket...")
    await websocket.accept()
    logger.info(f"[{connection_id}] WebSocket accepted, registering extension...")

    await service.register_extension(websocket)
    logger.info(f"[{connection_id}] Extension registered, entering message loop...")

    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.close(code=1000, reason="Invalid JSON")
                return
            except WebSocketDisconnect:
                break

            # Handle response
            if "id" in message and isinstance(message.get("id"), int):
                service.handle_extension_response(
                    message["id"],
                    message.get("result"),
                    message.get("error"),
                )
                continue

            # Handle log message
            if message.get("method") == "log":
                params = message.get("params", {})
                level = params.get("level", "info")
                args = params.get("args", [])
                logger.info(f"[extension:{level}] {' '.join(str(a) for a in args)}")
                continue

            # Handle CDP event
            if message.get("method") == "forwardCDPEvent":
                event_params = message.get("params", {})
                method = event_params.get("method", "")
                params = event_params.get("params", {})
                session_id = event_params.get("sessionId")

                if method == "Target.attachedToTarget":
                    await service.handle_target_attached(
                        params.get("sessionId", ""),
                        params.get("targetInfo", {}),
                    )
                elif method == "Target.detachedFromTarget":
                    await service.handle_target_detached(params.get("sessionId", ""))
                elif method == "Target.targetInfoChanged":
                    await service.handle_target_info_changed(params.get("targetInfo", {}))
                else:
                    # Forward other CDP events to Playwright
                    await service.send_to_playwright({
                        "sessionId": session_id,
                        "method": method,
                        "params": params,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Extension WebSocket error: {e}")
    finally:
        # Only clean up if this is the current extension connection
        if service.extension_ws == websocket:
            await service.unregister_extension()
