"""Permission Service Unit Tests.

Test Scenarios:
1. Basic request/decision flow
2. Timeout handling
3. Cancellation handling
4. Multiple concurrent requests
5. cancelPendingRequests batch cancellation
6. Different permission scopes
7. SESSION permission scope
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
    """Basic request/decision flow tests."""

    @pytest.mark.asyncio
    async def test_create_permission_request_generates_uuid(self, permission_service):
        """Test creating permission request generates UUID."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            request_id = await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # Verify request_id is valid UUID format
            assert len(request_id) == 36
            assert request_id.count("-") == 4

    @pytest.mark.asyncio
    async def test_create_permission_request_tracks_session(self, permission_service):
        """Test creating permission request tracks session."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            request_id = await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # Verify session_requests tracking
            assert "session-123" in permission_service._session_requests
            assert request_id in permission_service._session_requests["session-123"]

    @pytest.mark.asyncio
    async def test_create_permission_request_emits_event(self, permission_service):
        """Test creating permission request emits WebSocket event."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            await permission_service.create_permission_request(
                session_id="session-123",
                task_id="task-123",
                tool_name="Bash",
                tool_input={"command": "ls"},
            )

            # Verify event emission
            permission_service.event_emitter.assert_called_once()
            call_args = permission_service.event_emitter.call_args
            assert call_args[0][0] == "permission:request"
            assert call_args[0][1]["tool_name"] == "Bash"

    @pytest.mark.asyncio
    async def test_resolve_decision_approve(self, permission_service, mock_repos):
        """Test approve decision."""
        # Setup mock task
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

            # Create waiting event
            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            result = await permission_service.resolve_decision(decision)

            assert result is True
            # Verify event is set
            assert event.is_set()
            # Verify decision result is saved
            assert permission_service._decision_results["req-123"] == decision

    @pytest.mark.asyncio
    async def test_resolve_decision_deny(self, permission_service, mock_repos):
        """Test deny decision."""
        # Setup mock task
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

            # Create waiting event
            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            result = await permission_service.resolve_decision(decision)

            assert result is True
            # Verify task is marked as failed
            fail_calls = [c for c in mock_repos["task_repo"].calls if c["method"] == "fail_task"]
            assert len(fail_calls) == 1
            assert fail_calls[0]["error_message"] == "Security concern"


class TestPermissionServiceTimeout:
    """Timeout handling tests."""

    @pytest.mark.asyncio
    async def test_wait_for_decision_timeout(self, permission_service):
        """Test wait for decision timeout."""
        with pytest.raises(PermissionTimeoutError):
            await permission_service.wait_for_decision("req-123", timeout_seconds=0.1)

    @pytest.mark.asyncio
    async def test_handle_timeout(self, permission_service, mock_repos):
        """Test timeout handling."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock):
            await permission_service.handle_timeout("req-123", "task-123")

            # Verify task is marked as failed
            fail_calls = [c for c in mock_repos["task_repo"].calls if c["method"] == "fail_task"]
            assert len(fail_calls) == 1
            assert "timed out" in fail_calls[0]["error_message"]

            # Verify WebSocket event
            event_calls = permission_service.event_emitter.call_args_list
            timeout_call = [c for c in event_calls if c[0][0] == "permission:timeout"]
            assert len(timeout_call) == 1


class TestPermissionServiceCancel:
    """Cancellation handling tests."""

    @pytest.mark.asyncio
    async def test_cancel_request(self, permission_service):
        """Test cancel single request."""
        event = asyncio.Event()
        permission_service._pending_decisions["req-123"] = event

        await permission_service.cancel_request("req-123")

        # Verify event is set
        assert event.is_set()
        # Verify decision result
        result = permission_service._decision_results["req-123"]
        assert result.allow is False
        assert result.reason == "Request cancelled"

    @pytest.mark.asyncio
    async def test_cancel_pending_requests(self, permission_service):
        """Test batch cancel all requests in session."""
        # Create multiple pending requests
        events = {}
        for i in range(3):
            event = asyncio.Event()
            request_id = f"req-{i}"
            permission_service._pending_decisions[request_id] = event
            events[request_id] = event

        # Track session requests
        permission_service._session_requests["session-123"] = {"req-0", "req-1", "req-2"}

        cancelled = await permission_service.cancel_pending_requests("session-123")

        # Verify cancellation count
        assert cancelled == 3
        # Verify all events are set
        for event in events.values():
            assert event.is_set()
        # Verify session tracking is cleared
        assert "session-123" not in permission_service._session_requests

    @pytest.mark.asyncio
    async def test_cancel_pending_requests_on_deny(self, permission_service, mock_repos):
        """Test auto cancel other requests on deny."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        # Create multiple pending requests
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

            # Create waiting event
            event = asyncio.Event()
            permission_service._pending_decisions["req-0"] = event

            await permission_service.resolve_decision(decision)

            # Verify session tracking is cleared (other requests cancelled)
            assert "session-123" not in permission_service._session_requests


