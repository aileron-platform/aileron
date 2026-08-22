from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import text

from aileron_runtime_database_connection import (
    AsyncpgRuntimeConnectionAdapter,
    CallbackRuntimeConnectionSource,
    RuntimeDatabaseConnections,
)


def test_asyncpg_adapter_opens_the_canonical_wire_against_postgres() -> None:
    database_connection = os.environ.get("TEST_RUNTIME_DATABASE_CONNECTION")
    if database_connection is None:
        pytest.skip("TEST_RUNTIME_DATABASE_CONNECTION is not configured")

    engine = RuntimeDatabaseConnections().open(
        source=CallbackRuntimeConnectionSource(lambda: database_connection),
        adapter=AsyncpgRuntimeConnectionAdapter(),
    )

    async def probe() -> None:
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text("SELECT current_setting('server_version_num')::integer")
                )
                assert result.scalar_one() >= 150000
        finally:
            await engine.dispose()

    asyncio.run(probe())
