from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Base
from app.modules.thread.persistence_models import (
    ThreadMessageModel,
    ThreadModel,
    ThreadToolResultContentModel,
    ThreadTurnExecutionModel,
    ThreadTurnModel,
)
from app.modules.thread.capabilities_store import RuntimeCapabilitiesModel

THREAD_TEST_TABLES = [
    RuntimeCapabilitiesModel.__table__,
    ThreadModel.__table__,
    ThreadTurnModel.__table__,
    ThreadTurnExecutionModel.__table__,
    ThreadMessageModel.__table__,
    ThreadToolResultContentModel.__table__,
]


async def reset_thread_tables(connection) -> None:
    await connection.execute(
        text(
            "DROP TABLE IF EXISTS thread_tool_result_contents, thread_messages, "
            "thread_turn_executions, thread_turns, threads, runtime_capabilities CASCADE"
        )
    )
    await connection.run_sync(
        Base.metadata.create_all,
        tables=THREAD_TEST_TABLES,
        checkfirst=False,
    )


async def drop_thread_tables(connection) -> None:
    await connection.execute(
        text(
            "DROP TABLE IF EXISTS thread_tool_result_contents, thread_messages, "
            "thread_turn_executions, thread_turns, threads, runtime_capabilities CASCADE"
        )
    )


async def list_thread_messages(
    session: AsyncSession,
    thread_id: str,
) -> list[ThreadMessageModel]:
    result = await session.execute(
        select(ThreadMessageModel)
        .where(ThreadMessageModel.thread_id == thread_id)
        .order_by(ThreadMessageModel.message_sequence.asc())
    )
    return list(result.scalars().all())
