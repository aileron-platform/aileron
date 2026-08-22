"""Prompt Invocation Catalog API models."""

from enum import StrEnum

from pydantic import BaseModel, Field

from .config import PromptInvocationTool


class PromptInvocationScope(StrEnum):
    """Prompt Invocation source scope."""

    PROJECT = "project"
    USER = "user"
    PLUGIN = "plugin"


class PromptInvocationKind(StrEnum):
    """Prompt Invocation resource kind."""

    SLASH_COMMAND = "slash-command"
    SKILL = "skill"


class CatalogCompleteness(StrEnum):
    """Prompt Invocation Catalog source completeness."""

    COMPLETE = "complete"
    DEGRADED = "degraded"


class PromptInvocationItem(BaseModel):
    """Invocation-ready Catalog item."""

    id: str
    source_key: str = Field(alias="sourceKey")
    file_name: str = Field(alias="fileName")
    kind: PromptInvocationKind
    scope: PromptInvocationScope
    plugin_name: str | None = Field(default=None, alias="pluginName")
    namespace: str | None = None
    display_name: str = Field(alias="displayName")
    category: str
    description: str
    invocation: str
    tags: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PromptInvocationSourceError(BaseModel):
    """Failure from one Catalog source."""

    source: str
    error_code: str = Field(alias="errorCode")
    message: str

    model_config = {"populate_by_name": True}


class PromptInvocationCatalogResponse(BaseModel):
    """Aggregated Prompt Invocation Catalog."""

    workspace_id: str = Field(alias="workspaceId")
    agentic_tool: PromptInvocationTool = Field(alias="agenticTool")
    completeness: CatalogCompleteness
    revision: str
    available_scopes: list[PromptInvocationScope] = Field(alias="availableScopes")
    source_errors: list[PromptInvocationSourceError] = Field(
        default_factory=list,
        alias="sourceErrors",
    )
    items: list[PromptInvocationItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
