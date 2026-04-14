"""Permission Service 單元測試.

測試場景：
1. 基本請求/決策流程
2. 超時處理
3. 取消處理
4. 多個並發請求
5. cancelPendingRequests 批量取消
6. 不同權限範圍
7. SESSION 權限範圍
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.agent_session.domain.enums import (
    AgentSessionStatus,
    PermissionScope,
    PermissionStatus,
    TaskStatus,
)
from app.modules.agent_session.schemas.agent_session import PermissionDecisionRequest
from app.modules.agent_session.services.permission_service import (
    PermissionDeniedError,
    PermissionService,
    PermissionServiceError,
    PermissionTimeoutError,
)


class MockTaskModel:
    """Mock Task Model for testing."""

    def __init__(self, task_id: str = "task-123", session_id: str = "session-123"):
        self.task_id = task_id
        self.session_id = session_id


class MockRepository:
    """Mock Repository base class."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []


class MockSessionRepository(MockRepository):
    """Mock Session Repository."""

    async def update_status(self, session_id: str, status: AgentSessionStatus):
        self.calls.append({"method": "update_status", "session_id": session_id, "status": status})


class MockTaskRepository(MockRepository):
    """Mock Task Repository."""

    def __init__(self):
        super().__init__()
        self._tasks = {}

    async def find_by_id(self, task_id: str) -> Optional[MockTaskModel]:
        return self._tasks.get(task_id, MockTaskModel(task_id=task_id))

    async def set_awaiting_permission(self, task_id: str, permission_request: Dict):
        self.calls.append({
            "method": "set_awaiting_permission",
            "task_id": task_id,
            "permission_request": permission_request,
        })

    async def update(self, task_id: str, data: Dict):
        self.calls.append({"method": "update", "task_id": task_id, "data": data})

    async def fail_task(self, task_id: str, error_message: str):
        self.calls.append({"method": "fail_task", "task_id": task_id, "error_message": error_message})


class MockMessageRepository(MockRepository):
    """Mock Message Repository."""

    pass


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    return {
        "session_repo": MockSessionRepository(),
        "task_repo": MockTaskRepository(),
        "message_repo": MockMessageRepository(),
    }


@pytest.fixture
def permission_service(mock_db, mock_repos):
    """Create PermissionService with mocks."""
    service = PermissionService(
        db=mock_db,
        session_repo=mock_repos["session_repo"],
        task_repo=mock_repos["task_repo"],
        message_repo=mock_repos["message_repo"],
        event_emitter=MagicMock(),
    )
    return service


