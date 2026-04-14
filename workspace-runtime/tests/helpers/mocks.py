"""Mock 服務實作 - 提供單元測試所需的 mock 對象."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.sessions.domain import (
    ApprovalStatus,
    ExecutionStatus,
    MessageRole,
    MessageSource,
    MessageType,
    Session,
    SessionMessage,
    SessionStatus,
    ToolApprovalRequest,
)


class MockSessionRepository:
    """Mock Session Repository."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._workspace_sessions: Dict[str, List[str]] = {}

    async def add(self, session: Session) -> None:
        """添加 session."""
        self._sessions[session.id] = session
        if session.workspace_id not in self._workspace_sessions:
            self._workspace_sessions[session.workspace_id] = []
        self._workspace_sessions[session.workspace_id].append(session.id)

    async def get(self, session_id: str) -> Optional[Session]:
        """獲取 session."""
        return self._sessions.get(session_id)

    async def update_status(self, session_id: str, status: SessionStatus) -> None:
        """更新 session 狀態."""
        session = self._sessions.get(session_id)
        if session:
            session.status = status
            session.updated_at = datetime.now(timezone.utc)

    async def update_summary(
        self,
        session_id: str,
        total_messages: int = 0,
        claude_session_id: Optional[str] = None,
    ) -> None:
        """更新 session 摘要."""
        session = self._sessions.get(session_id)
        if session:
            session.total_messages = total_messages
            if claude_session_id:
                session.claude_session_id = claude_session_id
            session.updated_at = datetime.now(timezone.utc)

    async def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 50,
        offset: int = 0,
        source: Optional[MessageSource] = None,
    ) -> List[Session]:
        """列出 workspace 的 sessions."""
        session_ids = self._workspace_sessions.get(workspace_id, [])
        sessions = [self._sessions[sid] for sid in session_ids if sid in self._sessions]

        if source:
            sessions = [s for s in sessions if s.source == source]

        return sessions[offset : offset + limit]

    async def count_by_workspace(
        self, workspace_id: str, source: Optional[MessageSource] = None
    ) -> int:
        """計算 workspace 的 session 數量."""
        sessions = await self.list_by_workspace(workspace_id, limit=1000)
        if source:
            sessions = [s for s in sessions if s.source == source]
        return len(sessions)

    def clear(self) -> None:
        """清空所有 sessions."""
        self._sessions.clear()
        self._workspace_sessions.clear()


