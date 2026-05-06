"""Claude Code plugin workflow models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ClaudePluginScope = Literal["user", "project", "local"]


class ClaudePluginInstallation(BaseModel):
    """Single Claude Code plugin installation scope."""

    scope: ClaudePluginScope
    enabled: bool
    installPath: str
    projectPath: str | None = None
    version: str | None = None
    installedAt: str | None = None
    lastUpdated: str | None = None


class ClaudePluginResourceCounts(BaseModel):
    """Resource counts contributed by a Claude Code plugin."""

    commands: int = 0
    agents: int = 0
    hooks: int = 0
    mcpServers: int = 0
    skills: int = 0
    lspServers: int = 0


class ClaudePluginMarketplaceSummary(BaseModel):
    """Marketplace sidecar used for plugin list filters."""

    name: str
    owner: str | None = None
    pluginCount: int = 0
    source: str | None = None


class ClaudePluginDependency(BaseModel):
    """Declared plugin dependency."""

    name: str
    version: str | None = None
    marketplace: str | None = None


class ClaudePluginSummary(BaseModel):
    """Flattened Claude Code plugin list item."""

    id: str
    name: str
    marketplace: str | None = None
    version: str | None = None
    description: str | None = None
    author: str | None = None
    category: str | None = None
    homepage: str | None = None
    enabled: bool = False
    installations: list[ClaudePluginInstallation] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    resourceCounts: ClaudePluginResourceCounts = Field(default_factory=ClaudePluginResourceCounts)


class ClaudePluginsResponse(BaseModel):
    """Claude Code plugin list response."""

    workspaceId: str
    plugins: list[ClaudePluginSummary] = Field(default_factory=list)
    marketplaces: list[ClaudePluginMarketplaceSummary] = Field(default_factory=list)


class ClaudePluginDetail(ClaudePluginSummary):
    """Claude Code plugin detail response."""

    repository: str | None = None
    license: str | None = None
    readme: str | None = None
    dependencies: list[ClaudePluginDependency] = Field(default_factory=list)
    resources: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)


class ClaudePluginDetailResponse(BaseModel):
    """Claude Code plugin detail response wrapper."""

    workspaceId: str
    plugin: ClaudePluginDetail


class ClaudePluginToggleRequest(BaseModel):
    """Claude Code plugin toggle request."""

    enabled: bool
    scope: ClaudePluginScope


class ClaudePluginToggleResponse(BaseModel):
    """Claude Code plugin toggle response."""

    workspaceId: str
    pluginId: str
    scope: ClaudePluginScope
    enabled: bool
