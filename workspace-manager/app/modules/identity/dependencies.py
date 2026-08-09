"""FastAPI dependencies owned by the Identity module."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from .users import UserService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)