class MockMessageRepository:
    """Mock Message Repository."""

    def __init__(self) -> None:
        self._messages: Dict[str, List[SessionMessage]] = {}

    async def add(self, message: SessionMessage) -> None:
        """添加 message."""
        if message.session_id not in self._messages:
            self._messages[message.session_id] = []
        self._messages[message.session_id].append(message)

    async def add_batch(self, messages: List[SessionMessage]) -> None:
        """批次添加 messages."""
        for message in messages:
            await self.add(message)

    async def list_by_session(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> List[SessionMessage]:
        """列出 session 的 messages."""
        messages = self._messages.get(session_id, [])
        return messages[offset : offset + limit]

    async def count_by_session(self, session_id: str) -> int:
        """計算 session 的 message 數量."""
        return len(self._messages.get(session_id, []))

    def clear(self) -> None:
        """清空所有 messages."""
        self._messages.clear()


class MockWorkspaceStateRepository:
    """Mock Workspace State Repository."""

    def __init__(self) -> None:
        self._states: Dict[str, Dict[str, Any]] = {}

    async def get_state(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """獲取 workspace 狀態."""
        return self._states.get(workspace_id)

    async def save_state(self, workspace_id: str, state: Dict[str, Any]) -> None:
        """保存 workspace 狀態."""
        self._states[workspace_id] = state

    async def delete_state(self, workspace_id: str) -> None:
        """刪除 workspace 狀態."""
        self._states.pop(workspace_id, None)

    def clear(self) -> None:
        """清空所有狀態."""
        self._states.clear()


class MockSessionRegistry:
    """Mock Session Registry."""

    def __init__(self) -> None:
        self._running: Dict[str, ExecutionStatus] = {}
        self._activity: Dict[str, datetime] = {}

    async def is_running(self, session_id: str) -> bool:
        """檢查 session 是否正在運行."""
        return session_id in self._running

    async def mark_running(self, session_id: str) -> None:
        """標記 session 為運行中."""
        self._running[session_id] = ExecutionStatus.RUNNING

    async def mark_finished(
        self, session_id: str, status: ExecutionStatus
    ) -> None:
        """標記 session 已完成."""
        self._running.pop(session_id, None)

    async def remove(self, session_id: str) -> None:
        """移除 session."""
        self._running.pop(session_id, None)

    async def get_running_sessions(self) -> List[str]:
        """獲取所有運行中的 sessions."""
        return list(self._running.keys())

    async def update_activity(self, session_id: str) -> None:
        """更新 session 的最後活動時間."""
        self._activity[session_id] = datetime.now(timezone.utc)

    async def get_last_activity(self, session_id: str) -> Optional[datetime]:
        """獲取 session 的最後活動時間."""
        return self._activity.get(session_id)

    async def get_status(self, session_id: str) -> Optional[ExecutionStatus]:
        """獲取 session 的執行狀態."""
        return self._running.get(session_id)

    def clear(self) -> None:
        """清空所有運行中的 sessions."""
        self._running.clear()
        self._activity.clear()


class MockWorkspaceExecutionManager:
    """Mock Workspace Execution Manager."""

    def __init__(self) -> None:
        self._active_sessions: Dict[str, str] = {}  # workspace_id -> session_id

    async def request_execution(
        self, workspace_id: str, session_id: str
    ) -> tuple[bool, Optional[str]]:
        """請求執行權限."""
        if workspace_id in self._active_sessions:
            return False, self._active_sessions[workspace_id]
        self._active_sessions[workspace_id] = session_id
        return True, None

    async def release_execution(self, workspace_id: str, session_id: str) -> None:
        """釋放執行權限."""
        if self._active_sessions.get(workspace_id) == session_id:
            self._active_sessions.pop(workspace_id)

    async def is_session_active(self, workspace_id: str, session_id: str) -> bool:
        """檢查 session 是否活躍."""
        return self._active_sessions.get(workspace_id) == session_id

    def clear(self) -> None:
        """清空所有活躍 sessions."""
        self._active_sessions.clear()


class MockMessageDispatchService:
    """Mock Message Dispatch Service."""

    def __init__(self) -> None:
        self.dispatched_messages: List[SessionMessage] = []

    async def dispatch(self, message: SessionMessage) -> None:
        """分派 message."""
        self.dispatched_messages.append(message)

    def clear(self) -> None:
        """清空已分派的 messages."""
        self.dispatched_messages.clear()


class MockWebSocketManager:
    """Mock WebSocket Manager."""

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []
        self.connected_clients: Dict[str, List[Any]] = {}

    async def connect(
        self, workspace_id: str, websocket: Any, client_id: str
    ) -> None:
        """連接 WebSocket."""
        if workspace_id not in self.connected_clients:
            self.connected_clients[workspace_id] = []
        self.connected_clients[workspace_id].append(
            {"client_id": client_id, "websocket": websocket}
        )

    async def disconnect(self, workspace_id: str, client_id: str) -> None:
        """斷開 WebSocket."""
        if workspace_id in self.connected_clients:
            self.connected_clients[workspace_id] = [
                c
                for c in self.connected_clients[workspace_id]
                if c["client_id"] != client_id
            ]

    async def send_message(
        self, workspace_id: str, message: Dict[str, Any]
    ) -> None:
        """發送 message."""
        self.sent_messages.append({"workspace_id": workspace_id, "message": message})

    async def broadcast_event(
        self, workspace_id: str, event: Dict[str, Any]
    ) -> None:
        """廣播 event."""
        self.sent_messages.append({"workspace_id": workspace_id, "event": event})

    async def broadcast_message(self, message: SessionMessage) -> None:
        """廣播 message."""
        self.sent_messages.append(
            {
                "workspace_id": message.workspace_id,
                "type": "message",
                "message": message,
            }
        )

    async def notify_session_started(
        self,
        workspace_id: str,
        session_id: str,
        instruction: str,
        model: str,
        status: str,
        started_at: datetime,
    ) -> None:
        """通知 session 已啟動."""
        self.sent_messages.append(
            {
                "workspace_id": workspace_id,
                "type": "session_started",
                "session_id": session_id,
                "instruction": instruction,
                "model": model,
                "status": status,
                "started_at": started_at,
            }
        )

    async def notify_session_completed(
        self,
        workspace_id: str,
        session_id: str,
        status: str,
        total_messages: int,
        has_error: bool,
        completed_at: datetime,
        error_message: Optional[str] = None,
    ) -> None:
        """通知 session 已完成."""
        self.sent_messages.append(
            {
                "workspace_id": workspace_id,
                "type": "session_completed",
                "session_id": session_id,
                "status": status,
                "total_messages": total_messages,
                "has_error": has_error,
                "completed_at": completed_at,
                "error_message": error_message,
            }
        )

    def clear(self) -> None:
        """清空所有數據."""
        self.sent_messages.clear()
        self.connected_clients.clear()


class MockUnifiedCLIManager:
    """Mock Unified CLI Manager."""

    def __init__(
        self,
        workspace_id: str = "test-workspace",
        workspace_path: str = "/tmp/test-workspace",
        session_id: str = "test-session",
        user_id: str = "test-user",
        session_source: str = "web",
        approval_service: Optional[Any] = None,
    ) -> None:
        self.workspace_id = workspace_id
        self.workspace_path = workspace_path
        self.session_id = session_id
        self.user_id = user_id
        self.session_source = session_source
        self.approval_service = approval_service
        self.aborted = False
        self.execution_count = 0

    async def execute_instruction(
        self,
        instruction: str,
        cli_type: Any,
        images: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        cli_session_id: Optional[str] = None,
        permission_mode: Optional[str] = None,
    ):
        """執行指令並返回 mock 消息流 - 返回異步生成器."""
        async def _generator():
            self.execution_count += 1

            # 模擬返回一些消息
            messages = [
                {
                    "id": str(uuid4()),
                    "user_id": self.user_id,
                    "role": MessageRole.ASSISTANT.value,
                    "message_type": MessageType.CHAT.value,
                    "normalized_content": f"Processing: {instruction}",
                    "cli_source": "claude",
                    "raw_content": {"session_id": cli_session_id or str(uuid4())},
                    "metadata": {},
                    "sequence": 1,
                    "token_count": 100,
                    "duration_ms": 50,
                    "cost_usd": 0.001,
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": str(uuid4()),
                    "user_id": self.user_id,
                    "role": MessageRole.ASSISTANT.value,
                    "message_type": MessageType.CHAT.value,
                    "normalized_content": "Task completed successfully",
                    "cli_source": "claude",
                    "raw_content": {},
                    "metadata": {},
                    "sequence": 2,
                    "token_count": 50,
                    "duration_ms": 30,
                    "cost_usd": 0.0005,
                    "created_at": datetime.now(timezone.utc),
                },
            ]

            for message in messages:
                if self.aborted:
                    break
                await asyncio.sleep(0.001)  # 模擬處理時間
                yield message

        return _generator()

    async def abort_execution(self, session_id: str) -> bool:
        """中止執行."""
        self.aborted = True
        return True


def create_mock_cli_manager_factory():
    """創建 mock CLI manager factory."""

    def factory(**kwargs):
        return MockUnifiedCLIManager(**kwargs)

    return factory


def create_test_session(
    session_id: Optional[str] = None,
    workspace_id: str = "test-workspace",
    instruction: str = "Test instruction",
    model: str = "claude-3-5-sonnet-20241022",
    status: SessionStatus = SessionStatus.IDLE,
    source: MessageSource = MessageSource.USER,
    user_id: Optional[str] = "test-user",
) -> Session:
    """創建測試用 session."""
    return Session(
        id=session_id or str(uuid4()),
        workspace_id=workspace_id,
        instruction=instruction,
        model=model,
        status=status,
        source=source,
        user_id=user_id,
        claude_session_id=None,
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        metadata={},
    )


def create_test_message(
    message_id: Optional[str] = None,
    session_id: str = "test-session",
    workspace_id: str = "test-workspace",
    user_id: str = "test-user",
    role: MessageRole = MessageRole.ASSISTANT,
    message_type: MessageType = MessageType.CHAT,
    content: str = "Test message",
) -> SessionMessage:
    """創建測試用 message."""
    return SessionMessage(
        id=message_id or str(uuid4()),
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        message_type=message_type,
        normalized_content=content,
        cli_source="claude",
        raw_content={},
        metadata={},
        sequence=1,
        token_count=100,
        duration_ms=50,
        cost_usd=0.001,
        created_at=datetime.now(timezone.utc),
    )


__all__ = [
    "MockSessionRepository",
    "MockMessageRepository",
    "MockWorkspaceStateRepository",
    "MockSessionRegistry",
    "MockWorkspaceExecutionManager",
    "MockMessageDispatchService",
    "MockWebSocketManager",
    "MockUnifiedCLIManager",
    "create_mock_cli_manager_factory",
    "create_test_session",
    "create_test_message",
]
