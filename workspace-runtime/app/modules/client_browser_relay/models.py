"""
Client Browser Relay data models

Defines data structures required by CDP Relay Server
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


# ============================================================================
# Target-related models
# ============================================================================


class TargetInfo(BaseModel):
    """CDP Target information"""

    target_id: str = Field(..., alias="targetId")
    type: str = "page"
    title: str = ""
    url: str = ""
    attached: bool = False
    browser_context_id: str = Field("default", alias="browserContextId")

    class Config:
        populate_by_name = True


@dataclass
class ConnectedTarget:
    """Connected Target"""

    session_id: str
    target_id: str
    target_info: TargetInfo


@dataclass
class PlaywrightClient:
    """Playwright client connection"""

    id: str
    known_targets: set[str] = field(default_factory=set)


# ============================================================================
# API Response models
# ============================================================================


class RelayStatusResponse(BaseModel):
    """Relay Server status response"""

    ws_endpoint: str = Field(..., alias="wsEndpoint")
    extension_connected: bool = Field(..., alias="extensionConnected")
    mode: str = "extension"
    connected_targets_count: int = Field(0, alias="connectedTargetsCount")
    playwright_clients_count: int = Field(0, alias="playwrightClientsCount")

    class Config:
        populate_by_name = True


class RelayHealthResponse(BaseModel):
    """Minimal unauthenticated health response."""

    status: str = "ok"


class NamedPagesResponse(BaseModel):
    """Named pages list response"""

    pages: list[str] = Field(default_factory=list)


class CreatePageRequest(BaseModel):
    """Create page request"""

    name: str


class CreatePageResponse(BaseModel):
    """Create page response"""

    ws_endpoint: str = Field(..., alias="wsEndpoint")
    name: str
    target_id: str = Field(..., alias="targetId")
    url: str

    class Config:
        populate_by_name = True


class DeletePageResponse(BaseModel):
    """Delete page response"""

    success: bool
