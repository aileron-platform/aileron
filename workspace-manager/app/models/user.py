"""User models"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .common import TimestampMixin


class UserBase(BaseModel):
    """User basic fields"""

    email: EmailStr = Field(description="Email address")
    username: str = Field(description="Username")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    display_name: Optional[str] = Field(default=None, description="Display name")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    is_active: bool = Field(default=True, description="Is active")


class UserCreate(UserBase):
    """Create user request (for system initialization only, actual user creation is done in Keycloak)"""


class UserUpdate(BaseModel):
    """Update user request"""

    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    display_name: Optional[str] = Field(default=None, description="Display name")
    avatar_url: Optional[str] = Field(default=None, description="Avatar URL")
    is_active: Optional[bool] = Field(default=None, description="Is active")


class User(UserBase, TimestampMixin):
    """User response model"""

    id: str = Field(description="User ID")


class UserListResponse(BaseModel):
    """User list response"""

    items: list[User]
    total: int
