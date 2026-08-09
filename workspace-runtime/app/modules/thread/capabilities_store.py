from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base

JsonbType = JSONB().with_variant(JSON(), "sqlite")

AgenticToolId = Literal["claude", "codex", "opencode"]
ClaudeMode = Literal["execute", "plan"]


class ToolCapability(BaseModel):
    id: AgenticToolId
    models: list[str] = Field(min_length=1)
    default_model: str
    modes: list[ClaudeMode] | None = None
    default_mode: ClaudeMode | None = None
    context_window: int = Field(gt=0)


class WorkspaceCapabilities(BaseModel):
    tools: list[ToolCapability] = Field(min_length=1)
    default_tool: AgenticToolId

    @model_validator(mode="after")
    def _defaults_must_be_valid(self) -> WorkspaceCapabilities:
        tool_ids = {tool.id for tool in self.tools}
        if self.default_tool not in tool_ids:
            raise ValueError("default_tool must reference a configured tool")

        for tool in self.tools:
            if tool.default_model not in tool.models:
                raise ValueError("default_model must reference a configured model")
            if tool.modes is None:
                if tool.default_mode is not None:
                    raise ValueError("default_mode requires modes")
                continue
            if tool.default_mode is None or tool.default_mode not in tool.modes:
                raise ValueError("default_mode must reference a configured mode")
        return self

    def validate_selection(
        self, tool: str, model: str, claude_mode: str | None
    ) -> bool:
        cap = next((item for item in self.tools if item.id == tool), None)
        if cap is None or model not in cap.models:
            return False
        if cap.modes is not None:
            return claude_mode is not None and claude_mode in cap.modes
        return claude_mode is None


class RuntimeCapabilitiesModel(Base):
    """Persisted manager-pushed capability snapshot."""

    __tablename__ = "runtime_capabilities"

    workspace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    capabilities: Mapped[dict] = mapped_column(JsonbType, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CapabilitiesStore:
    """Last-write-wins runtime capability snapshot store."""

    async def put(
        self, db: AsyncSession, workspace_id: str, capabilities: dict
    ) -> None:
        snapshot = WorkspaceCapabilities.model_validate(capabilities)
        normalized = snapshot.model_dump(mode="json")

        result = await db.execute(
            select(RuntimeCapabilitiesModel).where(
                RuntimeCapabilitiesModel.workspace_id == workspace_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            db.add(
                RuntimeCapabilitiesModel(
                    workspace_id=workspace_id,
                    capabilities=normalized,
                    synced_at=datetime.now(UTC),
                )
            )
        else:
            row.capabilities = normalized
            row.synced_at = datetime.now(UTC)
        await db.flush()

    async def get(
        self, db: AsyncSession, workspace_id: str
    ) -> WorkspaceCapabilities | None:
        result = await db.execute(
            select(RuntimeCapabilitiesModel).where(
                RuntimeCapabilitiesModel.workspace_id == workspace_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return WorkspaceCapabilities.model_validate(row.capabilities)
