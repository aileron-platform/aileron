from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.agent_session.domain.enums import TaskStatus
from app.modules.agent_session.schemas.task import TaskResponse


def test_task_response_extracts_codex_token_usage_from_current_raw_shape() -> None:
    usage = TaskResponse._extract_token_usage(
        {
            "type": "codex",
            "token_usage": {
                "last": {
                    "input_tokens": 42,
                    "output_tokens": 5,
                    "total_tokens": 47,
                    "cached_input_tokens": 12,
                },
                "total": {
                    "input_tokens": 142,
                    "output_tokens": 25,
                    "total_tokens": 167,
                    "cached_input_tokens": 32,
                },
                "service_tier": "fast",
            },
        }
    )

    assert usage is not None
    assert usage.input_tokens == 142
    assert usage.output_tokens == 25
    assert usage.total_tokens == 167
    assert usage.cache_read_tokens == 32
    assert usage.cost_usd is None
    assert usage.service_tier == "fast"


def test_task_response_extracts_codex_token_usage_from_flat_raw_shape() -> None:
    usage = TaskResponse._extract_token_usage(
        {
            "type": "codex",
            "token_usage": {
                "input_tokens": 10,
                "output_tokens": 7,
                "total_tokens": 17,
                "cached_input_tokens": 4,
            },
        }
    )

    assert usage is not None
    assert usage.input_tokens == 10
    assert usage.output_tokens == 7
    assert usage.total_tokens == 17
    assert usage.cache_read_tokens == 4


def test_task_response_marks_codex_context_compacted() -> None:
    response = TaskResponse.from_entity(
        SimpleNamespace(
            id="task-1",
            session_id="session-1",
            created_at=datetime.now(timezone.utc),
            created_by="anonymous",
            started_at=None,
            completed_at=None,
            status=TaskStatus.COMPLETED,
            message_range=None,
            permission_request=None,
            description=None,
            full_prompt="prompt",
            model=None,
            tool_use_count=0,
            duration_ms=None,
            agent_session_id=None,
            computed_context_window=10,
            raw_sdk_response={
                "type": "codex",
                "context_compactions": [{"item_id": "compact-1"}],
            },
        )
    )

    assert response.context_compacted is True
