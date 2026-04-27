"""Base Repository class.

Provides common CRUD methods and short ID resolution logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(ABC, Generic[T]):
    """Base Repository class.

    Provides common CRUD operations and short ID resolution.
    """

    def __init__(self, db: AsyncSession, model_class: Type[T], id_column: str = "id"):
        """Initialize Repository.

        Args:
            db: Database session
            model_class: ORM model class
            id_column: Primary key column name
        """
        self.db = db
        self.model_class = model_class
        self.id_column = id_column

    @abstractmethod
    def _get_id_column(self) -> Any:
        """Get primary key column.

        Returns:
            Column object of the primary key field
        """
        pass

    async def find_by_id(self, id: str) -> Optional[T]:
        """Query by ID.

        Supports short ID resolution (prefix matching).

        Args:
            id: Full ID or short ID

        Returns:
            Found record or None
        """
        id_col = self._get_id_column()

        # Try exact match first
        stmt = select(self.model_class).where(id_col == id)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return row

        # Short ID resolution (prefix matching)
        if len(id) < 36:
            stmt = select(self.model_class).where(id_col.startswith(id))
            result = await self.db.execute(stmt)
            rows = result.scalars().all()

            if len(rows) == 1:
                return rows[0]
            elif len(rows) > 1:
                raise ValueError(f"Ambiguous short ID: {id} matches {len(rows)} records")

        return None

    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: Optional[str] = None,
        order_desc: bool = True,
    ) -> List[T]:
        """Query all records.

        Args:
            filters: Filter conditions
            limit: Maximum number of records
            offset: Offset
            order_by: Sort column
            order_desc: Whether to sort in descending order

        Returns:
            List of records
        """
        stmt = select(self.model_class)

        # Apply filter conditions
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    column = getattr(self.model_class, key)
                    if value is None:
                        stmt = stmt.where(column.is_(None))
                    else:
                        stmt = stmt.where(column == value)

        # Sorting
        if order_by and hasattr(self.model_class, order_by):
            column = getattr(self.model_class, order_by)
            if order_desc:
                stmt = stmt.order_by(column.desc())
            else:
                stmt = stmt.order_by(column.asc())

        # Pagination
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> T:
        """Create record.

        Args:
            data: Record data

        Returns:
            Created record
        """
        instance = self.model_class(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: str, data: Dict[str, Any]) -> Optional[T]:
        """Update record.

        Args:
            id: Record ID
            data: Update data

        Returns:
            Updated record or None
        """
        # Query first to ensure it exists
        existing = await self.find_by_id(id)
        if not existing:
            return None

        # Get actual ID (might be full ID after short ID resolution)
        actual_id = getattr(existing, self.id_column)

        # Update
        id_col = self._get_id_column()
        stmt = update(self.model_class).where(id_col == actual_id).values(**data)
        await self.db.execute(stmt)
        await self.db.flush()

        # Re-query
        return await self.find_by_id(actual_id)

    async def delete(self, id: str) -> bool:
        """Delete record.

        Args:
            id: Record ID

        Returns:
            Whether deletion was successful
        """
        # Query first to ensure it exists
        existing = await self.find_by_id(id)
        if not existing:
            return False

        # Get actual ID
        actual_id = getattr(existing, self.id_column)

        # Delete
        id_col = self._get_id_column()
        stmt = delete(self.model_class).where(id_col == actual_id)
        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.rowcount > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records.

        Args:
            filters: Filter conditions

        Returns:
            Number of records
        """
        from sqlalchemy import func as sql_func

        stmt = select(sql_func.count()).select_from(self.model_class)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    column = getattr(self.model_class, key)
                    if value is None:
                        stmt = stmt.where(column.is_(None))
                    else:
                        stmt = stmt.where(column == value)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def exists(self, id: str) -> bool:
        """Check if record exists.

        Args:
            id: Record ID

        Returns:
            Whether the record exists
        """
        record = await self.find_by_id(id)
        return record is not None


__all__ = ["BaseRepository"]
