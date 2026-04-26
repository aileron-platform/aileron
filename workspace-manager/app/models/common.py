"""Common models"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard API response format"""

    status: str = Field(default="success", description="Response status")
    message: Optional[str] = Field(default=None, description="Message")


class TimestampMixin(BaseModel):
    """Model with created and updated timestamp fields"""

    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update time")

    model_config = {"from_attributes": True}
