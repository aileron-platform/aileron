"""Authentication related models"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request"""

    email: EmailStr = Field(description="User email")
    password: str = Field(min_length=6, description="Login password")


class RefreshRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(min_length=10, description="Refresh token")


class TokenResponse(BaseModel):
    """Token information returned on successful login"""

    access_token: str = Field(description="Access token")
    refresh_token: str = Field(description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(default=1800, description="Access token validity time (seconds)")


class AuthStatus(BaseModel):
    """Authentication status response"""

    authenticated: bool = Field(description="Whether authenticated")
    user_id: Optional[str] = Field(default=None, description="User ID")
    email: Optional[EmailStr] = Field(default=None, description="User email")
