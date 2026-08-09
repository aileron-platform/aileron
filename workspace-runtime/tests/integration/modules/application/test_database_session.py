from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text

from app.database.session import dispose_async_engine, get_async_db

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _isolated_async_engine() -> AsyncGenerator[None, None]:
    # get_async_db() lazily caches its engine on the module, bound to whichever
    # event loop first creates it. Each test runs on its own event loop, so the
    # cache must be reset around every test or later tests see a dead loop.
    await dispose_async_engine()
    yield
    await dispose_async_engine()


@pytest.fixture
async def probe_table(postgres_engine) -> AsyncGenerator[None, None]:
    async with postgres_engine.begin() as connection:
        await connection.execute(text("DROP TABLE IF EXISTS session_probe"))
        await connection.execute(
            text("CREATE TABLE session_probe (id serial primary key, value text)")
        )
    yield
    async with postgres_engine.begin() as connection:
        await connection.execute(text("DROP TABLE IF EXISTS session_probe"))


async def test_get_async_db_session_survives_manual_commit_mid_request(
    probe_table: None, postgres_engine
) -> None:
    """Regression test: service code that commits mid-request (e.g. to make a
    write visible to a background task before the request finishes) must be
    able to keep using the same session afterwards, and any further writes
    must still land once the request completes.

    ThreadService.submit_thread() does exactly this: it commits the new
    turn/execution before starting the agent runner, then the caller
    (ThreadService.post_message) keeps reading from the same session to build
    the response. With get_async_db() wrapping the whole request in
    `async with session.begin():`, that manual commit closes the ambient
    transaction early and the following read raises
    sqlalchemy.exc.InvalidRequestError: Can't operate on closed transaction
    inside context manager.
    """
    gen = get_async_db()
    session = await anext(gen)

    await session.execute(text("INSERT INTO session_probe (value) VALUES ('first')"))
    await session.commit()

    # This must not raise. It reproduces ThreadService.post_message reading
    # `latest_turn` right after ThreadService.submit_thread() committed.
    result = await session.execute(text("SELECT value FROM session_probe"))
    assert result.scalar_one() == "first"

    await session.execute(text("INSERT INTO session_probe (value) VALUES ('second')"))

    # Simulate FastAPI closing the dependency generator after a clean response.
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    async with postgres_engine.connect() as verify_connection:
        rows = await verify_connection.execute(
            text("SELECT value FROM session_probe ORDER BY id")
        )
        assert [row[0] for row in rows] == ["first", "second"]


async def test_get_async_db_rolls_back_on_exception(
    probe_table: None, postgres_engine
) -> None:
    gen = get_async_db()
    session = await anext(gen)

    await session.execute(
        text("INSERT INTO session_probe (value) VALUES ('uncommitted')")
    )

    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("boom"))

    async with postgres_engine.connect() as verify_connection:
        rows = await verify_connection.execute(text("SELECT value FROM session_probe"))
        assert rows.all() == []
