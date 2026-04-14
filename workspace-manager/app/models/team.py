"""團隊模型"""

from typing import Optional

from pydantic import BaseModel, Field

from .common import TimestampMixin


class TeamBase(BaseModel):
    """團隊基本欄位"""

    name: str = Field(description="團隊名稱")
    description: Optional[str] = Field(default=None, description="團隊描述")
    avatar_url: Optional[str] = Field(default=None, description="團隊頭像")


class TeamCreate(TeamBase):
    """建立團隊請求"""

    owner_id: str = Field(description="擁有者使用者 ID")


class TeamUpdate(BaseModel):
    """更新團隊請求"""

    name: Optional[str] = Field(default=None, description="團隊名稱")
    description: Optional[str] = Field(default=None, description="團隊描述")
    avatar_url: Optional[str] = Field(default=None, description="團隊頭像")


class Team(TeamBase, TimestampMixin):
    """團隊回應模型"""

    id: str = Field(description="團隊 ID")
    owner_id: str = Field(description="擁有者使用者 ID")
    member_count: int = Field(default=1, description="團隊成員數量")


class TeamListResponse(BaseModel):
    """團隊列表回應"""

    items: list[Team]
    total: int
