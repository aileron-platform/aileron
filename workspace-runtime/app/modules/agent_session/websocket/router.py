"""WebSocket Router.

提供 Agent Session WebSocket 端點。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config.settings import get_settings
from .manager import ConnectionManager, get_connection_manager
from .replay_store import get_websocket_replay_store
from app.database import async_session_scope
from app.services.auth_service import SimpleUser, get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-session-websocket"])


@router.websocket("/ws/agent-sessions/{session_id}")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: Optional[str] = Query(None),
    last_seq: Optional[int] = Query(None, ge=0),
):
    """WebSocket 連線端點 - 訂閱特定 session.
    
    連線後會自動訂閱該 session 的所有事件：
    - sessions patched
    - tasks created/patched
    - messages created
    - streaming:start/chunk/end
    - thinking:start/chunk/end
    - permission:request/approved/denied
    - tool:complete
    
    Client 可以發送的訊息：
    - {"type": "ping"} - 心跳
    - {"type": "subscribe", "session_id": "..."} - 訂閱其他 session
    - {"type": "unsubscribe", "session_id": "..."} - 取消訂閱
    
    Args:
        websocket: WebSocket 連線
        session_id: 要訂閱的 session ID
        user_id: 可選的用戶 ID
        last_seq: 用於 replay 的最後已接收序號（可選）
    """
    manager = get_connection_manager()
    authenticated_user = await _authenticate_websocket(websocket)
    if authenticated_user is None:
        return

    # 建立連線並訂閱 session
    connection_id = await manager.connect(
        websocket,
        user_id=authenticated_user.id,
        session_id=session_id,
    )
    logger.info(f"🔵 WebSocket connected: {connection_id} -> session {session_id[:8]}")
    logger.info(f"   當前連線數: {manager.get_connection_count()}")

    replay_enabled = last_seq is not None and last_seq >= 0
    if replay_enabled:
        replay_enabled = await manager.start_replay_mode(connection_id)

    # 訂閱成功後，查詢會話狀態並發送給客戶端
    try:
        from ..services.agent_session_service import AgentSessionService

        async with async_session_scope() as db:
            service = AgentSessionService(db)
            logger.info(f"🔄 正在查詢會話狀態: {session_id[:8]}")
            session = await service.get_session(session_id)
            if session:
                # 發送 session:init 事件（初始化會話狀態，與真正的 sessions created 區分）
                event_data = AgentSessionService._session_to_event_data(session)
                logger.info(f"📤 準備發送會話狀態給連線 {connection_id}")
                logger.info(f"   事件數據: {event_data}")
                success = await manager.send_to_connection(connection_id, {
                    "type": "session:init",
                    "session_id": session_id,
                    "data": event_data,
                }, bypass_replay_queue=True)
                if success:
                    logger.info(f"✅ 已發送初始會話狀態給連線 {connection_id}")
                else:
                    logger.error(f"❌ 發送會話狀態失敗")
            else:
                logger.warning(f"❌ 找不到會話: {session_id}")

        # 重播 pending tool decision（如 AskUserQuestion）
        await _replay_pending_tool_decision(manager, connection_id, session_id)

        # 若客戶端提供 last_seq，回放缺失事件
        if replay_enabled and last_seq is not None:
            replayed_count = await _replay_session_events(
                manager=manager,
                connection_id=connection_id,
                session_id=session_id,
                last_seq=last_seq,
            )
            logger.info(
                "🔁 Replay sent: session=%s last_seq=%s count=%s",
                session_id[:8],
                last_seq,
                replayed_count,
            )
    except Exception as e:
        logger.warning(f"❌ Failed to fetch session state on initial connection: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if replay_enabled:
            queued_count = await manager.finish_replay_mode(connection_id)
            if queued_count > 0:
                logger.info(
                    "📬 Flushed queued events after replay: session=%s count=%s",
                    session_id[:8],
                    queued_count,
                )

    try:
        while True:
            # 接收客戶端訊息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await _handle_client_message(manager, connection_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        await manager.disconnect(connection_id)


@router.websocket("/ws")
async def websocket_global_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None),
):
    """全域 WebSocket 連線端點.
    
    可以動態訂閱/取消訂閱多個 sessions。
    
    Client 可以發送的訊息：
    - {"type": "ping"} - 心跳
    - {"type": "subscribe", "session_id": "..."} - 訂閱 session
    - {"type": "unsubscribe", "session_id": "..."} - 取消訂閱
    
    Args:
        websocket: WebSocket 連線
        user_id: 可選的用戶 ID
    """
    manager = get_connection_manager()
    authenticated_user = await _authenticate_websocket(websocket)
    if authenticated_user is None:
        return
    
    # 建立連線 (不訂閱任何 session)
    connection_id = await manager.connect(websocket, user_id=authenticated_user.id)
    logger.info(f"Global WebSocket connected: {connection_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await _handle_client_message(manager, connection_id, message)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
        logger.info(f"Global WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.exception(f"Global WebSocket error: {e}")
        await manager.disconnect(connection_id)


async def _handle_client_message(
    manager: ConnectionManager,
    connection_id: str,
    message: Dict[str, Any],
) -> None:
    """處理客戶端訊息.
    
    Args:
        manager: Connection Manager
        connection_id: 連線 ID
        message: 客戶端訊息
    """
    msg_type = message.get("type")
    
    if msg_type == "ping":
        # 心跳回應
        await manager.send_to_connection(connection_id, {"type": "pong"})
        
    elif msg_type == "subscribe":
        # 訂閱 session
        session_id = message.get("session_id")
        if session_id:
            success = await manager.subscribe_session(connection_id, session_id)
            await manager.send_to_connection(connection_id, {
                "type": "subscribed",
                "session_id": session_id,
                "success": success,
            })

            # 訂閱成功後，查詢會話狀態並發送給客戶端
            if success:
                try:
                    # 動態導入以避免循環導入
                    from ..services.agent_session_service import AgentSessionService

                    async with async_session_scope() as db:
                        service = AgentSessionService(db)
                        session = await service.get_session(session_id)
                        if session:
                            # 發送 session:init 事件（初始化會話狀態）
                            event_data = AgentSessionService._session_to_event_data(session)
                            await manager.send_to_connection(connection_id, {
                                "type": "session:init",
                                "session_id": session_id,
                                "data": event_data,
                            })
                except Exception as e:
                    logger.warning(f"Failed to fetch session state on subscribe: {e}")

                # 重播 pending tool decision（如 AskUserQuestion）
                await _replay_pending_tool_decision(manager, connection_id, session_id)
        else:
            await manager.send_to_connection(connection_id, {
                "type": "error",
                "message": "session_id is required",
            })
            
    elif msg_type == "unsubscribe":
        # 取消訂閱 session
        session_id = message.get("session_id")
        if session_id:
            success = await manager.unsubscribe_session(connection_id, session_id)
            await manager.send_to_connection(connection_id, {
                "type": "unsubscribed",
                "session_id": session_id,
                "success": success,
            })
        else:
            await manager.send_to_connection(connection_id, {
                "type": "error",
                "message": "session_id is required",
            })
            
    else:
        # 未知訊息類型
        await manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })


async def _authenticate_websocket(websocket: WebSocket) -> Optional[SimpleUser]:
    """驗證 agent-session WebSocket 連線。"""
    token = _extract_websocket_token(websocket)
    if not token:
        await websocket.close(code=4401, reason="Missing authentication token")
        return None

    settings = get_settings()
    if settings.INTERNAL_API_TOKEN and token == settings.INTERNAL_API_TOKEN:
        return SimpleUser("internal-test-user", username="internal-test-user")

    auth_service = get_auth_service()
    user = await auth_service.validate_access_token(token)
    if user is None:
        await websocket.close(code=4401, reason="Invalid or expired authentication token")
        return None

    return user


def _extract_websocket_token(websocket: WebSocket) -> Optional[str]:
    """從 WebSocket handshake 取得 access token。"""
    authorization = websocket.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return token

    query_token = websocket.query_params.get("token")
    if query_token:
        return query_token.strip()

    internal_header_token = websocket.headers.get("x-internal-token")
    if internal_header_token:
        return internal_header_token.strip()

    internal_query_token = websocket.query_params.get("internal_token")
    if internal_query_token:
        return internal_query_token.strip()

    return None


async def _replay_pending_tool_decision(
    manager: ConnectionManager,
    connection_id: str,
    session_id: str,
) -> None:
    """重播 pending tool decision 給重新連線的客戶端.

    當客戶端重新連線或訂閱 session 時，若 session 有正在等待使用者決策的
    tool decision（如 AskUserQuestion 或 permission request），重新發送
    tool-decision:request 事件，確保前端能恢復互動狀態。
    """
    import json as _json

    from ..domain.enums import TaskStatus
    from ..repositories.task_repository import TaskRepository

    try:
        async with async_session_scope() as db:
            task_repo = TaskRepository(db)
            task = await task_repo.find_active_by_session(session_id)

            if not task or task.status != TaskStatus.AWAITING_PERMISSION.value:
                return

            # 解析 task.data 取得 permission_request
            if not task.data:
                return
            try:
                data = _json.loads(task.data)
            except Exception:
                return

            permission_request = data.get("permission_request")
            if not permission_request:
                return

            request_id = permission_request.get("request_id")
            tool_name = permission_request.get("tool_name", "")
            tool_input = permission_request.get("tool_input", {})
            decision_type = permission_request.get("type", "permission")
            tool_use_id = permission_request.get("tool_use_id")

            if not request_id:
                return

            # 根據 decision_type 重建 options
            if decision_type == "user_input":
                options = [
                    {"option_id": "submit", "name": "提交", "kind": "allow_once", "scope": "once"},
                    {"option_id": "cancel", "name": "取消", "kind": "reject_once", "scope": "once"},
                ]
                timeout = 300
            else:
                options = [
                    {"option_id": "allow_once", "name": "允許一次", "kind": "allow_once", "scope": "once"},
                    {"option_id": "allow_session", "name": "允許此會話", "kind": "allow_always", "scope": "session"},
                    {"option_id": "reject_once", "name": "拒絕", "kind": "reject_once", "scope": "once"},
                ]
                timeout = 60

            tool_call = {
                "toolCallId": tool_use_id or request_id,
                "title": tool_name,
                "kind": "execute",
                "rawInput": tool_input,
            }

            await manager.send_to_connection(connection_id, {
                "type": "tool-decision:request",
                "session_id": session_id,
                "task_id": task.task_id,
                "data": {
                    "request_id": request_id,
                    "decision_type": decision_type,
                    "options": options,
                    "tool_call": tool_call,
                    "timeout": timeout,
                },
            }, bypass_replay_queue=True)

            logger.info(
                "🔄 Replayed pending tool decision: session=%s type=%s tool=%s",
                session_id[:8], decision_type, tool_name,
            )
    except Exception as e:
        logger.warning(f"Failed to replay pending tool decision: {e}")


async def _replay_session_events(
    manager: ConnectionManager,
    connection_id: str,
    session_id: str,
    last_seq: int,
) -> int:
    """回放 session 事件到指定連線."""
    replay_store = get_websocket_replay_store()
    cursor = max(int(last_seq), 0)
    total = 0
    batch_size = 200

    while True:
        events = await replay_store.list_events_since(
            session_id=session_id,
            last_seq=cursor,
            limit=batch_size,
        )
        if not events:
            break

        previous_cursor = cursor
        for event in events:
            sent = await manager.send_to_connection(
                connection_id,
                event,
                bypass_replay_queue=True,
            )
            if not sent:
                return total

            seq = event.get("seq")
            if isinstance(seq, int) and seq > cursor:
                cursor = seq
            total += 1

        # 保護：避免異常資料導致無限迴圈
        if cursor <= previous_cursor:
            break

        if len(events) < batch_size:
            break

        # 讓出事件迴圈，避免大量回放時阻塞其他協程
        await asyncio.sleep(0)

    return total


__all__ = ["router"]
