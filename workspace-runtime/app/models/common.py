"""Common models"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.datetime_utils import utcnow


class APIResponse(BaseModel):
    """Standard API response format"""

    status: str = Field(default="success", description="Status")
    message: Optional[str] = Field(default=None, description="Message")


class TimestampMixin(BaseModel):
    """Mixin containing timestamp fields"""

    created_at: datetime = Field(default_factory=utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=utcnow, description="Update time")

    class Config:
        orm_mode = True
