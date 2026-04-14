"""認證相關模型"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """登入請求"""

    email: EmailStr = Field(description="使用者電子郵件")
    password: str = Field(min_length=6, description="登入密碼")


class RefreshRequest(BaseModel):
    """刷新權杖請求"""

    refresh_token: str = Field(min_length=10, description="刷新權杖")


class TokenResponse(BaseModel):
    """登入成功回傳的權杖資訊"""

    access_token: str = Field(description="存取權杖")
    refresh_token: str = Field(description="刷新權杖")
    token_type: str = Field(default="bearer", description="權杖類型")
    expires_in: int = Field(default=1800, description="存取權杖有效時間 (秒)")


class AuthStatus(BaseModel):
    """認證狀態回應"""

    authenticated: bool = Field(description="是否通過認證")
    user_id: Optional[str] = Field(default=None, description="使用者 ID")
    email: Optional[EmailStr] = Field(default=None, description="使用者電子郵件")
