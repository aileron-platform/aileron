"""FastAPI dependencies owned by the Settings module."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from .user_settings import SettingsService


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(db)
