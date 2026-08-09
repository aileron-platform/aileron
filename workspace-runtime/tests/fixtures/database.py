"""Database fixtures for testing

Provides PostgreSQL fixtures for Runtime-owned state integration tests.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
async def postgres_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create PostgreSQL async engine for integration tests

    Requires:
    - PostgreSQL running on localhost:5433
    - Database: test_workspace_runtime
    - User: test_user
    - Password: test_password

    Run with Docker:
        docker compose -f docker-compose.test.yml up -d postgres-test
    """
    engine = create_async_engine(
        "postgresql+asyncpg://test_user:test_password@postgres-test:5432/test_workspace_runtime",
        echo=False,
        poolclass=NullPool,  # Use NullPool for testing to avoid connection issues
        pool_pre_ping=True,
    )

    yield engine
    await engine.dispose()
