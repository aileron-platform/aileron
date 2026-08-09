"""Durable Runtime-owned telemetry outbox."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import DateTime, Integer, JSON, String, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base

from .models import TelemetryBatch


class TelemetryOutbox(Protocol):
    async def enqueue(self, batch: TelemetryBatch) -> None: ...

    async def pending(self, *, limit: int) -> Sequence[TelemetryBatch]: ...

    async def mark_sent(self, batch_id: str) -> None: ...

    async def mark_failed(self, batch_id: str) -> None: ...


class ResourceTelemetryOutboxModel(Base):
    __tablename__ = "resource_telemetry_outbox"

    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SqlAlchemyTelemetryOutbox:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def enqueue(self, batch: TelemetryBatch) -> None:
        async with self._sessions.begin() as session:
            session.add(
                ResourceTelemetryOutboxModel(
                    batch_id=batch.batch_id,
                    payload=batch.to_wire(),
                )
            )

    async def pending(self, *, limit: int) -> tuple[TelemetryBatch, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ResourceTelemetryOutboxModel)
                    .order_by(ResourceTelemetryOutboxModel.created_at)
                    .limit(limit)
                )
            ).all()
        return tuple(TelemetryBatch.from_wire(row.payload) for row in rows)

    async def mark_sent(self, batch_id: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                delete(ResourceTelemetryOutboxModel).where(
                    ResourceTelemetryOutboxModel.batch_id == batch_id
                )
            )

    async def mark_failed(self, batch_id: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(ResourceTelemetryOutboxModel)
                .where(ResourceTelemetryOutboxModel.batch_id == batch_id)
                .values(
                    attempts=ResourceTelemetryOutboxModel.attempts + 1,
                    last_attempt_at=datetime.now(timezone.utc),
                )
            )


__all__ = [
    "ResourceTelemetryOutboxModel",
    "SqlAlchemyTelemetryOutbox",
    "TelemetryOutbox",
]
