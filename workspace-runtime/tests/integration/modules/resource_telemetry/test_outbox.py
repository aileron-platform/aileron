from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.resource_telemetry.models import TelemetryBatch
from app.modules.resource_telemetry.outbox import (
    ResourceTelemetryOutboxModel,
    SqlAlchemyTelemetryOutbox,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outbox_survives_a_new_adapter_instance(postgres_engine) -> None:
    async with postgres_engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ResourceTelemetryOutboxModel.__table__.drop(
                sync_connection, checkfirst=True
            )
        )
        await connection.run_sync(
            lambda sync_connection: ResourceTelemetryOutboxModel.__table__.create(
                sync_connection, checkfirst=True
            )
        )
    sessions = async_sessionmaker(postgres_engine, expire_on_commit=False)
    first = SqlAlchemyTelemetryOutbox(sessions)
    batch = TelemetryBatch(
        batch_id="batch-after-restart",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        events=(),
        capacity_measurements=(),
    )
    await first.enqueue(batch)

    after_restart = SqlAlchemyTelemetryOutbox(sessions)
    pending = await after_restart.pending(limit=10)

    assert [item.batch_id for item in pending] == ["batch-after-restart"]
    await after_restart.mark_failed("batch-after-restart")
    assert [item.batch_id for item in await after_restart.pending(limit=10)] == [
        "batch-after-restart"
    ]
    await after_restart.mark_sent("batch-after-restart")
    assert await after_restart.pending(limit=10) == ()
