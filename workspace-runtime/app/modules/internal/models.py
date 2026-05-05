"""Internal API data models"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EnvironmentVariable(BaseModel):
    """Environment variable model"""
    key: str = Field(..., description="Environment variable name")
    value: str = Field(..., description="Environment variable value")


class SSHKeysRequest(BaseModel):
    """SSH Keys configuration request"""
    private_key: str = Field(..., alias="privateKey", description="SSH private key")
    public_key: str = Field(..., alias="publicKey", description="SSH public key")

    class Config:
        populate_by_name = True


class OAuthAccountInfo(BaseModel):
    """OAuth account information"""
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
    """Claude Code configuration request"""
    auth_method: Optional[str] = Field(
        None,
        alias="authMethod",
        description="Authentication method (subscription or api_key)"
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
        description="Token expiration time (millisecond timestamp, legacy may be ISO8601 string)",
    )
    oauth_account: Optional[OAuthAccountInfo] = Field(
        None,
        alias="oauthAccount",
        description="OAuth account information"
    )
    api_key: Optional[str] = Field(
        None,
        alias="apiKey",
        description="Claude API Key"
    )
    model: Optional[str] = Field(
        None,
        alias="model",
        description="Unified model choice (used for both subscription and apikey)"
    )
    environment_variables: List[EnvironmentVariable] = Field(
        default_factory=list,
        alias="environmentVariables",
        description="Environment variable list"
    )

    class Config:
        populate_by_name = True


class CodexAccountInfo(BaseModel):
    """Codex account summary."""
    account_id: Optional[str] = Field(None, alias="accountId")
    email: Optional[str] = None
    plan_type: Optional[str] = Field(None, alias="planType")

    class Config:
        populate_by_name = True


class CodexAuthFlow(BaseModel):
    """Codex login flow metadata."""
    login_id: Optional[str] = Field(None, alias="loginId")
    auth_url: Optional[str] = Field(None, alias="authUrl")
    verification_url: Optional[str] = Field(None, alias="verificationUrl")
    user_code: Optional[str] = Field(None, alias="userCode")
    expires_at: Optional[int] = Field(None, alias="expiresAt")

    class Config:
        populate_by_name = True


class CodexAuthTokens(BaseModel):
    """Codex external auth tokens used only for runtime-side fallback."""
    access_token: Optional[str] = Field(None, alias="accessToken")
    refresh_token: Optional[str] = Field(None, alias="refreshToken")
    id_token: Optional[str] = Field(None, alias="idToken")
    expires_at: Optional[int] = Field(None, alias="expiresAt")

    class Config:
        populate_by_name = True


class CodexCliState(BaseModel):
    """Codex CLI files synchronized from a logged-in workspace."""
    auth_json: Optional[dict[str, Any]] = Field(None, alias="authJson")
    config_toml: Optional[str] = Field(None, alias="configToml")
    installation_id: Optional[str] = Field(None, alias="installationId")

    class Config:
        populate_by_name = True


class CodexSettingsRequest(BaseModel):
    """Codex configuration request."""
    auth_method: Optional[str] = Field(
        None,
        alias="authMethod",
        description="Authentication method (subscription or apikey)",
    )
    login_status: Optional[str] = Field(None, alias="loginStatus")
    account: Optional[CodexAccountInfo] = None
    model: Optional[str] = None
    environment_variables: List[EnvironmentVariable] = Field(
        default_factory=list,
        alias="environmentVariables",
        description="Codex environment variable list",
    )
    auth_flow: Optional[CodexAuthFlow] = Field(None, alias="authFlow")
    auth_tokens: Optional[CodexAuthTokens] = Field(
        None,
        alias="authTokens",
        description="Optional runtime-only token bootstrap payload",
    )
    cli_state: Optional[CodexCliState] = Field(
        None,
        alias="cliState",
        description="Optional Codex CLI files synchronized from a logged-in workspace",
    )
    clear_auth: bool = Field(False, alias="clearAuth")

    class Config:
        populate_by_name = True


class GeminiRequest(BaseModel):
    """Gemini configuration request"""
    auth_method: Optional[str] = Field(None, alias="authMethod")
    account_email: Optional[str] = Field(None, alias="accountEmail")
    access_token: Optional[str] = Field(None, alias="accessToken")
    refresh_token: Optional[str] = Field(None, alias="refreshToken")
    id_token: Optional[str] = Field(None, alias="idToken")
    expires_at: Optional[int] = Field(None, alias="expiresAt")
    scope: Optional[str] = None
    environment_variables: List[EnvironmentVariable] = Field(
        default_factory=list, alias="environmentVariables"
    )

    class Config:
        populate_by_name = True


class GitSettingsRequest(BaseModel):
    """Git configuration request"""
    user_name: str = Field(..., alias="userName", description="Git user name")
    user_email: str = Field(..., alias="userEmail", description="Git user email")

    class Config:
        populate_by_name = True


class FirewallConfigRequest(BaseModel):
    """Firewall configuration request"""
    network_access_enabled: bool = Field(..., alias="networkAccessEnabled", description="Network access permission switch")
    domain_access_mode: str = Field(..., alias="domainAccessMode", description="Allowed domain mode (all/specific)")
    allowed_domains: List[str] = Field(default_factory=list, alias="allowedDomains", description="Allowed domain list")

    class Config:
        populate_by_name = True


class InternalApiResponse(BaseModel):
    """Internal API unified response format"""
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Response message")
    details: Optional[dict] = Field(None, description="Detailed information")


class SetupCheckDetail(BaseModel):
    """Detailed status of initialization check items"""

    status: str = Field(..., description="Item status")
    message: str = Field(..., description="Status description")


class WorkspaceSetupStatusResponse(BaseModel):
    """Workspace initialization status response"""

    success: bool = Field(..., description="Whether status retrieval succeeded")
    message: str = Field(..., description="Response message")
    checks: Dict[str, SetupCheckDetail] = Field(default_factory=dict, description="Status of each check item")


__all__ = [
    "EnvironmentVariable",
    "SSHKeysRequest",
    "ClaudeCodeRequest",
    "CodexAccountInfo",
    "CodexAuthFlow",
    "CodexAuthTokens",
    "CodexCliState",
    "CodexSettingsRequest",
    "GeminiRequest",
    "GitSettingsRequest",
    "FirewallConfigRequest",
    "InternalApiResponse",
    "SetupCheckDetail",
    "WorkspaceSetupStatusResponse",
]
