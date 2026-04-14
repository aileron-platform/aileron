"""
Client Browser Relay Router

WebSocket 和 HTTP 路由端點
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
# HTTP 端點
# ============================================================================


@router.get(
    "/",
    response_model=RelayStatusResponse,
    summary="健康檢查和狀態資訊",
    description="取得 Relay Server 的狀態資訊，包括 WebSocket 端點和擴展連接狀態",
    responses=build_responses(500),
)
async def get_relay_status(request: Request) -> RelayStatusResponse:
    """健康檢查和狀態資訊"""
    settings = get_settings()
    service = get_relay_service()

    # 從 request 取得 host
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
    summary="列出命名頁面",
    description="取得所有命名頁面的列表",
    responses=build_responses(500),
)
async def list_named_pages() -> NamedPagesResponse:
    """列出命名頁面"""
    service = get_relay_service()
    return NamedPagesResponse(pages=service.get_named_pages())


@router.post(
    "/pages",
    response_model=CreatePageResponse,
    summary="獲取或建立命名頁面",
    description="獲取指定名稱的頁面，如果不存在則建立新頁面",
    responses=build_responses(400, 500, 503),
)
async def get_or_create_page(
    request: Request,
    body: CreatePageRequest,
) -> CreatePageResponse:
    """獲取或建立命名頁面"""
    settings = get_settings()
    service = get_relay_service()

    if not body.name:
        raise HTTPException(status_code=400, detail="name is required")

    # 從 request 取得 host
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
    summary="刪除命名頁面",
    description="移除頁面的名稱映射（不會關閉標籤頁）",
    responses=build_responses(500),
)
async def delete_named_page(name: str) -> DeletePageResponse:
    """刪除命名頁面"""
    service = get_relay_service()
    deleted = await service.delete_named_page(name)
    return DeletePageResponse(success=deleted)


# ============================================================================
# WebSocket 端點
# ============================================================================


@router.websocket("/cdp/{client_id}")
async def cdp_endpoint_with_id(websocket: WebSocket, client_id: str) -> None:
    """Playwright 客戶端 WebSocket 端點（帶 client_id）"""
    await _handle_cdp_connection(websocket, client_id)


@router.websocket("/cdp")
async def cdp_endpoint(websocket: WebSocket) -> None:
    """Playwright 客戶端 WebSocket 端點"""
    client_id = f"client-{uuid.uuid4().hex[:8]}"
    await _handle_cdp_connection(websocket, client_id)


async def _handle_cdp_connection(websocket: WebSocket, client_id: str) -> None:
    """處理 Playwright 客戶端 WebSocket 連接"""
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
    """Chrome 擴展 WebSocket 端點"""
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

            # 處理回應
            if "id" in message and isinstance(message.get("id"), int):
                service.handle_extension_response(
                    message["id"],
                    message.get("result"),
                    message.get("error"),
                )
                continue

            # 處理日誌訊息
            if message.get("method") == "log":
                params = message.get("params", {})
                level = params.get("level", "info")
                args = params.get("args", [])
                logger.info(f"[extension:{level}] {' '.join(str(a) for a in args)}")
                continue

            # 處理 CDP 事件
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
        # 只有當這是當前的 extension 連接時才清理
        if service.extension_ws == websocket:
            await service.unregister_extension()