class TestPermissionServiceConcurrent:
    """Concurrent request tests."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_session(self, permission_service):
        """Test multiple concurrent requests in same session."""
        with patch.object(permission_service, "_create_permission_message", new_callable=AsyncMock):
            # Create multiple requests
            request_ids = []
            for i in range(5):
                request_id = await permission_service.create_permission_request(
                    session_id="session-123",
                    task_id=f"task-{i}",
                    tool_name="Bash",
                    tool_input={"command": f"command-{i}"},
                )
                request_ids.append(request_id)

            # Verify all requests are tracked
            assert len(permission_service._session_requests["session-123"]) == 5
            for request_id in request_ids:
                assert request_id in permission_service._session_requests["session-123"]


class TestPermissionServiceScopes:
    """Permission scope tests."""

    @pytest.mark.asyncio
    async def test_session_scope(self, permission_service, mock_repos):
        """Test SESSION permission scope."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock) as mock_update:
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=True,  # Remember decision
                scope=PermissionScope.SESSION,  # Use SESSION scope
                decided_by="user-123",
            )

            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            await permission_service.resolve_decision(decision)

            # Verify update call includes scope
            mock_update.assert_called_once()
            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["scope"] == "session"

    @pytest.mark.asyncio
    async def test_project_scope(self, permission_service, mock_repos):
        """Test PROJECT permission scope."""
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
        """Test ONCE scope does not remember decision."""
        mock_repos["task_repo"]._tasks["task-123"] = MockTaskModel()

        with patch.object(permission_service, "_update_permission_message", new_callable=AsyncMock) as mock_update:
            decision = PermissionDecisionRequest(
                request_id="req-123",
                task_id="task-123",
                allow=True,
                remember=False,  # Don't remember
                scope=PermissionScope.ONCE,
                decided_by="user-123",
            )

            event = asyncio.Event()
            permission_service._pending_decisions["req-123"] = event

            await permission_service.resolve_decision(decision)

            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["scope"] is None  # When remember=False, scope should be None


class TestPermissionModeMapper:
    """Permission mode mapping tests."""

    def test_map_to_claude_code(self):
        """Test mapping to Claude Code mode."""
        from app.modules.agent_session.domain.enums import AgenticTool, PermissionMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_permission_mode

        # Claude Code native modes
        assert map_permission_mode("default", AgenticTool.CLAUDE_CODE) == PermissionMode.DEFAULT
        assert map_permission_mode("acceptEdits", AgenticTool.CLAUDE_CODE) == PermissionMode.ACCEPT_EDITS
        assert map_permission_mode("bypassPermissions", AgenticTool.CLAUDE_CODE) == PermissionMode.BYPASS_PERMISSIONS
        assert map_permission_mode("dontAsk", AgenticTool.CLAUDE_CODE) == PermissionMode.DONT_ASK
        assert map_permission_mode("auto", AgenticTool.CLAUDE_CODE) == PermissionMode.AUTO

        # Other agent mode mappings
        assert map_permission_mode("yolo", AgenticTool.CLAUDE_CODE) == PermissionMode.BYPASS_PERMISSIONS
        assert map_permission_mode("ask", AgenticTool.CLAUDE_CODE) == PermissionMode.DEFAULT

    def test_map_to_gemini(self):
        """Test mapping to Gemini mode."""
        from app.modules.agent_session.domain.enums import AgenticTool, PermissionMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_permission_mode

        # Gemini native modes
        assert map_permission_mode("autoEdit", AgenticTool.GEMINI) == PermissionMode.ACCEPT_EDITS
        assert map_permission_mode("yolo", AgenticTool.GEMINI) == PermissionMode.BYPASS_PERMISSIONS

        # Claude Code mode mappings
        assert map_permission_mode("acceptEdits", AgenticTool.GEMINI) == PermissionMode.ACCEPT_EDITS

    def test_map_to_codex_config(self):
        """Test mapping to Codex config."""
        from app.modules.agent_session.domain.enums import CodexApprovalPolicy, CodexSandboxMode
        from app.modules.agent_session.utils.permission_mode_mapper import map_to_codex_permission_config

        config = map_to_codex_permission_config("ask")
        assert config["sandbox_mode"] == CodexSandboxMode.STRICT
        assert config["approval_policy"] == CodexApprovalPolicy.MANUAL

        config = map_to_codex_permission_config("allow-all")
        assert config["sandbox_mode"] == CodexSandboxMode.OFF
        assert config["approval_policy"] == CodexApprovalPolicy.AUTO
