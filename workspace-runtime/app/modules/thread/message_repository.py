from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.thread.persistence_models import (
    ThreadMessageModel,
    ThreadModel,
    ThreadToolResultContentModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
    TIMELINE_ANCHOR_TYPES,
)


class ThreadMessageRepository:
    """Thread-sequenced append-only repository for timeline messages."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def append(
        self,
        thread_id: str,
        turn_id: str,
        turn_execution_id: str,
        type_: str,
        content: dict[str, Any],
        *,
        source_event_key: str,
        parent_tool_use_id: int | None = None,
        tool_call_key: str | None = None,
        result_kind: str | None = None,
    ) -> ThreadMessageModel:
        existing = await self._find_source_event(turn_execution_id, source_event_key)
        if existing is not None:
            return self._assert_replay(
                existing,
                type_=type_,
                content=content,
                parent_tool_use_id=parent_tool_use_id,
                tool_call_key=tool_call_key,
                result_kind=result_kind,
            )

        thread = await self.db.scalar(
            select(ThreadModel).where(ThreadModel.id == thread_id).with_for_update()
        )
        existing = await self._find_source_event(turn_execution_id, source_event_key)
        if existing is not None:
            return self._assert_replay(
                existing,
                type_=type_,
                content=content,
                parent_tool_use_id=parent_tool_use_id,
                tool_call_key=tool_call_key,
                result_kind=result_kind,
            )

        turn = await self.db.get(ThreadTurnModel, turn_id)
        execution = await self.db.get(ThreadTurnExecutionModel, turn_execution_id)
        if (
            thread is None
            or turn is None
            or execution is None
            or turn.thread_id != thread_id
            or execution.turn_id != turn_id
        ):
            raise ValueError("timeline_parent_not_found")
        if type_ == "tool_call" and not tool_call_key:
            raise ValueError("tool_call_key_required")
        if type_ == "tool_result":
            if parent_tool_use_id is None:
                raise ValueError("tool_result_parent_required")
            if result_kind not in {"provider_result", "interaction_answer"}:
                raise ValueError("tool_result_kind_required")
        elif result_kind is not None:
            raise ValueError("result_kind_forbidden")
        if parent_tool_use_id is not None:
            parent = await self.db.get(ThreadMessageModel, parent_tool_use_id)
            if (
                parent is None
                or parent.type != "tool_call"
                or parent.thread_id != thread_id
                or parent.turn_id != turn_id
                or parent.turn_execution_id != turn_execution_id
            ):
                raise ValueError("invalid_tool_parent")
        if type_ == "tool_result":
            existing_result = await self.db.scalar(
                select(ThreadMessageModel).where(
                    and_(
                        ThreadMessageModel.type == "tool_result",
                        ThreadMessageModel.parent_tool_use_id == parent_tool_use_id,
                        ThreadMessageModel.result_kind == result_kind,
                    )
                )
            )
            if existing_result is not None:
                return self._assert_replay(
                    existing_result,
                    type_=type_,
                    content=content,
                    parent_tool_use_id=parent_tool_use_id,
                    tool_call_key=None,
                    result_kind=result_kind,
                )

        next_sequence = int(
            await self.db.scalar(
                select(
                    func.coalesce(func.max(ThreadMessageModel.message_sequence), 0) + 1
                ).where(ThreadMessageModel.thread_id == thread_id)
            )
            or 1
        )
        message = ThreadMessageModel(
            thread_id=thread_id,
            turn_id=turn_id,
            turn_execution_id=turn_execution_id,
            message_sequence=next_sequence,
            type=type_,
            content=content,
            source_event_key=source_event_key,
            parent_tool_use_id=parent_tool_use_id,
            tool_call_key=tool_call_key,
            result_kind=result_kind,
        )
        self.db.add(message)
        thread.version += 1
        turn.version += 1
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def _find_source_event(
        self, turn_execution_id: str, source_event_key: str
    ) -> ThreadMessageModel | None:
        message = await self.db.scalar(
            select(ThreadMessageModel).where(
                and_(
                    ThreadMessageModel.turn_execution_id == turn_execution_id,
                    ThreadMessageModel.source_event_key == source_event_key,
                )
            )
        )
        return message if isinstance(message, ThreadMessageModel) else None

    @staticmethod
    def _assert_replay(
        existing: ThreadMessageModel,
        *,
        type_: str,
        content: dict[str, Any],
        parent_tool_use_id: int | None,
        tool_call_key: str | None,
        result_kind: str | None,
    ) -> ThreadMessageModel:
        if (
            existing.type != type_
            or existing.content != content
            or existing.parent_tool_use_id != parent_tool_use_id
            or existing.tool_call_key != tool_call_key
            or existing.result_kind != result_kind
        ):
            raise ValueError("source_event_key_conflict")
        return existing

    async def list_timeline_anchors(
        self,
        thread_id: str,
        *,
        before_sequence: int | None,
        limit: int,
    ) -> list[ThreadMessageModel]:
        filters = [
            ThreadMessageModel.thread_id == thread_id,
            ThreadMessageModel.type.in_(TIMELINE_ANCHOR_TYPES),
        ]
        if before_sequence is not None:
            filters.append(ThreadMessageModel.message_sequence < before_sequence)
        result = await self.db.execute(
            select(ThreadMessageModel)
            .where(and_(*filters))
            .order_by(ThreadMessageModel.message_sequence.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def get_timeline_anchors_by_ids(
        self, thread_id: str, message_ids: list[int]
    ) -> list[ThreadMessageModel]:
        if not message_ids:
            return []
        result = await self.db.execute(
            select(ThreadMessageModel)
            .where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.id.in_(message_ids),
                    ThreadMessageModel.type.in_(TIMELINE_ANCHOR_TYPES),
                )
            )
            .order_by(ThreadMessageModel.message_sequence.asc())
        )
        return list(result.scalars().all())

    async def get_for_thread(
        self, thread_id: str, message_id: int
    ) -> ThreadMessageModel | None:
        result = await self.db.execute(
            select(ThreadMessageModel).where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.id == message_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def find_tool_call(
        self, turn_execution_id: str, tool_call_key: str
    ) -> ThreadMessageModel | None:
        result = await self.db.execute(
            select(ThreadMessageModel).where(
                and_(
                    ThreadMessageModel.turn_execution_id == turn_execution_id,
                    ThreadMessageModel.type == "tool_call",
                    ThreadMessageModel.tool_call_key == tool_call_key,
                )
            )
        )
        return result.scalar_one_or_none()

    async def latest_user_message(self, thread_id: str) -> ThreadMessageModel | None:
        result = await self.db.execute(
            select(ThreadMessageModel)
            .where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.type == "user",
                )
            )
            .order_by(ThreadMessageModel.message_sequence.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_results_for_parent(
        self, thread_id: str, parent_message_id: int
    ) -> list[ThreadMessageModel]:
        result = await self.db.execute(
            select(ThreadMessageModel).where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.type == "tool_result",
                    ThreadMessageModel.parent_tool_use_id == parent_message_id,
                )
            )
        )
        return list(result.scalars().all())

    async def list_results_for_parents(
        self, thread_id: str, parent_message_ids: list[int]
    ) -> list[ThreadMessageModel]:
        if not parent_message_ids:
            return []
        result = await self.db.execute(
            select(ThreadMessageModel)
            .where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.type == "tool_result",
                    ThreadMessageModel.parent_tool_use_id.in_(parent_message_ids),
                )
            )
            .order_by(ThreadMessageModel.message_sequence.asc())
        )
        return list(result.scalars().all())

    async def has_user_message_after(
        self, thread_id: str, message_sequence: int
    ) -> bool:
        value = await self.db.scalar(
            select(func.count())
            .select_from(ThreadMessageModel)
            .where(
                and_(
                    ThreadMessageModel.thread_id == thread_id,
                    ThreadMessageModel.type == "user",
                    ThreadMessageModel.message_sequence > message_sequence,
                )
            )
        )
        return bool(value)

    async def save_tool_result_content(
        self,
        *,
        message_id: int,
        media_type: str,
        payload: bytes,
        line_count: int | None,
    ) -> ThreadToolResultContentModel:
        content = ThreadToolResultContentModel(
            message_id=message_id,
            media_type=media_type,
            payload=payload,
            byte_length=len(payload),
            line_count=line_count,
        )
        self.db.add(content)
        await self.db.flush()
        return content

    async def get_tool_result_content(
        self, message_id: int
    ) -> ThreadToolResultContentModel | None:
        return await self.db.get(ThreadToolResultContentModel, message_id)
