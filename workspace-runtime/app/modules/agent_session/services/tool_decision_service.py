"""Tool Decision Service.

提供工具決策（permission/user_input）相關的業務邏輯。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import (
    PermissionStatus,
    AgentSessionStatus,
    TaskStatus,
    ToolDecisionOutcome,
    ToolDecisionType,
)
from ..repositories.message_repository import MessageRepository
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.agent_session import ToolDecisionRequest


class ToolDecisionServiceError(Exception):
    """Tool Decision Service 錯誤."""

    pass


class ToolDecisionTimeoutError(ToolDecisionServiceError):
    """Tool Decision 請求超時."""

    pass


class ToolDecisionDeniedError(ToolDecisionServiceError):
    """Tool Decision 被拒絕."""

    pass


class ToolDecisionService:
    """Tool Decision Service.

    處理工具執行的決策流程。
    """

    def __init__(
        self,
        db: AsyncSession,
        session_repo: Optional[AgentSessionRepository] = None,
        task_repo: Optional[TaskRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        event_emitter: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """初始化 Service.

        Args:
            db: 資料庫 session
            session_repo: Session Repository (可注入)
            task_repo: Task Repository (可注入)
            message_repo: Message Repository (可注入)
            event_emitter: 事件發送器 (用於 WebSocket)
        """
        self.db = db
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.message_repo = message_repo or MessageRepository(db)
        self.event_emitter = event_emitter

        # 等待中的決策 (request_id -> asyncio.Event)
        # 注意：這些字段目前是實例級別的，而 ToolDecisionService 每次請求都會建立新實例。
        # 真正的 in-memory 等待機制由 global_tool_decision_manager 管理。
        # 這些字段保留是為了向後相容，但實際上不會生效。
        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, ToolDecisionRequest] = {}

        # 追蹤每個 session 的權限請求 (session_id -> set of request_ids)
        # 用於在權限被拒絕時批量取消同一 session 的其他待處理請求
        self._session_requests: Dict[str, set] = {}

    async def create_tool_decision_request(
        self,
        session_id: str,
        task_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[list[Dict[str, Any]]] = None,
        tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> str:
        """建立 Tool Decision 請求.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID
            tool_name: 工具名稱
            tool_input: 工具輸入參數
            tool_use_id: Tool Use ID
            timeout_seconds: 超時秒數

        Returns:
            request_id
        """
        request_id = str(uuid.uuid4())
        now = utcnow()

        # 建立決策請求資料
        permission_request = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "requested_at": now.isoformat(),
        }
        if tool_use_id:
            permission_request["tool_use_id"] = tool_use_id
        if tool_call_id:
            permission_request["tool_call_id"] = tool_call_id
        if options is not None:
            permission_request["options"] = options
        if tool_call is not None:
            permission_request["raw_tool_call"] = tool_call

        # 更新 task 狀態
        await self.task_repo.set_awaiting_permission(task_id, permission_request)

        # 更新 session 狀態
        await self.session_repo.update_status(session_id, AgentSessionStatus.AWAITING_PERMISSION)

        # 建立決策請求訊息
        await self._create_permission_message(
            session_id=session_id,
            task_id=task_id,
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
            decision_type=decision_type,
            options=options or [],
            raw_tool_call=tool_call,
            tool_call_id=tool_call_id,
        )

        # 發送 WebSocket 事件
        if self.event_emitter:
            tool_call_payload = tool_call or {
                "toolCallId": tool_use_id or request_id,
                "title": tool_name,
                "kind": "execute",
                "rawInput": tool_input,
            }
            self.event_emitter("tool-decision:request", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
                "decision_type": decision_type,
                "options": options or [],
                "tool_call": tool_call_payload,
                "timeout": timeout_seconds,
            })

        # 追蹤此 session 的權限請求
        if session_id not in self._session_requests:
            self._session_requests[session_id] = set()
        self._session_requests[session_id].add(request_id)

        return request_id

    async def wait_for_decision(
        self,
        request_id: str,
        timeout_seconds: int = 60,
    ) -> ToolDecisionRequest:
        """等待 Tool Decision.

        Args:
            request_id: 請求 ID
            timeout_seconds: 超時秒數

        Returns:
            權限決策

        Raises:
            ToolDecisionTimeoutError: 超時
        """
        # 建立等待事件
        event = asyncio.Event()
        self._pending_decisions[request_id] = event

        try:
            # 等待決策或超時
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)

            # 取得決策結果
            decision = self._decision_results.get(request_id)
            if not decision:
                raise ToolDecisionServiceError(f"Decision not found for request: {request_id}")

            return decision

        except asyncio.TimeoutError:
            raise ToolDecisionTimeoutError(f"Tool decision request timed out: {request_id}")

        finally:
            # 清理
            self._pending_decisions.pop(request_id, None)
            self._decision_results.pop(request_id, None)

    async def resolve_decision(
        self,
        decision: ToolDecisionRequest,
    ) -> bool:
        """處理 Tool Decision.

        Args:
            decision: 決策請求

        Returns:
            是否成功處理
        """
        request_id = decision.request_id

        # 取得 task
        task_model = await self.task_repo.find_by_id(decision.task_id)
        if not task_model:
            raise ToolDecisionServiceError(f"Task not found: {decision.task_id}")

        session_id = task_model.session_id

        # 根據 option kind/outcome 判斷是否批准
        approved, derived_scope = await self._resolve_decision_outcome(
            session_id=session_id,
            request_id=request_id,
            decision=decision,
        )

        # 更新決策請求訊息
        status = PermissionStatus.APPROVED.value if approved else PermissionStatus.DENIED.value
        await self._update_permission_message(
            session_id=session_id,
            request_id=request_id,
            status=status,
            scope=(decision.scope.value if decision.scope else derived_scope),
            approved_by=decision.decided_by,
            decision_type=decision.decision_type.value,
            outcome=decision.outcome.value,
            option_id=decision.option_id,
            reason=decision.reason,
            decision_content=decision.content,
        )

        # 更新 task 狀態（user_input 不強制更新狀態，交由 hooks 控制）
        if decision.decision_type == ToolDecisionType.PERMISSION:
            if approved:
                # 批准 - 恢復執行
                await self.task_repo.update(decision.task_id, {"status": TaskStatus.RUNNING.value})
                await self.session_repo.update_status(session_id, AgentSessionStatus.RUNNING)
            else:
                # 拒絕 - 標記失敗
                await self.task_repo.fail_task(
                    decision.task_id,
                    error_message=decision.reason or "Permission denied",
                )
                await self.session_repo.update_status(session_id, AgentSessionStatus.IDLE)
                # 取消同一 session 中其他待處理的權限請求
                await self.cancel_pending_requests(session_id)

        # 儲存決策結果並通知等待者
        self._decision_results[request_id] = decision
        event = self._pending_decisions.get(request_id)
        if event:
            event.set()

        # 發送 WebSocket 事件
        if self.event_emitter:
            event_name = "tool-decision:approved" if approved else "tool-decision:denied"
            self.event_emitter(event_name, {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": decision.task_id,
                "decision_type": decision.decision_type.value,
                "outcome": decision.outcome.value,
                "option_id": decision.option_id,
                "scope": (decision.scope.value if decision.scope else derived_scope),
                "decided_by": decision.decided_by,
                "reason": decision.reason,
            })

        return True

    async def handle_timeout(
        self,
        request_id: str,
        task_id: str,
    ) -> None:
        """處理 Tool Decision 請求超時.

        Args:
            request_id: 請求 ID
            task_id: 任務 ID
        """
        task_model = await self.task_repo.find_by_id(task_id)
        if not task_model:
            return

        session_id = task_model.session_id

        # 更新權限請求訊息
        await self._update_permission_message(
            session_id=session_id,
            request_id=request_id,
            status=PermissionStatus.DENIED.value,
            approved_by="system",
        )

        # 標記 task 失敗
        await self.task_repo.fail_task(task_id, error_message="Tool decision request timed out")

        # 更新 session 狀態
        await self.session_repo.update_status(session_id, AgentSessionStatus.IDLE)

        # 發送 WebSocket 事件
        if self.event_emitter:
            self.event_emitter("tool-decision:timeout", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
            })

    async def cancel_request(
        self,
        request_id: str,
    ) -> None:
        """取消 Tool Decision 請求.

        Args:
            request_id: 請求 ID
        """
        # 通知等待者
        event = self._pending_decisions.get(request_id)
        if event:
            # 建立一個取消的決策
            self._decision_results[request_id] = ToolDecisionRequest(
                request_id=request_id,
                task_id="",
                decision_type=ToolDecisionType.PERMISSION,
                outcome=ToolDecisionOutcome.CANCELLED,
                decided_by="system",
                reason="Request cancelled",
            )
            event.set()

    async def cancel_pending_requests(
        self,
        session_id: str,
    ) -> int:
        """取消指定 session 的所有待處理權限請求.

        當權限被拒絕時調用，自動取消該 session 中所有其他待處理的請求。
        參考 agor 的 cancelPendingRequests 實現。

        Args:
            session_id: 會話 ID

        Returns:
            取消的請求數量
        """
        request_ids = self._session_requests.get(session_id, set()).copy()
        cancelled_count = 0

        for request_id in request_ids:
            event = self._pending_decisions.get(request_id)
            if event:
                self._decision_results[request_id] = ToolDecisionRequest(
                    request_id=request_id,
                    task_id="",
                    decision_type=ToolDecisionType.PERMISSION,
                    outcome=ToolDecisionOutcome.CANCELLED,
                    decided_by="system",
                    reason="Cancelled due to previous permission denial",
                )
                event.set()
                cancelled_count += 1

        # 清理 session 的請求追蹤
        self._session_requests.pop(session_id, None)

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} pending request(s) for session {session_id[:8]}")

        return cancelled_count

    async def _resolve_decision_outcome(
        self,
        session_id: str,
        request_id: str,
        decision: ToolDecisionRequest,
    ) -> tuple[bool, Optional[str]]:
        """解析決策結果與預設 scope."""
        approved = decision.outcome == ToolDecisionOutcome.SELECTED
        derived_scope: Optional[str] = None

        if decision.outcome == ToolDecisionOutcome.CANCELLED:
            return False, derived_scope

        if decision.option_id:
            content = await self._get_request_content(session_id, request_id)
            options = content.get("options") or []
            option = self._find_option(options, decision.option_id)
            if option:
                kind = option.get("kind")
                option_scope = option.get("scope")
                if isinstance(option_scope, str):
                    derived_scope = option_scope
                if isinstance(kind, str):
                    if kind.startswith("reject"):
                        approved = False
                    elif kind.startswith("allow"):
                        approved = True
                    if derived_scope is None:
                        derived_scope = self._scope_from_option_kind(kind)

        return approved, derived_scope

    async def _get_request_content(self, session_id: str, request_id: str) -> Dict[str, Any]:
        """取得決策請求內容（content blob）."""
        model = await self.message_repo.find_permission_request(session_id, request_id)
        if not model or not model.data:
            return {}
        try:
            data = json.loads(model.data)
        except (TypeError, json.JSONDecodeError):
            return {}
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, dict):
                return content
        return {}

    def _find_option(self, options: list[Any], option_id: str) -> Optional[Dict[str, Any]]:
        """從 options 中找出對應 option."""
        for option in options:
            if not isinstance(option, dict):
                continue
            candidate = option.get("option_id") or option.get("optionId")
            if candidate == option_id:
                return option
        return None

    def _scope_from_option_kind(self, kind: str) -> Optional[str]:
        """根據 option kind 推導 scope."""
        if kind == "allow_once":
            return "once"
        if kind == "allow_always":
            return "session"
        if kind == "reject_always":
            return "session"
        return None

    async def _create_permission_message(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[list[Dict[str, Any]]] = None,
        raw_tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> None:
        """建立權限請求訊息.

        Internal method to create the permission request message.
        """
        from .message_service import MessageService

        message_service = MessageService(
            self.db,
            message_repo=self.message_repo,
            session_repo=self.session_repo,
        )

        await message_service.create_permission_request(
            session_id=session_id,
            task_id=task_id,
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
            decision_type=decision_type,
            options=options,
            raw_tool_call=raw_tool_call,
            tool_call_id=tool_call_id,
        )

    async def _update_permission_message(
        self,
        session_id: str,
        request_id: str,
        status: str,
        scope: Optional[str] = None,
        approved_by: Optional[str] = None,
        decision_type: Optional[str] = None,
        outcome: Optional[str] = None,
        option_id: Optional[str] = None,
        reason: Optional[str] = None,
        decision_content: Optional[str] = None,
    ) -> None:
        """更新決策請求訊息.

        Internal method to update the permission request message status.
        """
        from .message_service import MessageService

        message_service = MessageService(
            self.db,
            message_repo=self.message_repo,
            session_repo=self.session_repo,
        )

        await message_service.update_permission_request(
            session_id=session_id,
            request_id=request_id,
            status=status,
            scope=scope,
            approved_by=approved_by,
            decision_type=decision_type,
            outcome=outcome,
            option_id=option_id,
            reason=reason,
            decision_content=decision_content,
        )


__all__ = [
    "ToolDecisionDeniedError",
    "ToolDecisionService",
    "ToolDecisionServiceError",
    "ToolDecisionTimeoutError",
]
