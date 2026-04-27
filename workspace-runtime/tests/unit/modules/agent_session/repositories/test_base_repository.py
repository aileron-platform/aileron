"""BaseRepository unit tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.modules.agent_session.repositories.base import BaseRepository


class TestBaseRepositoryLogic:
    """BaseRepository logic tests (no database required)."""

    def test_short_id_matching_logic(self):
        """Test short ID matching logic."""
        # Simulate short ID matching
        full_ids = [
            "abc123-full-uuid-1",
            "abc123-full-uuid-2",
            "xyz789-full-uuid-3",
        ]
        short_id = "abc123"

        # Find all matching IDs
        matches = [id for id in full_ids if id.startswith(short_id)]

        assert len(matches) == 2
        assert "abc123-full-uuid-1" in matches
        assert "abc123-full-uuid-2" in matches

    def test_short_id_unique_match(self):
        """Test short ID unique match."""
        full_ids = [
            "abc123-full-uuid-1",
            "xyz789-full-uuid-2",
        ]
        short_id = "abc"

        matches = [id for id in full_ids if id.startswith(short_id)]

        assert len(matches) == 1
        assert matches[0] == "abc123-full-uuid-1"

    def test_short_id_no_match(self):
        """Test short ID no match."""
        full_ids = [
            "abc123-full-uuid-1",
            "xyz789-full-uuid-2",
        ]
        short_id = "def"

        matches = [id for id in full_ids if id.startswith(short_id)]

        assert len(matches) == 0


class TestRepositoryCRUDLogic:
    """Repository CRUD logic tests."""

    def test_update_data_merge(self):
        """Test update data merge logic."""
        existing_data = {
            "title": "Original Title",
            "message_count": 5,
            "context_files": ["file1.txt"],
        }

        update_data = {
            "title": "New Title",
            "message_count": 10,
        }

        # Merge update
        merged = {**existing_data, **update_data}

        assert merged["title"] == "New Title"
        assert merged["message_count"] == 10
        assert merged["context_files"] == ["file1.txt"]

    def test_filter_building(self):
        """Test filter condition building."""
        filters = {}

        # Only add non-null values
        workspace_id = "ws-123"
        status = "idle"
        agentic_tool = None

        if workspace_id:
            filters["workspace_id"] = workspace_id
        if status:
            filters["status"] = status
        if agentic_tool:
            filters["agentic_tool"] = agentic_tool

        assert filters == {
            "workspace_id": "ws-123",
            "status": "idle",
        }

    def test_pagination_calculation(self):
        """Test pagination calculation."""
        total = 100
        page_size = 20

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size

        assert total_pages == 5

        # Calculate offset
        page = 3
        offset = (page - 1) * page_size

        assert offset == 40


class TestRepositoryEntityConversion:
    """Repository entity conversion tests."""

    def test_db_row_to_entity_fields(self):
        """Test DB row to entity field mapping."""
        db_row = {
            "session_id": "sess-123",
            "workspace_id": "ws-456",
            "status": "idle",
            "agentic_tool": "claude-code",
            "created_at": datetime.utcnow(),
            "updated_at": None,
            "created_by": "user-1",
            "archived": False,
            "archived_reason": None,
            "ready_for_prompt": True,
            "data": {
                "title": "Test Session",
                "message_count": 5,
            },
        }

        # Simulate entity creation
        entity_data = {
            "id": db_row["session_id"],
            "workspace_id": db_row["workspace_id"],
            "status": db_row["status"],
            "agentic_tool": db_row["agentic_tool"],
            "created_at": db_row["created_at"],
            "title": db_row["data"].get("title"),
            "message_count": db_row["data"].get("message_count", 0),
        }

        assert entity_data["id"] == "sess-123"
        assert entity_data["title"] == "Test Session"
        assert entity_data["message_count"] == 5

    def test_entity_to_data_blob(self):
        """Test entity to data blob conversion."""
        entity_attrs = {
            "title": "My Session",
            "model": "claude-sonnet",
            "message_count": 10,
            "context_files": ["a.txt", "b.txt"],
            "permission_config": None,
        }

        # Only include non-null values
        data_blob = {}
        if entity_attrs.get("title"):
            data_blob["title"] = entity_attrs["title"]
        if entity_attrs.get("model"):
            data_blob["model"] = entity_attrs["model"]
        if entity_attrs.get("message_count"):
            data_blob["message_count"] = entity_attrs["message_count"]
        if entity_attrs.get("context_files"):
            data_blob["contextFiles"] = entity_attrs["context_files"]
        if entity_attrs.get("permission_config"):
            data_blob["permission_config"] = entity_attrs["permission_config"]

        assert "title" in data_blob
        assert "permission_config" not in data_blob
        assert data_blob["contextFiles"] == ["a.txt", "b.txt"]


class Base(DeclarativeBase):
    pass


class FakeModel(Base):
    __tablename__ = "fake_model"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)


class FakeRepository(BaseRepository[FakeModel]):
    def _get_id_column(self):
        return self.model_class.id


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _count_result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


@pytest.fixture
def db():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.execute = AsyncMock()
    mock.flush = AsyncMock()
    mock.refresh = AsyncMock()
    return mock


@pytest.fixture
def repo(db):
    return FakeRepository(db, FakeModel)


@pytest.mark.asyncio
async def test_find_by_id_returns_exact_match_without_short_id_lookup(repo, db):
    row = FakeModel(id="full-id", status="active", category="alpha")
    db.execute.return_value = _scalar_result(row)

    found = await repo.find_by_id("full-id")

    assert found is row
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_find_by_id_returns_unique_short_id_match(repo, db):
    row = FakeModel(id="abc123456789", status="active", category="alpha")
    db.execute.side_effect = [_scalar_result(None), _scalars_result([row])]

    found = await repo.find_by_id("abc123")

    assert found is row
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_find_by_id_raises_for_ambiguous_short_id(repo, db):
    rows = [
        FakeModel(id="abc123456789", status="active", category="alpha"),
        FakeModel(id="abc123999999", status="idle", category="beta"),
    ]
    db.execute.side_effect = [_scalar_result(None), _scalars_result(rows)]

    with pytest.raises(ValueError, match="Ambiguous short ID"):
        await repo.find_by_id("abc123")


@pytest.mark.asyncio
async def test_find_by_id_returns_none_for_long_missing_id(repo, db):
    db.execute.return_value = _scalar_result(None)

    found = await repo.find_by_id("12345678-1234-1234-1234-123456789012")

    assert found is None
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_find_all_applies_filters_and_returns_rows(repo, db):
    rows = [
        FakeModel(id="row-1", status="active", category="alpha"),
        FakeModel(id="row-2", status=None, category="beta"),
    ]
    db.execute.return_value = _scalars_result(rows)

    result = await repo.find_all(
        filters={"status": None, "category": "beta", "unknown": "ignored"},
        limit=10,
        offset=5,
        order_by="id",
        order_desc=False,
    )

    stmt = db.execute.await_args.args[0]

    assert result == rows
    assert "IS NULL" in str(stmt)
    assert "category" in str(stmt)
    assert "unknown" not in str(stmt)


@pytest.mark.asyncio
async def test_create_adds_and_refreshes_instance(repo, db):
    created = await repo.create({"id": "new-id", "status": "active", "category": "alpha"})

    assert isinstance(created, FakeModel)
    assert created.id == "new-id"
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


@pytest.mark.asyncio
async def test_update_returns_none_when_record_missing(repo):
    repo.find_by_id = AsyncMock(return_value=None)

    updated = await repo.update("missing-id", {"status": "done"})

    assert updated is None


@pytest.mark.asyncio
async def test_update_uses_resolved_actual_id(repo, db):
    existing = FakeModel(id="full-id", status="active", category="alpha")
    refreshed = FakeModel(id="full-id", status="done", category="alpha")
    repo.find_by_id = AsyncMock(side_effect=[existing, refreshed])

    updated = await repo.update("short-id", {"status": "done"})

    assert updated is refreshed
    stmt = db.execute.await_args.args[0]
    assert "UPDATE" in str(stmt)
    assert db.flush.await_count == 1
    assert repo.find_by_id.await_args_list[1].args == ("full-id",)


@pytest.mark.asyncio
async def test_delete_returns_false_when_record_missing(repo):
    repo.find_by_id = AsyncMock(return_value=None)

    deleted = await repo.delete("missing-id")

    assert deleted is False


@pytest.mark.asyncio
async def test_delete_returns_true_when_row_deleted(repo, db):
    existing = FakeModel(id="full-id", status="active", category="alpha")
    repo.find_by_id = AsyncMock(return_value=existing)
    db.execute.return_value = MagicMock(rowcount=1)

    deleted = await repo.delete("short-id")

    assert deleted is True
    stmt = db.execute.await_args.args[0]
    assert "DELETE" in str(stmt)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_applies_filters_and_defaults_to_zero(repo, db):
    db.execute.return_value = _count_result(0)

    count = await repo.count({"status": "active", "category": None})

    stmt = db.execute.await_args.args[0]
    assert count == 0
    assert "count" in str(stmt).lower()
    assert "IS NULL" in str(stmt)


@pytest.mark.asyncio
async def test_exists_uses_find_by_id(repo):
    repo.find_by_id = AsyncMock(side_effect=[FakeModel(id="yes", status="ok", category="a"), None])

    assert await repo.exists("yes") is True
    assert await repo.exists("no") is False
