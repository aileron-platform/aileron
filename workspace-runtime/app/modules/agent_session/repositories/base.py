"""Repository 基礎類別.

提供通用的 CRUD 方法和短 ID 解析邏輯。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(ABC, Generic[T]):
    """Repository 基礎類別.

    提供通用的 CRUD 操作和短 ID 解析。
    """

    def __init__(self, db: AsyncSession, model_class: Type[T], id_column: str = "id"):
        """初始化 Repository.

        Args:
            db: 資料庫 session
            model_class: ORM 模型類別
            id_column: 主鍵欄位名稱
        """
        self.db = db
        self.model_class = model_class
        self.id_column = id_column

    @abstractmethod
    def _get_id_column(self) -> Any:
        """取得主鍵欄位.

        Returns:
            主鍵欄位的 Column 對象
        """
        pass

    async def find_by_id(self, id: str) -> Optional[T]:
        """依 ID 查詢.

        支援短 ID 解析 (前綴匹配)。

        Args:
            id: 完整 ID 或短 ID

        Returns:
            找到的記錄或 None
        """
        id_col = self._get_id_column()

        # 先嘗試完全匹配
        stmt = select(self.model_class).where(id_col == id)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return row

        # 短 ID 解析 (前綴匹配)
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
        """查詢所有記錄.

        Args:
            filters: 過濾條件
            limit: 最大筆數
            offset: 偏移量
            order_by: 排序欄位
            order_desc: 是否降序

        Returns:
            記錄列表
        """
        stmt = select(self.model_class)

        # 套用過濾條件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    column = getattr(self.model_class, key)
                    if value is None:
                        stmt = stmt.where(column.is_(None))
                    else:
                        stmt = stmt.where(column == value)

        # 排序
        if order_by and hasattr(self.model_class, order_by):
            column = getattr(self.model_class, order_by)
            if order_desc:
                stmt = stmt.order_by(column.desc())
            else:
                stmt = stmt.order_by(column.asc())

        # 分頁
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> T:
        """建立記錄.

        Args:
            data: 記錄資料

        Returns:
            建立的記錄
        """
        instance = self.model_class(**data)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: str, data: Dict[str, Any]) -> Optional[T]:
        """更新記錄.

        Args:
            id: 記錄 ID
            data: 更新資料

        Returns:
            更新後的記錄或 None
        """
        # 先查詢確保存在
        existing = await self.find_by_id(id)
        if not existing:
            return None

        # 取得實際 ID (可能是短 ID 解析後的完整 ID)
        actual_id = getattr(existing, self.id_column)

        # 更新
        id_col = self._get_id_column()
        stmt = update(self.model_class).where(id_col == actual_id).values(**data)
        await self.db.execute(stmt)
        await self.db.flush()

        # 重新查詢
        return await self.find_by_id(actual_id)

    async def delete(self, id: str) -> bool:
        """刪除記錄.

        Args:
            id: 記錄 ID

        Returns:
            是否成功刪除
        """
        # 先查詢確保存在
        existing = await self.find_by_id(id)
        if not existing:
            return False

        # 取得實際 ID
        actual_id = getattr(existing, self.id_column)

        # 刪除
        id_col = self._get_id_column()
        stmt = delete(self.model_class).where(id_col == actual_id)
        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.rowcount > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """計算記錄數量.

        Args:
            filters: 過濾條件

        Returns:
            記錄數量
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
        """檢查記錄是否存在.

        Args:
            id: 記錄 ID

        Returns:
            是否存在
        """
        record = await self.find_by_id(id)
        return record is not None


__all__ = ["BaseRepository"]
