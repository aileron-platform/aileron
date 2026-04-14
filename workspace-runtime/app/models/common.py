"""共用模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.datetime_utils import utcnow


class APIResponse(BaseModel):
    """標準 API 回應格式"""

    status: str = Field(default="success", description="狀態")
    message: Optional[str] = Field(default=None, description="訊息")


class TimestampMixin(BaseModel):
    """包含時間戳記欄位"""

    created_at: datetime = Field(default_factory=utcnow, description="建立時間")
    updated_at: datetime = Field(default_factory=utcnow, description="更新時間")

    class Config:
        orm_mode = True
