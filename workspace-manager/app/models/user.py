"""使用者模型"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from .common import TimestampMixin


class UserBase(BaseModel):
    """使用者基本欄位"""

    email: EmailStr = Field(description="電子郵件")
    username: str = Field(description="使用者名稱")
    first_name: Optional[str] = Field(default=None, description="名字")
    last_name: Optional[str] = Field(default=None, description="姓氏")
    display_name: Optional[str] = Field(default=None, description="顯示名稱")
    avatar_url: Optional[str] = Field(default=None, description="頭像 URL")
    is_active: bool = Field(default=True, description="是否啟用")


class UserCreate(UserBase):
    """建立使用者請求（僅用於系統初始化，實際用戶創建在 Keycloak 中完成）"""

    # 注意：密碼欄位已移除，因為認證已遷移到 Keycloak
    # 新用戶應通過 Keycloak 創建，而不是直接通過 API


class UserUpdate(BaseModel):
    """更新使用者請求"""

    first_name: Optional[str] = Field(default=None, description="名字")
    last_name: Optional[str] = Field(default=None, description="姓氏")
    display_name: Optional[str] = Field(default=None, description="顯示名稱")
    avatar_url: Optional[str] = Field(default=None, description="頭像 URL")
    is_active: Optional[bool] = Field(default=None, description="是否啟用")


class User(UserBase, TimestampMixin):
    """使用者回應模型"""

    id: str = Field(description="使用者 ID")


class UserListResponse(BaseModel):
    """使用者列表回應"""

    items: list[User]
    total: int
