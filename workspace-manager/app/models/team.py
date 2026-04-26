"""Team models"""

from typing import Optional

from pydantic import BaseModel, Field

from .common import TimestampMixin


class TeamBase(BaseModel):
    """Team basic fields"""

    name: str = Field(description="Team name")
    description: Optional[str] = Field(default=None, description="Team description")
    avatar_url: Optional[str] = Field(default=None, description="Team avatar")


class TeamCreate(TeamBase):
    """Create team request"""

    owner_id: str = Field(description="Owner user ID")


class TeamUpdate(BaseModel):
    """Update team request"""

    name: Optional[str] = Field(default=None, description="Team name")
    description: Optional[str] = Field(default=None, description="Team description")
    avatar_url: Optional[str] = Field(default=None, description="Team avatar")


class Team(TeamBase, TimestampMixin):
    """Team response model"""

    id: str = Field(description="Team ID")
    owner_id: str = Field(description="Owner user ID")
    member_count: int = Field(default=1, description="Team member count")


class TeamListResponse(BaseModel):
    """Team list response"""

    items: list[Team]
    total: int
