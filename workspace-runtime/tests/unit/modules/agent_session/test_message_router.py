from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.agent_session.domain.enums import MessageType
from app.modules.agent_session.schemas.message import MessageBulkCreate, MessageCreate
from app.modules.agent_session.services.message_service import MessageServiceError

router_module = importlib.import_module("app.modules.agent_session.routers.message_router")


@pytest.mark.asyncio
async def test_message_router_crud_and_bulk(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock()
    message = SimpleNamespace(id="msg-1")
    service.create_message.return_value = message
    service.get_message.side_effect = [message, None]
    service.find_messages.return_value = ([message], 1)
    service.delete_message.side_effect = [True, False]
    service.create_bulk.return_value = [message]

    monkeypatch.setattr(
        router_module.MessageResponse,
        "from_entity",
        classmethod(
            lambda cls, entity: cls(
                message_id=entity.id,
                created_at=datetime.now(timezone.utc),
                session_id="session-1",
                type="user",
                role="user",
                index=0,
            )
        ),
    )

    create_data = MessageCreate(session_id="ignored", content="hello")
    created = await router_module.create_message("session-1", create_data, service)
    fetched = await router_module.get_message("session-1", "msg-1", service)
    listed = await router_module.list_messages("session-1", "task-1", MessageType.USER, None, 10, 0, service)
    bulk = await router_module.create_messages_bulk(
        "session-1",
        MessageBulkCreate(messages=[MessageCreate(session_id="x", content="hello")]),
        service,
    )
    await router_module.delete_message("session-1", "msg-1", service)

    assert create_data.session_id == "session-1"
    assert created.message_id == "msg-1"
    assert fetched.message_id == "msg-1"
    assert listed.total == 1
    assert listed.items[0].message_id == "msg-1"
    assert bulk.created_count == 1
    assert bulk.messages[0].message_id == "msg-1"

    with pytest.raises(HTTPException) as exc_get:
        await router_module.get_message("session-1", "missing", service)
    assert exc_get.value.status_code == 404

    service.find_messages.side_effect = MessageServiceError("bad query")
    with pytest.raises(HTTPException) as exc_list:
        await router_module.list_messages("session-1", None, None, None, 10, 0, service)
    assert exc_list.value.status_code == 400

    with pytest.raises(HTTPException) as exc_delete:
        await router_module.delete_message("session-1", "missing", service)
    assert exc_delete.value.status_code == 404
