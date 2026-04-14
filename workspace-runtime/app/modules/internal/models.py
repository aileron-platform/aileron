"""Internal API 資料模型"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EnvironmentVariable(BaseModel):
    """環境變數模型"""
    key: str = Field(..., description="環境變數名稱")
    value: str = Field(..., description="環境變數值")


class SSHKeysRequest(BaseModel):
    """SSH Keys 設定請求"""
    private_key: str = Field(..., alias="privateKey", description="SSH 私鑰")
    public_key: str = Field(..., alias="publicKey", description="SSH 公鑰")

    class Config:
        populate_by_name = True


class OAuthAccountInfo(BaseModel):
    """OAuth 帳戶資訊"""
    account_uuid: Optional[str] = Field(None, alias="accountUuid")
    email_address: Optional[str] = Field(None, alias="emailAddress")
    organization_uuid: Optional[str] = Field(None, alias="organizationUuid")
    display_name: Optional[str] = Field(None, alias="displayName")
    organization_billing_type: Optional[str] = Field(None, alias="organizationBillingType")
    organization_role: Optional[str] = Field(None, alias="organizationRole")
    workspace_role: Optional[str] = Field(None, alias="workspaceRole")
    organization_name: Optional[str] = Field(None, alias="organizationName")

    class Config:
        populate_by_name = True


class ClaudeCodeRequest(BaseModel):
    """Claude Code 設定請求"""
    auth_method: Optional[str] = Field(
        None,
        alias="authMethod",
        description="認證方式 (subscription 或 api_key)"
    )
    subscription_access_token: Optional[str] = Field(
        None,
        alias="subscriptionAccessToken",
        description="Subscription OAuth Access Token"
    )
    subscription_refresh_token: Optional[str] = Field(
        None,
        alias="subscriptionRefreshToken",
        description="Subscription OAuth Refresh Token"
    )
    subscription_expires_at: Optional[int | str] = Field(
        None,
        alias="subscriptionExpiresAt",
        description="Token 過期時間（毫秒時間戳，舊版可能為 ISO8601 字串）",
    )
    oauth_account: Optional[OAuthAccountInfo] = Field(
        None,
        alias="oauthAccount",
        description="OAuth 帳戶資訊"
    )
    api_key: Optional[str] = Field(
        None,
        alias="apiKey",
        description="Claude API Key"
    )
    model: Optional[str] = Field(
        None,
        alias="model",
        description="統一的模型選擇（不論 subscription 或 apikey 都使用這個）"
    )
    environment_variables: List[EnvironmentVariable] = Field(
        default_factory=list,
        alias="environmentVariables",
        description="環境變數列表"
    )

    class Config:
        populate_by_name = True


class GitSettingsRequest(BaseModel):
    """Git 設定請求"""
    user_name: str = Field(..., alias="userName", description="Git 使用者名稱")
    user_email: str = Field(..., alias="userEmail", description="Git 使用者信箱")

    class Config:
        populate_by_name = True


class FirewallConfigRequest(BaseModel):
    """防火牆設定請求"""
    network_access_enabled: bool = Field(..., alias="networkAccessEnabled", description="網路存取權限開關")
    domain_access_mode: str = Field(..., alias="domainAccessMode", description="允許網域模式 (all/specific)")
    allowed_domains: List[str] = Field(default_factory=list, alias="allowedDomains", description="允許的網域列表")

    class Config:
        populate_by_name = True


class InternalApiResponse(BaseModel):
    """Internal API 統一回應格式"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="回應訊息")
    details: Optional[dict] = Field(None, description="詳細資訊")


class SetupCheckDetail(BaseModel):
    """初始化檢查項目的詳細狀態"""

    status: str = Field(..., description="項目狀態")
    message: str = Field(..., description="狀態描述")


class WorkspaceSetupStatusResponse(BaseModel):
    """Workspace 初始化狀態回應"""

    success: bool = Field(..., description="是否成功取得狀態")
    message: str = Field(..., description="回應訊息")
    checks: Dict[str, SetupCheckDetail] = Field(default_factory=dict, description="各檢查項目狀態")


__all__ = [
    "EnvironmentVariable",
    "SSHKeysRequest",
    "ClaudeCodeRequest",
    "GitSettingsRequest",
    "FirewallConfigRequest",
    "InternalApiResponse",
    "SetupCheckDetail",
    "WorkspaceSetupStatusResponse",
]
