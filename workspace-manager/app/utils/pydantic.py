"""Pydantic utility functions"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict


def to_camel(string: str) -> str:
    """Convert string to camelCase"""

    parts = string.split("_")
    if not parts:
        return string
    return parts[0] + "".join(word.capitalize() or "" for word in parts[1:])


class CamelModel(BaseModel):
    """Base model with camelCase output and ORM support"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

