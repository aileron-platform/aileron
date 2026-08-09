"""Workspace agentic capability models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.config.model_registry import normalize_model_selection
from app.modules.settings.models import UserSettings, UserToolModelSelection
from app.core.pydantic import CamelModel

AgenticToolId = Literal["claude", "codex", "opencode"]
ClaudeMode = Literal["execute", "plan"]

CLAUDE_CONTEXT_WINDOW = 200000
CODEX_CONTEXT_WINDOW = 200000
OPENCODE_CONTEXT_WINDOW = 128000


class ToolCapability(CamelModel):
    id: AgenticToolId
    models: list[str] = Field(..., min_length=1)
    default_model: str = Field(..., alias="defaultModel")
    modes: list[ClaudeMode] | None = None
    default_mode: ClaudeMode | None = Field(None, alias="defaultMode")
    context_window: int = Field(..., gt=0, alias="contextWindow")

    @model_validator(mode="after")
    def validate_tool_defaults(self) -> "ToolCapability":
        if self.default_model not in self.models:
            raise ValueError("default_model must be one of models")
        if self.modes is None:
            if self.default_mode is not None:
                raise ValueError("default_mode must be empty when modes are empty")
            return self
        if not self.modes:
            raise ValueError("modes must not be empty when provided")
        if self.default_mode is None:
            raise ValueError("default_mode is required when modes are provided")
        if self.default_mode not in self.modes:
            raise ValueError("default_mode must be one of modes")
        return self


class WorkspaceCapabilities(CamelModel):
    tools: list[ToolCapability] = Field(..., min_length=1)
    default_tool: AgenticToolId = Field(..., alias="defaultTool")

    @model_validator(mode="after")
    def validate_workspace_defaults(self) -> "WorkspaceCapabilities":
        tool_ids = {tool.id for tool in self.tools}
        if self.default_tool not in tool_ids:
            raise ValueError("default_tool must be one of tools")
        return self

    def validate_selection(
        self,
        tool: str,
        model: str,
        claude_mode: ClaudeMode | None,
    ) -> bool:
        capability = next((item for item in self.tools if item.id == tool), None)
        if capability is None or model not in capability.models:
            return False
        if capability.modes is None:
            return claude_mode is None
        return claude_mode in capability.modes


def _selection(
    settings_selection: UserToolModelSelection,
    tool_id: AgenticToolId,
) -> UserToolModelSelection:
    if settings_selection.allowed_models and settings_selection.default_model:
        return settings_selection
    normalized = normalize_model_selection(tool_id, None, mode="read")
    return UserToolModelSelection.model_validate(normalized.model_dump(by_alias=True))


def build_capabilities_from_settings(settings: UserSettings) -> WorkspaceCapabilities:
    claude_selection = _selection(settings.claude_code.model_selection, "claude")
    codex_selection = _selection(settings.codex.model_selection, "codex")
    opencode_selection = _selection(settings.opencode.model_selection, "opencode")

    return WorkspaceCapabilities(
        default_tool="claude",
        tools=[
            ToolCapability(
                id="claude",
                models=list(claude_selection.allowed_models),
                default_model=claude_selection.default_model,
                modes=["execute", "plan"],
                default_mode="execute",
                context_window=CLAUDE_CONTEXT_WINDOW,
            ),
            ToolCapability(
                id="codex",
                models=list(codex_selection.allowed_models),
                default_model=codex_selection.default_model,
                modes=None,
                default_mode=None,
                context_window=CODEX_CONTEXT_WINDOW,
            ),
            ToolCapability(
                id="opencode",
                models=list(opencode_selection.allowed_models),
                default_model=opencode_selection.default_model,
                modes=None,
                default_mode=None,
                context_window=OPENCODE_CONTEXT_WINDOW,
            ),
        ],
    )
