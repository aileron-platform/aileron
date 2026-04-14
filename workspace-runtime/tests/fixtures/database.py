"""Database fixtures for testing

Provides SQLite (for unit tests) and PostgreSQL (for integration tests) fixtures.
"""

import pytest
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, NullPool

# Import your models base
# from app.database.models import Base


@pytest.fixture(scope="function")
def sqlite_engine():
    """Create SQLite in-memory database engine for unit tests

    Features:
    - Fast (in-memory)
    - Isolated per test
    - Automatic cleanup
    - Foreign key constraints enabled
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True for SQL debugging
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    # Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    # Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    """Create database session with automatic rollback

    Usage:
        def test_something(db_session):
            # All database operations are automatically rolled back
            user = User(name="test")
            db_session.add(user)
            db_session.commit()
    """
    connection = sqlite_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# PostgreSQL fixtures for integration tests

@pytest.fixture(scope="session")
async def postgres_engine():
    """Create PostgreSQL async engine for integration tests

    Requires:
    - PostgreSQL running on localhost:5433
    - Database: test_workspace_runtime
    - User: test_user
    - Password: test_password

    Run with Docker:
        docker-compose -f docker-compose.test.yml up -d postgres-test
    """
    engine = create_async_engine(
        "postgresql+asyncpg://test_user:test_password@postgres-test:5432/test_workspace_runtime",
        echo=False,
        poolclass=NullPool,  # Use NullPool for testing to avoid connection issues
        pool_pre_ping=True,
    )

    # Create all tables
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(postgres_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for integration tests

    Usage:
        @pytest.mark.asyncio
        async def test_something(async_db_session):
            user = User(name="test")
            async_db_session.add(user)
            await async_db_session.commit()
    """
    async_session = async_sessionmaker(
        postgres_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


# Repository fixtures

@pytest.fixture
def session_repository(db_session):
    """Create SessionRepository with test database

    Usage:
        def test_create_session(session_repository):
            session = Session(...)
            await session_repository.save(session)
    """
    pytest.skip("舊版同步 SessionRepository 測試夾具已不再適用目前 async repository 架構")


@pytest.fixture
def message_repository(db_session):
    """Create MessageRepository with test database"""
    pytest.skip("舊版同步 MessageRepository 測試夾具已不再適用目前 async repository 架構")


# Integration test repositories (async)

@pytest.fixture
async def async_session_repository(async_db_session):
    """Create async SessionRepository for integration tests"""
    from app.modules.agent_session.repositories.agent_session_repository import (
        AgentSessionRepository,
    )

    return AgentSessionRepository(db=async_db_session)


@pytest.fixture
async def async_message_repository(async_db_session):
    """Create async MessageRepository for integration tests"""
    from app.modules.agent_session.repositories.message_repository import MessageRepository

    return MessageRepository(db=async_db_session)
