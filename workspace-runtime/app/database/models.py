"""Workspace Runtime-owned database model base."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for tables owned by Workspace Runtime."""

    pass


__all__ = [
    "Base",
]
