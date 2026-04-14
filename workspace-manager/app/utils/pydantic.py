"""Pydantic 輔助工具"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict


def to_camel(string: str) -> str:
    """將字串轉換為 camelCase"""

    parts = string.split("_")
    if not parts:
        return string
    return parts[0] + "".join(word.capitalize() or "" for word in parts[1:])


class CamelModel(BaseModel):
    """使用 camelCase 輸出且支援 ORM 的模型基底"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

