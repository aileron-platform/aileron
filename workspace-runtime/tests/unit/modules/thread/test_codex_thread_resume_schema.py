from __future__ import annotations

from typing import Any

import pytest
from openai_codex.generated.v2_all import (
    SubAgentActivityKind,
    SubAgentActivityThreadItem,
    ThreadResumeResponse,
)
from pydantic import ValidationError


def _sub_agent_activity(kind: str = "interacted") -> dict[str, object]:
    return {
        "agentPath": "reviewer",
        "agentThreadId": "019f507e-2fe8-7c12-a9fc-48f3d316b569",
        "id": "item-activity-1",
        "kind": kind,
        "type": "subAgentActivity",
    }


def _thread_resume_payload(item: dict[str, object]) -> dict[str, Any]:
    return {
        "approvalPolicy": "on-request",
        "approvalsReviewer": "user",
        "cwd": "/workspace",
        "model": "gpt-5",
        "modelProvider": "openai",
        "sandbox": {"type": "workspaceWrite"},
        "thread": {
            "cliVersion": "0.137.0",
            "createdAt": 1_775_000_000,
            "cwd": "/workspace",
            "ephemeral": False,
            "id": "thread-parent",
            "modelProvider": "openai",
            "preview": "Delegate a review task",
            "sessionId": "session-1",
            "source": "appServer",
            "status": {"type": "idle"},
            "turns": [
                {
                    "id": "turn-1",
                    "items": [item],
                    "itemsView": "full",
                    "status": "completed",
                }
            ],
            "updatedAt": 1_775_000_001,
        },
    }


@pytest.mark.parametrize(
    ("kind", "expected_kind"),
    [
        ("started", SubAgentActivityKind.started),
        ("interacted", SubAgentActivityKind.interacted),
        ("interrupted", SubAgentActivityKind.interrupted),
    ],
)
def test_thread_resume_response_accepts_sub_agent_activity(
    kind: str,
    expected_kind: SubAgentActivityKind,
) -> None:
    activity = _sub_agent_activity(kind)

    response = ThreadResumeResponse.model_validate(_thread_resume_payload(activity))

    parsed_activity = response.thread.turns[0].items[0].root
    assert isinstance(parsed_activity, SubAgentActivityThreadItem)
    assert parsed_activity.agent_path == "reviewer"
    assert parsed_activity.agent_thread_id == "019f507e-2fe8-7c12-a9fc-48f3d316b569"
    assert parsed_activity.kind is expected_kind
    serialized_activity = response.model_dump(by_alias=True, mode="json")["thread"][
        "turns"
    ][0]["items"][0]
    assert serialized_activity == activity


@pytest.mark.parametrize(
    "missing_field",
    ["agentPath", "agentThreadId", "id", "kind", "type"],
)
def test_thread_resume_response_rejects_missing_sub_agent_activity_fields(
    missing_field: str,
) -> None:
    activity = _sub_agent_activity()
    activity.pop(missing_field)

    with pytest.raises(ValidationError):
        ThreadResumeResponse.model_validate(_thread_resume_payload(activity))


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("agentPath", 1),
        ("agentThreadId", 1),
        ("id", 1),
        ("kind", "completed"),
        ("type", "subagentActivity"),
    ],
)
def test_thread_resume_response_rejects_invalid_sub_agent_activity_fields(
    field: str,
    invalid_value: object,
) -> None:
    activity = _sub_agent_activity()
    activity[field] = invalid_value

    with pytest.raises(ValidationError):
        ThreadResumeResponse.model_validate(_thread_resume_payload(activity))
