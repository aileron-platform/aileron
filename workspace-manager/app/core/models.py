"""Common models"""

from datetime import datetime
from pydantic import BaseModel, Field


class TimestampMixin(BaseModel):
    """Model with created and updated timestamp fields"""

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Update time"
    )

    model_config = {"from_attributes": True}