class TestPermissionServiceBasic:
    """基本請求/決策流程測試."""

    @pytest.mark.asyncio
    async def test_create_permission_request_generates_uuid(self, permission_service):
        """測試建立權限請求會生成 UUID."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            request_id = await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # 驗證 request_id 是有效的 UUID 格式
            assert len(request_id) == 36
            assert request_id.count("-") == 4

    @pytest.mark.asyncio
    async def test_create_permission_request_tracks_session(self, permission_service):
        """測試建立權限請求會追蹤 session."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            request_id = await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # 驗證 session_requests 追蹤
            assert "session-123" in permission_service._session_requests
            assert request_id in permission_service._session_requests["session-123"]

    @pytest.mark.asyncio
    async def test_create_permission_request_emits_event(self, permission_service):
        """測試建立權限請求會發送 WebSocket 事件."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # 驗證事件發送
            permission_service.event_emitter.assert_called_once()
            call_args = permission_service.event_emitter.call_args
            assert call_args[0][0] == "permission:request"
            assert call_args[0][1]["tool_name"] == "Bash"

    @pytest.mark.asyncio
    async def test_resolve_decision_approve(self, permission_service, mock_repos):
        """測試批准決策."""
        # 設置 mock task
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock):
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=False,
                scope=PermissionScope.ONCE,
                decided_by="user-123",
            )

            # 建立等待事件
            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            result = await permission_service.resolve_decision(decision)

            assert result is True
            # 驗證事件被設置
            assert event.is_set()
            # 驗證決策結果被儲存
            assert permission_service._decision_results["req-123"] == decision

    @pytest.mark.asyncio
    async def test_resolve_decision_deny(self, permission_service, mock_repos):
        """測試拒絕決策."""
        # 設置 mock task
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock):
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=False,
                remember=False,
                scope=PermissionScope.ONCE,
                decided_by="user-123",
                reason="Security concern",
            )

            # 建立等待事件
            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            result = await permission_service.resolve_decision(decision)

            assert result is True
            # 驗證 task 被標記為失敗
            fail_calls = [c for c in mock_repos["task_repo"].calls if c["method"] == "fail_task"]
            assert len(fail_calls) == 1
            assert fail_calls[0]["error_message"] == "Security concern"


class TestPermissionServiceTimeout:
    """超時處理測試."""

    @pytest.mark.asyncio
    async def test_wait_for_decision_timeout(self, permission_service):
        """測試等待決策超時."""
        with pytest.raises(PermissionTimeoutError):
            await permission_service.wait_for_decision("req-123", timeout_seconds=0.1)

    @pytest.mark.asyncio
    async def test_handle_timeout(self, permission_service, mock_repos):
        """測試超時處理."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock):
            await permission_service.handle_timeout("req-123", "task-123")

            # 驗證 task 被標記為失敗
            fail_calls = [c for c in mock_repos["task_repo"].calls if c["method"] == "fail_task"]
            assert len(fail_calls) == 1
            assert "timed out" in fail_calls[0]["error_message"]

            # 驗證 WebSocket 事件
            event_calls = permission_service.event_emitter.call_args_list
            timeout_call = [c for c in event_calls if c[0][0] == "permission:timeout"]
            assert len(timeout_call) == 1


class TestPermissionServiceCancel:
    """取消處理測試."""

    @pytest.mark.asyncio
    async def test_cancel_request(self, permission_service):
        """測試取消單個請求."""
        event = asyncio.Event()
        permission_service._pending_decisions["req-123"] = event

        await permission_service.cancel_request("req-123")

        # 驗證事件被設置
        assert event.is_set()
        # 驗證決策結果
        result = permission_service._decision_results["req-123"]
        assert result.allow is False
        assert result.reason == "Request cancelled"

    @pytest.mark.asyncio
    async def test_cancel_pending_requests(self, permission_service):
        """測試批量取消 session 的所有請求."""
        # 建立多個待處理請求
        events = {}
        for i in range(3):
            event = asyncio.Event()
            request_id = f"req-{i}"
            permission_service._pending_decisions[request_id] = event
            events[request_id] = event

        # 追蹤 session 的請求
        permission_service._session_requests["session-123"] = {"req-0", "req-1", "req-2"}

        cancelled = await permission_service.cancel_pending_requests("session-123")

        # 驗證取消數量
        assert cancelled == 3
        # 驗證所有事件被設置
        for event in events.values():
            assert event.is_set()
        # 驗證 session 追蹤被清理
        assert "session-123" not in permission_service._session_requests

    @pytest.mark.asyncio
    async def test_cancel_pending_requests_on_deny(self, permission_service, mock_repos):
        """測試拒絕時自動取消其他請求."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        # 建立多個待處理請求
        for i in range(3):
            event = asyncio.Event()
            permission_service._pending_decisions[f"req-{i}"] = event

        permission_service._session_requests["session-123"] = {"req-0", "req-1", "req-2"}

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock):
            decision = PermissionDecisionRequest(
                request_id="req-0",
                task_id="task-123",
                allow=False,
                remember=False,
                scope=PermissionScope.ONCE,
                decided_by="user-123",
            )

            # 建立等待事件
            event = asyncio.Event()
            permission_service._pending_decisions["req-0"] = event

            await permission_service.resolve_decision(decision)

            # 驗證 session 追蹤被清理（表示其他請求被取消）
            assert "session-123" not in permission_service._session_requests


class TestPermissionServiceConcurrent:
    """並發請求測試."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_session(self, permission_service):
        """測試同一 session 的多個並發請求."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            # 建立多個請求
            request_ids = []
            for i in range(5):
                request_id = await permission_service.create_permission_request(
                    session_id="session-123",
                    task_id=f"task-{i}",
                    tool_name="Bash",
                    tool_input={"command": f"command-{i}"},
                )
                request_ids.append(request_id)

            # 驗證所有請求都被追蹤
            assert len(permission_service._session_requests["session-123"]) == 5
            for request_id in request_ids:
                assert request_id in permission_service._session_requests["session-123"]


class TestPermissionServiceScopes:
    """權限範圍測試."""

    @pytest.mark.asyncio
    async def test_session_scope(self, permission_service, mock_repos):
        """測試 SESSION 權限範圍."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock) as mock_update:
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=True,  # 記住決策
                scope=PermissionScope.SESSION,  # 使用 SESSION 範圍
                decided_by="user-123",
            )

            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            await permission_service.resolve_decision(decision)

            # 驗證更新調用包含 scope
            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["scope"] == "session"

    @pytest.mark.asyncio
    async def test_project_scope(self, permission_service, mock_repos):
        """測試 PROJECT 權限範圍."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock) as mock_update:
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=True,
                scope=PermissionScope.PROJECT,
                decided_by="user-123",
            )

            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            await permission_service.resolve_decision(decision)

            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["scope"] == "project"

    @pytest.mark.asyncio
    async def test_once_scope_no_remember(self, permission_service, mock_repos):
        """測試 ONCE 範圍不記住決策."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock) as mock_update:
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=False,  # 不記住
                scope=PermissionScope.ONCE,
                decided_by="user-123",
            )

            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            await permission_service.resolve_decision(decision)

            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["scope"] is None  # remember=False 時 scope 應為 None


