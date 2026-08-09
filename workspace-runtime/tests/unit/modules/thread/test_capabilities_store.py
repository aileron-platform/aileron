from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.internal.models import CapabilitiesSyncRequest
from app.modules.internal.router import sync_capabilities
from app.modules.thread.capabilities_store import (
    CapabilitiesStore,
    RuntimeCapabilitiesModel,
)


def make_capabilities(default_model: str = "claude-opus-4-8") -> dict:
    return {
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8", "claude-sonnet-5"],
                "default_model": default_model,
                "modes": ["execute", "plan"],
                "default_mode": "execute",
                "context_window": 200000,
            },
            {
                "id": "codex",
                "models": ["gpt-5.6-sol"],
                "default_model": "gpt-5.6-sol",
                "context_window": 200000,
            },
        ],
        "default_tool": "claude",
    }


@pytest.fixture
async def capability_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    async with postgres_engine.begin() as conn:
        await conn.run_sync(RuntimeCapabilitiesModel.__table__.drop, checkfirst=True)
        await conn.run_sync(RuntimeCapabilitiesModel.__table__.create)

    session_factory = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with postgres_engine.begin() as conn:
        await conn.run_sync(RuntimeCapabilitiesModel.__table__.drop, checkfirst=True)


@pytest.mark.asyncio
async def test_capabilities_store_round_trip(capability_session: AsyncSession) -> None:
    store = CapabilitiesStore()

    await store.put(capability_session, "workspace-a", make_capabilities())
    await capability_session.commit()

    snapshot = await store.get(capability_session, "workspace-a")

    assert snapshot is not None
    assert snapshot.default_tool == "claude"
    assert snapshot.tools[0].default_model == "claude-opus-4-8"


@pytest.mark.asyncio
async def test_capabilities_store_overwrites_existing_snapshot(
    capability_session: AsyncSession,
) -> None:
    store = CapabilitiesStore()

    await store.put(
        capability_session, "workspace-a", make_capabilities("claude-opus-4-8")
    )
    await store.put(
        capability_session, "workspace-a", make_capabilities("claude-sonnet-5")
    )
    await capability_session.commit()

    snapshot = await store.get(capability_session, "workspace-a")

    assert snapshot is not None
    assert snapshot.tools[0].default_model == "claude-sonnet-5"


@pytest.mark.asyncio
async def test_capabilities_store_returns_none_when_missing(
    capability_session: AsyncSession,
) -> None:
    assert (
        await CapabilitiesStore().get(capability_session, "missing-workspace") is None
    )


@pytest.mark.asyncio
async def test_internal_capabilities_endpoint_persists_snapshot(
    capability_session: AsyncSession,
) -> None:
    request = CapabilitiesSyncRequest(
        workspace_id="workspace-a",
        capabilities=make_capabilities(),
    )

    response = await sync_capabilities(request, capability_session)
    snapshot = await CapabilitiesStore().get(capability_session, "workspace-a")

    assert response.success is True
    assert snapshot is not None
    assert snapshot.default_tool == "claude"
