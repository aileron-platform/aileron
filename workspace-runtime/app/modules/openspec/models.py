"""OpenSpec runtime API models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class OpenSpecActionAvailability(str, Enum):
    """OpenSpec action 可用性狀態。"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    HIDDEN = "hidden"
    SETUP_REQUIRED = "setup_required"
    SYNC_REQUIRED = "sync_required"
    BLOCKED = "blocked"


class OpenSpecActionGroup(str, Enum):
    """OpenSpec action 分組。"""

    START = "start"
    PLAN = "plan"
    IMPLEMENT = "implement"
    FINALIZE = "finalize"
    LEARN = "learn"


class OpenSpecActionProfile(str, Enum):
    """OpenSpec action 所屬 workflow profile。"""

    CORE = "core"
    EXPANDED = "expanded"


class OpenSpecChangeStatus(str, Enum):
    """OpenSpec change 導覽狀態。"""

    IN_PROGRESS = "in-progress"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class OpenSpecActionContextSubview(str, Enum):
    """OpenSpec action 解析所依據的前端 subview。"""

    IN_PROGRESS = "in-progress"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class OpenSpecChangeSummary(BaseModel):
    """OpenSpec change 摘要。"""

    name: str = Field(description="Change 名稱")
    status: str | None = Field(default=None, description="Change 狀態")
    completedTasks: int = Field(default=0, description="已完成任務數")
    totalTasks: int = Field(default=0, description="總任務數")
    lastModified: str | None = Field(default=None, description="最後更新時間")


class OpenSpecSpecDocument(BaseModel):
    """OpenSpec spec 文件摘要。"""

    capabilityName: str = Field(description="Capability 名稱")
    path: str = Field(description="Spec 文件路徑")


class OpenSpecNavigationChange(BaseModel):
    """OpenSpec 第二欄導覽所需的 change 資料。"""

    name: str = Field(description="Change 名稱")
    status: OpenSpecChangeStatus = Field(description="Change 導覽狀態")
    archived: bool = Field(description="是否為 archived change")
    proposalPath: str | None = Field(default=None, description="proposal.md 路徑")
    designPath: str | None = Field(default=None, description="design.md 路徑")
    tasksPath: str | None = Field(default=None, description="tasks.md 路徑")
    specs: list[OpenSpecSpecDocument] = Field(default_factory=list, description="Spec 文件列表")
    completedTasks: int = Field(default=0, description="已完成 checklist task 數")
    totalTasks: int = Field(default=0, description="checklist task 總數")
    lastModified: str | None = Field(default=None, description="最後更新時間")


class OpenSpecActionItem(BaseModel):
    """OpenSpec action 定義。"""

    id: str = Field(description="Action ID")
    title: str = Field(description="顯示標題")
    description: str = Field(description="描述")
    group: OpenSpecActionGroup = Field(description="分組")
    profile: OpenSpecActionProfile = Field(description="所屬 profile")
    availability: OpenSpecActionAvailability = Field(description="可用性")
    reason: str | None = Field(default=None, description="狀態原因")
    recommended: bool = Field(default=False, description="是否推薦")
    requiresChange: bool = Field(default=False, description="是否需要 change context")
    supportsChangeArgument: bool = Field(default=False, description="是否支援 change name 參數")
    draftTemplate: str = Field(description="插入 chat draft 的預設內容")


class OpenSpecWorkspaceState(BaseModel):
    """Workspace OpenSpec 狀態。"""

    cliInstalled: bool = Field(description="是否安裝 OpenSpec CLI")
    cliVersion: str | None = Field(default=None, description="OpenSpec CLI 版本")
    initialized: bool = Field(description="是否已初始化 openspec/")
    profile: OpenSpecActionProfile = Field(description="目前 profile")
    projectSynced: bool | None = Field(default=None, description="專案是否與 workflow 設定同步")
    activeChanges: list[OpenSpecChangeSummary] = Field(default_factory=list, description="進行中的 changes")


class OpenSpecWorkspaceResponse(BaseModel):
    """OpenSpec workspace 狀態與 actions 聚合回應。"""

    workspaceId: str = Field(description="Workspace ID")
    state: OpenSpecWorkspaceState = Field(description="OpenSpec 狀態")
    actions: list[OpenSpecActionItem] = Field(default_factory=list, description="可用 actions")
    changes: list[OpenSpecNavigationChange] = Field(default_factory=list, description="OpenSpec 導覽 changes")