class TestPermissionModeMapper:
    """權限模式映射測試."""

    def test_map_to_claude_code(self):
        """測試映射到 Claude Code 模式."""
        from app.modules.agent_session.domain.enums import AgenticTool, PermissionMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_permission_mode

        # Claude Code 原生模式
        assert map_permission_mode("default", AgenticTool.CLAUDE_CODE) == PermissionMode.DEFAULT
        assert map_permission_mode("acceptEdits", AgenticTool.CLAUDE_CODE) == PermissionMode.ACCEPT_EDITS
        assert map_permission_mode("bypassPermissions", AgenticTool.CLAUDE_CODE) == PermissionMode.BYPASS_PERMISSIONS
        assert map_permission_mode("dontAsk", AgenticTool.CLAUDE_CODE) == PermissionMode.DONT_ASK
        assert map_permission_mode("auto", AgenticTool.CLAUDE_CODE) == PermissionMode.AUTO

        # 其他代理模式映射
        assert map_permission_mode("yolo", AgenticTool.CLAUDE_CODE) == PermissionMode.BYPASS_PERMISSIONS
        assert map_permission_mode("ask", AgenticTool.CLAUDE_CODE) == PermissionMode.DEFAULT

    def test_map_to_gemini(self):
        """測試映射到 Gemini 模式."""
        from app.modules.agent_session.domain.enums import AgenticTool, PermissionMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_permission_mode

        # Gemini 原生模式
        assert map_permission_mode("autoEdit", AgenticTool.GEMINI) == PermissionMode.ACCEPT_EDITS
        assert map_permission_mode("yolo", AgenticTool.GEMINI) == PermissionMode.BYPASS_PERMISSIONS

        # Claude Code 模式映射
        assert map_permission_mode("acceptEdits", AgenticTool.GEMINI) == PermissionMode.ACCEPT_EDITS

    def test_map_to_codex_config(self):
        """測試映射到 Codex 配置."""
        from app.modules.agent_session.domain.enums import CodexApprovalPolicy, CodexSandboxMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_to_codex_permission_config

        config = map_to_codex_permission_config("ask")
        assert config["sandbox_mode"] == CodexSandboxMode.STRICT
        assert config["approval_policy"] == CodexApprovalPolicy.MANUAL

        config = map_to_codex_permission_config("allow-all")
        assert config["sandbox_mode"] == CodexSandboxMode.OFF
        assert config["approval_policy"] == CodexApprovalPolicy.AUTO
