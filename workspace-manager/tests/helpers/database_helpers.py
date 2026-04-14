"""資料庫測試輔助工具"""

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
    """資料庫測試輔助工具"""

    def __init__(self):
        self.postgres_container = None
        self.engine = None
        self.session_factory = None

    def create_test_database(self) -> PostgresContainer:
        """創建測試資料庫容器"""
        self.postgres_container = PostgresContainer("postgres:15-alpine")
        self.postgres_container.start()
        return self.postgres_container

    def create_engine(self, database_url: str) -> sa.Engine:
        """創建資料庫引擎"""
        self.engine = create_engine(database_url)
        return self.engine

    def create_session_factory(self, engine: sa.Engine) -> sessionmaker:
        """創建會話工廠"""
        self.session_factory = sessionmaker(bind=engine)
        return self.session_factory

    def create_tables(self, engine: sa.Engine, metadata: Any) -> None:
        """創建資料表"""
        metadata.create_all(bind=engine)

    def drop_tables(self, engine: sa.Engine, metadata: Any) -> None:
        """刪除資料表"""
        metadata.drop_all(bind=engine)

    def cleanup(self) -> None:
        """清理資源"""
        if self.engine:
            self.engine.dispose()
        if self.postgres_container:
            self.postgres_container.stop()

    @staticmethod
    def seed_test_data(session: Session) -> None:
        """播種測試資料"""
        # 這裡可以根據實際的模型來添加測試資料
        pass

    @staticmethod
    def clear_test_data(session: Session) -> None:
        """清理測試資料"""
        # 清理所有表格的資料
        session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE;"))
        session.execute(text("TRUNCATE TABLE teams RESTART IDENTITY CASCADE;"))
        session.execute(text("TRUNCATE TABLE workspaces RESTART IDENTITY CASCADE;"))
        session.execute(text("TRUNCATE TABLE templates RESTART IDENTITY CASCADE;"))
        session.commit()


@pytest.fixture(scope="session")
def test_database():
    """測試資料庫 fixture (session 範圍)"""
    helper = DatabaseTestHelper()

    try:
        # 啟動 PostgreSQL 容器
        container = helper.create_test_database()
        database_url = container.get_connection_url()

        # 創建引擎和會話工廠
        engine = helper.create_engine(database_url)
        session_factory = helper.create_session_factory(engine)

        yield {
            "container": container,
            "engine": engine,
            "session_factory": session_factory,
            "database_url": database_url,
        }

    finally:
        # 清理資源
        helper.cleanup()


@pytest.fixture
def db_session(test_database: Dict[str, Any]) -> Generator[Session, None, None]:
    """資料庫會話 fixture"""
    session_factory = test_database["session_factory"]
    session = session_factory()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_engine(test_database: Dict[str, Any]):
    """資料庫引擎 fixture"""
    return test_database["engine"]


@pytest.fixture
def database_url(test_database: Dict[str, Any]):
    """資料庫 URL fixture"""
    return test_database["database_url"]


@pytest.fixture(autouse=True)
def cleanup_db_data(db_session: Session):
    """自動清理資料庫資料"""
    yield
    DatabaseTestHelper.clear_test_data(db_session)


class MockDatabaseRecord:
    """Mock 資料庫記錄"""

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
        """轉換為字典"""
        result = {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        result.update(self.data)
        return result


def assert_record_exists(session: Session, table_name: str, **filters) -> None:
    """斷言記錄存在"""
    query = text(f"SELECT 1 FROM {table_name} WHERE ")
    conditions = []
    params = {}

    for i, (key, value) in enumerate(filters.items()):
        if i > 0:
            query += " AND "
        query += f"{key} = :{key}"
        params[key] = value

    result = session.execute(query, params).fetchone()
    assert result is not None, f"記錄不存在: {table_name} with filters {filters}"


def assert_record_count(
    session: Session, table_name: str, expected_count: int, **filters
) -> None:
    """斷言記錄數量"""
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
    assert result == expected_count, f"記錄數量不匹配: 期望 {expected_count}, 實際 {result}"


def assert_table_has_columns(
    session: Session, table_name: str, expected_columns: list[str]
) -> None:
    """斷言表格包含指定欄位"""
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
    """)
    result = session.execute(query, {"table_name": table_name}).fetchall()
    actual_columns = [row[0] for row in result]

    for column in expected_columns:
        assert column in actual_columns, f"表格 {table_name} 缺少欄位: {column}"


def assert_foreign_key_exists(
    session: Session,
    table_name: str,
    column_name: str,
    referenced_table: str,
    referenced_column: str,
) -> None:
    """斷言外鍵約束存在"""
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

    assert result > 0, f"外鍵約束不存在: {table_name}.{column_name} -> {referenced_table}.{referenced_column}"


# 測試資料生成器
class TestDataGenerator:
    """測試資料生成器"""

    @staticmethod
    def generate_user_data(count: int = 1) -> list[Dict[str, Any]]:
        """生成用戶測試資料"""
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
        """生成團隊測試資料"""
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
        """生成工作區測試資料"""
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
    """測試資料生成器 fixture"""
    return TestDataGenerator()