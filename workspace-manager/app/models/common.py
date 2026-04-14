"""共用模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """標準 API 回應格式"""

    status: str = Field(default="success", description="回應狀態")
    message: Optional[str] = Field(default=None, description="提示訊息")


class TimestampMixin(BaseModel):
    """帶有建立與更新時間欄位的模型"""

    created_at: datetime = Field(default_factory=datetime.utcnow, description="建立時間")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新時間")

    model_config = {"from_attributes": True}
