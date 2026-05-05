"""Gemini extension data models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GeminiExtensionInstallInfo(BaseModel):
    """Metadata written by Gemini CLI during extension install."""

    source: str | None = None
    type: str | None = None
    releaseTag: str | None = None

    model_config = ConfigDict(extra="allow")


class GeminiExtensionMcpServer(BaseModel):
    """Extension-contributed MCP server."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class GeminiExtensionSlashCommand(BaseModel):
    """Extension-contributed slash command."""

    fileName: str
    namespace: str | None = None
    description: str | None = None
    content: str = ""
    path: str


class GeminiExtensionSkill(BaseModel):
    """Extension-contributed skill."""

    name: str
    path: str
    content: str = ""


class GeminiExtensionHookDocument(BaseModel):
    """Extension-contributed hook document."""

    hooks: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    path: str | None = None


class GeminiExtensionPolicy(BaseModel):
    """Extension-contributed policy preview."""

    path: str
    content: str


class GeminiExtensionContextFile(BaseModel):
    """Extension-contributed context file preview."""

    path: str
    content: str


class GeminiExtensionPackage(BaseModel):
    """Installed Gemini extension package."""

    name: str
    version: str | None = None
    description: str | None = None
    path: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    installInfo: GeminiExtensionInstallInfo | None = None
    overrides: list[str] = Field(default_factory=list)
    enabledHere: bool = False
    mcpServers: list[GeminiExtensionMcpServer] = Field(default_factory=list)
    slashCommands: list[GeminiExtensionSlashCommand] = Field(default_factory=list)
    skills: list[GeminiExtensionSkill] = Field(default_factory=list)
    hooks: list[GeminiExtensionHookDocument] = Field(default_factory=list)
    policies: list[GeminiExtensionPolicy] = Field(default_factory=list)
    excludeTools: list[str] = Field(default_factory=list)
    contextFile: GeminiExtensionContextFile | None = None


class GeminiExtensionSummary(BaseModel):
    """List row for an installed Gemini extension."""

    name: str
    version: str | None = None
    description: str | None = None
    contextFileName: str | None = None
    installSource: str | None = None
    installType: str | None = None
    releaseTag: str | None = None
    enabledHere: bool
    overrides: list[str] = Field(default_factory=list)
    resourceCounts: dict[Literal["mcp", "commands", "skills", "hooks", "policies"], int]
    excludeToolsCount: int


class GeminiExtensionListResponse(BaseModel):
    """Gemini extensions list response."""

    workspaceId: str
    extensions: list[GeminiExtensionSummary] = Field(default_factory=list)


class GeminiExtensionDetailResponse(BaseModel):
    """Gemini extension detail response."""

    workspaceId: str
    extension: GeminiExtensionPackage


class GeminiExtensionToggleResponse(BaseModel):
    """Gemini extension enablement mutation response."""

    workspaceId: str
    name: str
    enabledHere: bool
    overrides: list[str] = Field(default_factory=list)


class GeminiExtensionCommandError(RuntimeError):
    """Gemini CLI subprocess failed."""

    def __init__(self, command: list[str], stderr: str, returncode: int) -> None:
        self.command = command
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(stderr or f"Gemini command failed with exit code {returncode}")
