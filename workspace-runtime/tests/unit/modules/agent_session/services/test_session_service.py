"""AgentSessionService unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.agent_session.domain.entities import AgentSession
from app.modules.agent_session.domain.enums import (
    AgentSessionStatus,
    AgenticTool,
    GeminiPermissionMode,
    PermissionMode,
)
from app.modules.agent_session.domain.value_objects import ModelConfig, PermissionConfig
from app.modules.agent_session.schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionQuery,
    ModelConfigCreate,
    PermissionConfigCreate,
    AgentSessionUpdate,
)
from app.modules.agent_session.services.agent_session_service import AgentSessionService, AgentSessionValidationError
from app.modules.version_control.utils import VersionControlError


class TestAgentSessionService:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        svc = AgentSessionService(mock_db)
        svc.session_repo = MagicMock()
        svc.task_repo = MagicMock()
        svc.emitter = AsyncMock()
        svc.emitter.emit_session_created = AsyncMock(return_value=1)
        svc.emitter.emit_session_patched = AsyncMock(return_value=1)
        svc.git_utils = MagicMock()
        return svc

    def _session_entity(
        self,
        session_id: str = "session-123",
        workspace_id: str = "ws-test",
        status: AgentSessionStatus = AgentSessionStatus.IDLE,
        agentic_tool: AgenticTool = AgenticTool.CLAUDE_CODE,
        archived: bool = False,
        permission_config: PermissionConfig | None = None,
        model_settings: ModelConfig | None = None,
        tasks: list[str] | None = None,
        message_count: int = 0,
        title: str | None = None,
    ) -> AgentSession:
        return AgentSession(
            id=session_id,
            workspace_id=workspace_id,
            created_at=datetime.now(timezone.utc),
            created_by="test-user",
            status=status,
            agentic_tool=agentic_tool,
            archived=archived,
            ready_for_prompt=True,
            permission_config=permission_config,
            model_settings=model_settings,
            tasks=tasks or [],
            message_count=message_count,
            title=title,
        )

    @pytest.mark.asyncio
    async def test_create_session_default_tool(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity()
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.create_session(AgentSessionCreate(workspace_id="ws-123"))

        assert result is entity
        create_payload = service.session_repo.create.await_args.args[0]
        assert create_payload["workspace_id"] == "ws-123"
        assert create_payload["agentic_tool"] == AgenticTool.CLAUDE_CODE.value
        assert json.loads(create_payload["data"])["message_count"] == 0
        service.emitter.emit_session_created.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session_found(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="found-session")
        service.session_repo.find_by_id = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.get_session("found-session")

        assert result is entity

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service) -> None:
        service.session_repo.find_by_id = AsyncMock(return_value=None)

        assert await service.get_session("not-found") is None

    @pytest.mark.asyncio
    async def test_archive_session(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="archived-session", archived=True)
        service.session_repo.archive = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.archive_session("archived-session", "manual")

        assert result is entity
        service.session_repo.archive.assert_awaited_once_with("archived-session", "manual")

    @pytest.mark.asyncio
    async def test_update_session_status(self, service) -> None:
        existing = MagicMock()
        existing.data = json.dumps({"title": "before"})
        updated = MagicMock()
        entity = self._session_entity(session_id="status-session", status=AgentSessionStatus.RUNNING)
        service.session_repo.find_by_id = AsyncMock(return_value=existing)
        service.session_repo.update = AsyncMock(return_value=updated)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.update_session(
            "status-session",
            AgentSessionUpdate(status=AgentSessionStatus.RUNNING),
        )

        assert result is entity
        update_payload = service.session_repo.update.await_args.args[1]
        assert update_payload["status"] == AgentSessionStatus.RUNNING.value
        service.emitter.emit_session_patched.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_session(self, service, monkeypatch) -> None:
        service.session_repo.delete = AsyncMock(return_value=True)
        cleanup = MagicMock()
        monkeypatch.setattr(
            "app.modules.agent_session.services.execution_service.ExecutionService.cleanup_session_lock",
            cleanup,
        )

        result = await service.delete_session("delete-session")

        assert result is True
        cleanup.assert_called_once_with("delete-session")

    @pytest.mark.asyncio
    async def test_find_sessions(self, service) -> None:
        models = [MagicMock(), MagicMock()]
        entities = [
            self._session_entity(session_id="s1"),
            self._session_entity(session_id="s2", status=AgentSessionStatus.RUNNING),
        ]
        service.session_repo.find_all = AsyncMock(return_value=models)
        service.session_repo.count = AsyncMock(return_value=2)
        service.session_repo.to_entity = MagicMock(side_effect=entities)

        sessions, total = await service.find_sessions(AgentSessionQuery(workspace_id="ws-1"))

        assert [session.id for session in sessions] == ["s1", "s2"]
        assert total == 2

    @pytest.mark.asyncio
    async def test_create_session_serializes_permission_model_and_context_window(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="rich-session")
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        payload = AgentSessionCreate(
            workspace_id="ws-rich",
            user_id="user-1",
            title="My Session",
            context_files=["a.py"],
            agentic_tool=AgenticTool.GEMINI,
            permission_config=PermissionConfigCreate(mode=PermissionMode.ACCEPT_EDITS),
            model_config=ModelConfigCreate(
                mode="exact",
                model="gemini-2.5-pro",
                thinkingMode="auto",
                manualThinkingTokens=128,
                provider="google",
            ),
        )

        await service.create_session(payload)

        create_payload = service.session_repo.create.await_args.args[0]
        data_blob = json.loads(create_payload["data"])
        assert create_payload["created_by"] == "user-1"
        assert create_payload["agentic_tool"] == AgenticTool.GEMINI.value
        assert data_blob["title"] == "My Session"
        assert data_blob["contextFiles"] == ["a.py"]
        assert data_blob["permission_config"]["mode"] == PermissionMode.ACCEPT_EDITS.value
        assert data_blob["model_config"]["provider"] == "google"
        assert data_blob["model_config"]["thinkingMode"] == "auto"
        assert data_blob["model_config"]["manualThinkingTokens"] == 128
        assert data_blob["context_window_limit"] == 1000000

    @pytest.mark.asyncio
    async def test_create_session_defaults_gemini_permission_to_yolo(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="gemini-default")
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        await service.create_session(
            AgentSessionCreate(
                workspace_id="ws-gemini",
                agentic_tool=AgenticTool.GEMINI,
            )
        )

        data_blob = json.loads(service.session_repo.create.await_args.args[0]["data"])
        assert data_blob["permission_config"]["mode"] == PermissionMode.DEFAULT.value
        assert data_blob["permission_config"]["gemini"] == GeminiPermissionMode.YOLO.value

    @pytest.mark.asyncio
    async def test_create_session_persists_git_context_and_workspace_path(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="context-session")
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)
        service.git_utils.resolve_context_path.return_value = Path("/workspace/.worktrees/feature-auth")

        await service.create_session(
            AgentSessionCreate(
                workspace_id="ws-context",
                git_context_id="worktree:feature-auth",
            )
        )

        service.git_utils.resolve_context_path.assert_called_once_with(
            "ws-context",
            "worktree:feature-auth",
        )
        data_blob = json.loads(service.session_repo.create.await_args.args[0]["data"])
        assert data_blob["custom_context"] == {
            "git_context_id": "worktree:feature-auth",
            "workspace_path": "/workspace/.worktrees/feature-auth",
        }

    @pytest.mark.asyncio
    async def test_create_session_persists_explicit_knowledge_workspace_path(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(session_id="knowledge-session")
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        await service.create_session(
            AgentSessionCreate(
                workspace_id="ws-knowledge",
                workspace_path="/knowledge/team-docs",
            )
        )

        data_blob = json.loads(service.session_repo.create.await_args.args[0]["data"])
        assert data_blob["custom_context"] == {
            "workspace_path": "/knowledge/team-docs",
        }

    @pytest.mark.asyncio
    async def test_create_session_rejects_workspace_path_outside_runtime_roots(self, service) -> None:
        service.session_repo.create = AsyncMock()

        with pytest.raises(AgentSessionValidationError) as exc_info:
            await service.create_session(
                AgentSessionCreate(
                    workspace_id="ws-invalid",
                    workspace_path="/etc",
                )
            )

        assert exc_info.value.to_dict() == {
            "errorCode": "AGENT_SESSION_WORKSPACE_PATH_OUTSIDE_ALLOWED_ROOTS",
            "messageKey": "agentSession.errors.workspacePath.outsideAllowedRoots",
            "params": {"field": "workspacePath", "allowedRoots": ["/workspace", "/knowledge"]},
        }
        service.session_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_session_rejects_relative_workspace_path(self, service) -> None:
        service.session_repo.create = AsyncMock()

        with pytest.raises(AgentSessionValidationError) as exc_info:
            await service.create_session(
                AgentSessionCreate(
                    workspace_id="ws-invalid",
                    workspace_path="knowledge/team-docs",
                )
            )

        assert exc_info.value.to_dict() == {
            "errorCode": "AGENT_SESSION_WORKSPACE_PATH_NOT_ABSOLUTE",
            "messageKey": "agentSession.errors.workspacePath.notAbsolute",
            "params": {"field": "workspacePath"},
        }
        service.session_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_session_propagates_git_context_resolution_errors(self, service) -> None:
        service.git_utils.resolve_context_path.side_effect = VersionControlError(
            "Git context 'missing' not found",
            status_code=404,
            error_code="VC_CONTEXT_NOT_FOUND",
        )

        with pytest.raises(VersionControlError):
            await service.create_session(
                AgentSessionCreate(
                    workspace_id="ws-context",
                    git_context_id="missing",
                )
            )

    @pytest.mark.asyncio
    async def test_create_session_ignores_emitter_error_and_returns_entity(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity()
        service.session_repo.create = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)
        service.emitter.emit_session_created = AsyncMock(side_effect=RuntimeError("boom"))

        result = await service.create_session(AgentSessionCreate(workspace_id="ws-123"))

        assert result is entity

    @pytest.mark.asyncio
    async def test_find_sessions_builds_full_filters(self, service) -> None:
        service.session_repo.find_all = AsyncMock(return_value=[])
        service.session_repo.count = AsyncMock(return_value=0)
        service.session_repo.to_entity = MagicMock()

        await service.find_sessions(
            AgentSessionQuery(
                workspace_id="ws-filter",
                status=AgentSessionStatus.RUNNING,
                agentic_tool=AgenticTool.CODEX,
                archived=True,
                limit=10,
                offset=5,
            )
        )

        filters = service.session_repo.find_all.await_args.kwargs["filters"]
        assert filters == {
            "archived": True,
            "workspace_id": "ws-filter",
            "status": AgentSessionStatus.RUNNING.value,
            "agentic_tool": AgenticTool.CODEX.value,
        }
        assert service.session_repo.count.await_args.args[0] == filters

    @pytest.mark.asyncio
    async def test_update_session_returns_none_when_missing(self, service) -> None:
        service.session_repo.find_by_id = AsyncMock(return_value=None)

        result = await service.update_session("missing", AgentSessionUpdate(title="x"))

        assert result is None

    @pytest.mark.asyncio
    async def test_update_session_returns_existing_entity_when_no_changes(self, service) -> None:
        existing = MagicMock()
        existing.data = json.dumps({"title": "before"})
        entity = self._session_entity(title="before")
        service.session_repo.find_by_id = AsyncMock(return_value=existing)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.update_session("status-session", AgentSessionUpdate())

        assert result is entity
        service.session_repo.update.assert_not_called()
        service.emitter.emit_session_patched.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_session_merges_title_permission_and_model_settings(self, service) -> None:
        existing = MagicMock()
        existing.data = json.dumps({"title": "before", "contextFiles": ["keep.txt"]})
        existing.agentic_tool = AgenticTool.CLAUDE_CODE.value
        updated = MagicMock()
        entity = self._session_entity(
            session_id="updated-session",
            title="after",
            permission_config=PermissionConfig(mode=PermissionMode.BYPASS_PERMISSIONS),
            model_settings=ModelConfig(mode="alias", model="claude-sonnet-4"),
        )
        service.session_repo.find_by_id = AsyncMock(return_value=existing)
        service.session_repo.update = AsyncMock(return_value=updated)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        result = await service.update_session(
            "updated-session",
            AgentSessionUpdate(
                title="after",
                archived=True,
                archived_reason="manual",
                permission_config=PermissionConfigCreate(mode=PermissionMode.BYPASS_PERMISSIONS),
                model_config=ModelConfigCreate(model="claude-sonnet-4"),
            ),
        )

        assert result is entity
        update_payload = service.session_repo.update.await_args.args[1]
        data_blob = json.loads(update_payload["data"])
        assert update_payload["archived"] is True
        assert update_payload["archived_reason"] == "manual"
        assert data_blob["title"] == "after"
        assert data_blob["contextFiles"] == ["keep.txt"]
        assert data_blob["permission_config"]["mode"] == PermissionMode.BYPASS_PERMISSIONS.value
        assert data_blob["model_config"]["model"] == "claude-sonnet-4"
        service.emitter.emit_session_patched.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_session_defaults_missing_gemini_permission_to_yolo(self, service) -> None:
        existing = MagicMock()
        existing.data = json.dumps({"contextFiles": ["keep.txt"]})
        existing.agentic_tool = AgenticTool.GEMINI.value
        updated = MagicMock()
        entity = self._session_entity(
            session_id="gemini-updated",
            agentic_tool=AgenticTool.GEMINI,
        )
        service.session_repo.find_by_id = AsyncMock(return_value=existing)
        service.session_repo.update = AsyncMock(return_value=updated)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        await service.update_session(
            "gemini-updated",
            AgentSessionUpdate(
                permission_config=PermissionConfigCreate(mode=PermissionMode.DEFAULT),
            ),
        )

        data_blob = json.loads(service.session_repo.update.await_args.args[1]["data"])
        assert data_blob["permission_config"]["gemini"] == GeminiPermissionMode.YOLO.value

    @pytest.mark.asyncio
    async def test_update_session_returns_none_when_update_fails(self, service) -> None:
        existing = MagicMock()
        existing.data = json.dumps({})
        service.session_repo.find_by_id = AsyncMock(return_value=existing)
        service.session_repo.update = AsyncMock(return_value=None)

        result = await service.update_session("failed-update", AgentSessionUpdate(title="new"))

        assert result is None

    @pytest.mark.asyncio
    async def test_archive_session_returns_none_when_missing(self, service) -> None:
        service.session_repo.archive = AsyncMock(return_value=None)

        assert await service.archive_session("missing") is None

    @pytest.mark.asyncio
    async def test_get_current_execution_handles_missing_running_session(self, service) -> None:
        service.session_repo.find_running_by_workspace = AsyncMock(return_value=None)

        result = await service.get_current_execution("ws-1")

        assert result == {"has_active_execution": False}

    @pytest.mark.asyncio
    async def test_get_current_execution_returns_active_task_info(self, service) -> None:
        running_session = MagicMock(session_id="session-1", agentic_tool=AgenticTool.CODEX.value)
        active_task = MagicMock(id="task-1", started_at="2026-03-28T00:00:00Z")
        service.session_repo.find_running_by_workspace = AsyncMock(return_value=running_session)
        service.task_repo.find_active_by_session = AsyncMock(return_value=active_task)

        result = await service.get_current_execution("ws-1")

        assert result == {
            "has_active_execution": True,
            "session_id": "session-1",
            "task_id": "task-1",
            "agentic_tool": AgenticTool.CODEX.value,
            "started_at": "2026-03-28T00:00:00Z",
        }

    @pytest.mark.asyncio
    async def test_update_status_add_task_increments_and_context_usage_return_entities(self, service) -> None:
        model = MagicMock()
        entity = self._session_entity(message_count=3)
        service.session_repo.update_status = AsyncMock(return_value=model)
        service.session_repo.add_task = AsyncMock(return_value=model)
        service.session_repo.increment_message_count = AsyncMock(return_value=model)
        service.session_repo.update_context_usage = AsyncMock(return_value=model)
        service.session_repo.to_entity = MagicMock(return_value=entity)

        assert await service.update_status("s1", AgentSessionStatus.RUNNING) is entity
        assert await service.add_task("s1", "t1") is entity
        assert await service.increment_message_count("s1", 2) is entity
        assert await service.update_context_usage("s1", 100, 200) is entity

    @pytest.mark.asyncio
    async def test_update_status_related_methods_return_none_when_repo_returns_none(self, service) -> None:
        service.session_repo.update_status = AsyncMock(return_value=None)
        service.session_repo.add_task = AsyncMock(return_value=None)
        service.session_repo.increment_message_count = AsyncMock(return_value=None)
        service.session_repo.update_context_usage = AsyncMock(return_value=None)

        assert await service.update_status("s1", AgentSessionStatus.RUNNING) is None
        assert await service.add_task("s1", "t1") is None
        assert await service.increment_message_count("s1") is None
        assert await service.update_context_usage("s1", 1) is None

    def test_get_tool_capabilities_helpers_and_event_data(self, service) -> None:
        permission_config = PermissionConfig(mode=PermissionMode.DEFAULT)
        model_settings = ModelConfig(mode="alias", model="claude-sonnet-4")
        entity = self._session_entity(
            session_id="event-session",
            status=AgentSessionStatus.RUNNING,
            agentic_tool=AgenticTool.CLAUDE_CODE,
            permission_config=permission_config,
            model_settings=model_settings,
            tasks=["task-1"],
            message_count=2,
            title="Title",
        )

        assert service.get_tool_capabilities(AgenticTool.CLAUDE_CODE.value).name == "Claude Code"
        assert service.get_tool_capabilities("unknown-tool") is None
        assert AgenticTool.CODEX.value in service.get_all_tool_capabilities()

        event_data = service._session_to_event_data(entity)
        assert event_data["session_id"] == "event-session"
        assert event_data["status"] == AgentSessionStatus.RUNNING.value
        assert event_data["agentic_tool"] == AgenticTool.CLAUDE_CODE.value
        assert event_data["title"] == "Title"
        assert event_data["message_count"] == 2
        assert event_data["tasks"] == ["task-1"]
        assert event_data["permission_config"]["mode"] == PermissionMode.DEFAULT.value
        assert event_data["model_config"]["model"] == "claude-sonnet-4"
