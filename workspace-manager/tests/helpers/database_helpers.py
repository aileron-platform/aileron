"""Database Testing Helper Functions"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer


class DatabaseTestHelper:
    """Database Testing Helper Functions"""

    def __init__(self):
        self.postgres_container = None
        self.engine = None
        self.session_factory = None

    def create_test_database(self) -> PostgresContainer:
        """Create test database container"""
        self.postgres_container = PostgresContainer("postgres:15-alpine")
        self.postgres_container.start()
        return self.postgres_container

    def create_engine(self, database_url: str) -> sa.Engine:
        """Create database engine"""
        self.engine = create_engine(database_url)
        return self.engine

    def create_session_factory(self, engine: sa.Engine) -> sessionmaker:
        """Create session factory"""
        self.session_factory = sessionmaker(bind=engine)
        return self.session_factory

    def create_tables(self, engine: sa.Engine, metadata: Any) -> None:
        """Create database tables"""
        metadata.create_all(bind=engine)

    def drop_tables(self, engine: sa.Engine, metadata: Any) -> None:
        """Drop database tables"""
        metadata.drop_all(bind=engine)

    def cleanup(self) -> None:
        """Clean up resources"""
        if self.engine:
            self.engine.dispose()
        if self.postgres_container:
            self.postgres_container.stop()

    @staticmethod
    def seed_test_data(session: Session) -> None:
        """Seed test data"""
        # Test data can be added here based on actual models
        pass

    @staticmethod
    def clear_test_data(session: Session) -> None:
        """Clear test data"""
        # Clear data from all tables
        session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE;"))
        session.execute(text("TRUNCATE TABLE teams RESTART IDENTITY CASCADE;"))
        session.execute(text("TRUNCATE TABLE workspaces RESTART IDENTITY CASCADE;"))
        session.commit()


@pytest.fixture(scope="session")
def test_database():
    """Test database fixture (session scope)"""
    helper = DatabaseTestHelper()

    try:
        # Start PostgreSQL container
        container = helper.create_test_database()
        database_url = container.get_connection_url()

        # Create engine and session factory
        engine = helper.create_engine(database_url)
        session_factory = helper.create_session_factory(engine)

        yield {
            "container": container,
            "engine": engine,
            "session_factory": session_factory,
            "database_url": database_url,
        }

    finally:
        # Clean up resources
        helper.cleanup()


@pytest.fixture
def db_session(test_database: Dict[str, Any]) -> Generator[Session, None, None]:
    """Database session fixture"""
    session_factory = test_database["session_factory"]
    session = session_factory()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_engine(test_database: Dict[str, Any]):
    """Database engine fixture"""
    return test_database["engine"]


@pytest.fixture
def database_url(test_database: Dict[str, Any]):
    """Database URL fixture"""
    return test_database["database_url"]


@pytest.fixture(autouse=True)
def cleanup_db_data(db_session: Session):
    """Automatically clean up database data"""
    yield
    DatabaseTestHelper.clear_test_data(db_session)


class MockDatabaseRecord:
    """Mock database record"""

    def __init__(
        self,
        table_name: str,
        data: Dict[str, Any] | None = None,
        id: uuid.UUID | None = None,
    ):
        self.table_name = table_name
        self.id = id or uuid.uuid4()
        self.data = data or {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        result.update(self.data)
        return result


def assert_record_exists(session: Session, table_name: str, **filters) -> None:
    """Assert record exists"""
    query = text(f"SELECT 1 FROM {table_name} WHERE ")
    conditions = []
    params = {}

    for i, (key, value) in enumerate(filters.items()):
        if i > 0:
            query += " AND "
        query += f"{key} = :{key}"
        params[key] = value

    result = session.execute(query, params).fetchone()
    assert result is not None, f"Record does not exist: {table_name} with filters {filters}"


def assert_record_count(
    session: Session, table_name: str, expected_count: int, **filters
) -> None:
    """Assert record count"""
    query = text(f"SELECT COUNT(*) FROM {table_name}")
    params = {}

    if filters:
        query += " WHERE "
        for i, (key, value) in enumerate(filters.items()):
            if i > 0:
                query += " AND "
            query += f"{key} = :{key}"
            params[key] = value

    result = session.execute(query, params).scalar()
    assert result == expected_count, f"Record count mismatch: expected {expected_count}, actual {result}"


def assert_table_has_columns(
    session: Session, table_name: str, expected_columns: list[str]
) -> None:
    """Assert table has specified columns"""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
    """)
    result = session.execute(query, {"table_name": table_name}).fetchall()
    actual_columns = [row[0] for row in result]

    for column in expected_columns:
        assert column in actual_columns, f"Table {table_name} missing column: {column}"


def assert_foreign_key_exists(
    session: Session,
    table_name: str,
    column_name: str,
    referenced_table: str,
    referenced_column: str,
) -> None:
    """Assert foreign key constraint exists"""
    query = text("""
        SELECT COUNT(*)
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = :table_name
            AND kcu.column_name = :column_name
            AND kcu.referenced_table_name = :referenced_table
            AND kcu.referenced_column_name = :referenced_column
    """)

    result = session.execute(query, {
        "table_name": table_name,
        "column_name": column_name,
        "referenced_table": referenced_table,
        "referenced_column": referenced_column,
    }).scalar()

    assert result > 0, f"Foreign key constraint does not exist: {table_name}.{column_name} -> {referenced_table}.{referenced_column}"


# Test Data Generator
class TestDataGenerator:
    """Test data generator"""

    @staticmethod
    def generate_user_data(count: int = 1) -> list[Dict[str, Any]]:
        """Generate user test data"""
        users = []
        for i in range(count):
            users.append({
                "username": f"testuser{i}",
                "email": f"testuser{i}@example.com",
                "full_name": f"Test User {i}",
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
        return users

    @staticmethod
    def generate_team_data(count: int = 1, owner_id: uuid.UUID | None = None) -> list[Dict[str, Any]]:
        """Generate team test data"""
        teams = []
        for i in range(count):
            teams.append({
                "name": f"Test Team {i}",
                "description": f"Test team description {i}",
                "owner_id": owner_id or uuid.uuid4(),
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
        return teams

    @staticmethod
    def generate_workspace_data(count: int = 1, owner_id: uuid.UUID | None = None) -> list[Dict[str, Any]]:
        """Generate workspace test data"""
        workspaces = []
        for i in range(count):
            workspaces.append({
                "name": f"Test Workspace {i}",
                "description": f"Test workspace description {i}",
                "owner_id": owner_id or uuid.uuid4(),
                "status": "stopped",
                "config": {
                    "cpu_limit": "2",
                    "memory_limit": "4Gi",
                    "storage_limit": "10Gi",
                },
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
        return workspaces


@pytest.fixture
def test_data_generator():
    """Test data generator fixture"""
    return TestDataGenerator()
