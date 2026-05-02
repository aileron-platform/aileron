"""Pydantic models for Settings Module"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.utils.pydantic import CamelModel


class UserProfile(CamelModel):
    user_id: str = Field(..., alias="userId")
    username: str
    first_name: str = Field("", alias="firstName")
    last_name: str = Field("", alias="lastName")
    email: EmailStr
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")


class UserProfileUpdate(CamelModel):
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    avatar_url: Optional[str] = Field(None, alias="avatarUrl")


class NotificationSettings(CamelModel):
    desktop: bool = True
    email: bool = False
    updates: bool = True


class PerformanceSettings(CamelModel):
    auto_save: bool = Field(True, alias="autoSave")
    animations_enabled: bool = Field(True, alias="animationsEnabled")


class PrivacySettings(CamelModel):
    analytics: bool = False
    crash_reports: bool = Field(True, alias="crashReports")
    usage_data: bool = Field(False, alias="usageData")


class GeneralSettings(CamelModel):
    theme: str = "system"
    language: str = "en"
    timezone: str = "Asia/Taipei"
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    acp_cli_args: list[str] = Field(default_factory=list)


class SSHSettings(CamelModel):
    public_key: Optional[str] = Field(None, alias="publicKey")
    private_key: Optional[str] = Field(None, alias="privateKey")
    fingerprint: Optional[str] = None
    last_rotated_at: Optional[datetime] = Field(None, alias="lastRotatedAt")


class ClaudeModelInfo(CamelModel):
    model_key: str = Field(..., alias="modelKey")
    model_name: str = Field(..., alias="modelName")


class ClaudeProviderInfo(CamelModel):
    provider: str
    display_name: str = Field(..., alias="displayName")


class ClaudeCodeEnvironmentVariable(CamelModel):
    key: str
    value: str


class CodexEnvironmentVariable(CamelModel):
    key: str
    value: str


class OAuthAccountInfo(CamelModel):
    """OAuth account information"""
    account_uuid: Optional[str] = Field(None, alias="accountUuid")
    email_address: Optional[str] = Field(None, alias="emailAddress")
    organization_uuid: Optional[str] = Field(None, alias="organizationUuid")
    display_name: Optional[str] = Field(None, alias="displayName")
    organization_billing_type: Optional[str] = Field(None, alias="organizationBillingType")
    organization_role: Optional[str] = Field(None, alias="organizationRole")
    workspace_role: Optional[str] = Field(None, alias="workspaceRole")
    organization_name: Optional[str] = Field(None, alias="organizationName")


class ClaudeCodeSettings(CamelModel):
    # Authentication method: subscription or apikey
    auth_method: str = Field("subscription", alias="authMethod")

    # Subscription authentication related
    subscription_auth_code: Optional[str] = Field(None, alias="subscriptionAuthCode")
    subscription_access_token: Optional[str] = Field(None, alias="subscriptionAccessToken")
    subscription_refresh_token: Optional[str] = Field(None, alias="subscriptionRefreshToken")
    subscription_expires_at: Optional[int] = Field(None, alias="subscriptionExpiresAt", description="Expiration time (millisecond timestamp)")
    oauth_account: Optional[OAuthAccountInfo] = Field(None, alias="oauthAccount")

    # API key authentication related
    auth_key: Optional[str] = Field(None, alias="authKey")
    api_provider: Optional[str] = Field(None, alias="apiProvider")  # Anthropic, AWS Bedrock, Google Vertex AI, Other

    # Unified model selection field (used by both subscription and apikey)
    model: Optional[str] = Field(None, alias="model")

    # EnvironmentVariableSettings
    environment_variables: list[ClaudeCodeEnvironmentVariable] = Field(
        default_factory=list, alias="environmentVariables"
    )

    # Legacy settings for backward compatibility
    selected_provider: Optional[str] = Field(None, alias="selectedProvider")
    available_models: list[ClaudeModelInfo] = Field(default_factory=list, alias="availableModels")
    available_providers: list[ClaudeProviderInfo] = Field(
        default_factory=list, alias="availableProviders"
    )


class CodexAccountInfo(CamelModel):
    account_id: Optional[str] = Field(None, alias="accountId")
    email: Optional[str] = None
    plan_type: Optional[str] = Field(None, alias="planType")


class CodexAuthFlow(CamelModel):
    login_id: Optional[str] = Field(None, alias="loginId")
    auth_url: Optional[str] = Field(None, alias="authUrl")
    verification_url: Optional[str] = Field(None, alias="verificationUrl")
    user_code: Optional[str] = Field(None, alias="userCode")
    expires_at: Optional[int] = Field(None, alias="expiresAt")


class CodexSettings(CamelModel):
    auth_method: str = Field("subscription", alias="authMethod")
    login_status: str = Field("notConnected", alias="loginStatus")
    account: Optional[CodexAccountInfo] = None
    model: str = "gpt-5.3-codex"
    environment_variables: list[CodexEnvironmentVariable] = Field(
        default_factory=list, alias="environmentVariables"
    )
    auth_flow: Optional[CodexAuthFlow] = Field(None, alias="authFlow")
    last_synced_at: Optional[int] = Field(None, alias="lastSyncedAt")
    last_sync_error: Optional[str] = Field(None, alias="lastSyncError")


class GitSettings(CamelModel):
    user_name: Optional[str] = Field(None, alias="userName")
    user_email: Optional[str] = Field(None, alias="userEmail")
    signing_key: Optional[str] = Field(None, alias="signingKey")


class UserSettings(CamelModel):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    claude_code: ClaudeCodeSettings = Field(default_factory=ClaudeCodeSettings, alias="claudeCode")
    codex: CodexSettings = Field(default_factory=CodexSettings)
    git: GitSettings = Field(default_factory=GitSettings)


class UserProfileResponse(CamelModel):
    data: UserProfile


class UserSettingsResponse(CamelModel):
    data: UserSettings


class UserSettingsUpdate(CamelModel):
    general: Optional[GeneralSettings] = None
    ssh: Optional[SSHSettings] = None
    claude_code: Optional[ClaudeCodeSettings] = Field(None, alias="claudeCode")
    codex: Optional[CodexSettings] = None
    git: Optional[GitSettings] = None


class SSHKeyPairResponse(CamelModel):
    """SSH key pair generation response"""
    public_key: str = Field(..., alias="publicKey")
    private_key: str = Field(..., alias="privateKey")
    fingerprint: str
    generated_at: datetime = Field(..., alias="generatedAt")
