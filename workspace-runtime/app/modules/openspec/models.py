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


class OpenSpecWorkspaceProfile(str, Enum):
    """OpenSpec workspace 目前啟用的 workflow profile。"""

    CORE = "core"
    EXPANDED = "expanded"
    CUSTOM = "custom"


class OpenSpecActionInputKind(str, Enum):
    """OpenSpec action 在 UI 需要的輸入型別。"""

    NONE = "none"
    CHANGE = "change"
    STRUCTURED = "structured"


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
    CUSTOMIZATION = "customization"


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
    recommendedReason: str | None = Field(default=None, description="推薦原因")
    requiresChange: bool = Field(default=False, description="是否需要 change context")
    supportsChangeArgument: bool = Field(default=False, description="是否支援 change name 參數")
    inputKind: OpenSpecActionInputKind = Field(default=OpenSpecActionInputKind.NONE, description="UI 輸入型別")
    exampleCommand: str | None = Field(default=None, description="範例指令")
    draftTemplate: str = Field(description="插入 chat draft 的預設內容")


class OpenSpecWorkspaceState(BaseModel):
    """Workspace OpenSpec 狀態。"""

    cliInstalled: bool = Field(description="是否安裝 OpenSpec CLI")
    cliVersion: str | None = Field(default=None, description="OpenSpec CLI 版本")
    initialized: bool = Field(description="是否已初始化 openspec/")
    profile: OpenSpecWorkspaceProfile = Field(description="目前 profile")
    projectSynced: bool | None = Field(default=None, description="專案是否與 workflow 設定同步")
    activeChanges: list[OpenSpecChangeSummary] = Field(default_factory=list, description="進行中的 changes")


class OpenSpecWorkspaceSummaryCounts(BaseModel):
    """Workspace OpenSpec grouped counts for generic surfaces."""

    inProgress: int = Field(default=0, description="進行中 changes 數量")
    complete: int = Field(default=0, description="已完成 changes 數量")
    archived: int = Field(default=0, description="已封存 changes 數量")


class OpenSpecWorkspaceSummaryResponse(BaseModel):
    """Workspace OpenSpec 輕量 summary 回應。"""

    workspaceId: str = Field(description="Workspace ID")
    initialized: bool = Field(description="是否已初始化 openspec/")
    counts: OpenSpecWorkspaceSummaryCounts = Field(description="依狀態分組的 change 計數")


class OpenSpecWorkspaceResponse(BaseModel):
    """OpenSpec workspace 狀態與 actions 聚合回應。"""

    workspaceId: str = Field(description="Workspace ID")
    state: OpenSpecWorkspaceState = Field(description="OpenSpec 狀態")
    actions: list[OpenSpecActionItem] = Field(default_factory=list, description="可用 actions")
    changes: list[OpenSpecNavigationChange] = Field(default_factory=list, description="OpenSpec 導覽 changes")


class OpenSpecCustomizationFileKind(str, Enum):
    """Customization 檔案種類。"""

    CONFIG = "config"
    SCHEMA = "schema"
    TEMPLATE = "template"


class OpenSpecCustomizationTemplateFile(BaseModel):
    """Schema template 檔案摘要。"""

    name: str = Field(description="Template 檔名")
    path: str = Field(description="Template 路徑")


class OpenSpecCustomizationSchema(BaseModel):
    """Project-local schema 摘要。"""

    name: str = Field(description="Schema 名稱")
    path: str = Field(description="Schema 目錄路徑")
    schemaPath: str = Field(description="schema.yaml 路徑")
    isDefault: bool = Field(description="是否為目前 default schema")
    isInvalid: bool = Field(description="Schema 是否驗證失敗")
    templateFiles: list[OpenSpecCustomizationTemplateFile] = Field(default_factory=list, description="Template 檔案")


class OpenSpecCustomizationStateResponse(BaseModel):
    """Customization explorer 所需的聚合狀態。"""

    workspaceId: str = Field(description="Workspace ID")
    configPath: str = Field(description="config.yaml 路徑")
    configPresent: bool = Field(description="config.yaml 是否存在")
    defaultSchema: str | None = Field(default=None, description="目前 project default schema")
    builtInSchemas: list[str] = Field(default_factory=list, description="可 fork 的 built-in schemas")
    schemas: list[OpenSpecCustomizationSchema] = Field(default_factory=list, description="Project-local schemas")


class OpenSpecCustomizationFileResponse(BaseModel):
    """Customization 檔案內容。"""

    workspaceId: str = Field(description="Workspace ID")
    path: str = Field(description="檔案路徑")
    name: str = Field(description="檔名")
    kind: OpenSpecCustomizationFileKind = Field(description="檔案種類")
    content: str = Field(description="檔案內容")
    editable: bool = Field(description="是否可編輯")
    language: str = Field(description="編輯器語言")
    schemaName: str | None = Field(default=None, description="所屬 schema")
    metadata: dict[str, object] = Field(default_factory=dict, description="附加 metadata")


class OpenSpecCustomizationFileUpdateRequest(BaseModel):
    """更新 customization 檔案內容。"""

    content: str = Field(description="新的檔案內容")


class OpenSpecCustomizationSchemaForkRequest(BaseModel):
    """Fork schema 請求。"""

    sourceSchema: str = Field(description="來源 schema")
    destinationSchema: str = Field(description="目標 schema 名稱")


class OpenSpecCustomizationSchemaCreateRequest(BaseModel):
    """建立 schema 請求。"""

    name: str = Field(description="Schema 名稱")
    description: str | None = Field(default=None, description="Schema 描述")
    artifacts: list[str] = Field(default_factory=list, description="Artifacts")


class OpenSpecCustomizationActionResponse(BaseModel):
    """Customization action 一般回應。"""

    success: bool = Field(default=True, description="是否成功")
    message: str = Field(description="訊息")
    schemaName: str | None = Field(default=None, description="Schema 名稱")
    path: str | None = Field(default=None, description="相關路徑")


class OpenSpecCustomizationValidationRequest(BaseModel):
    """Validation 請求。"""

    path: str = Field(description="目前 context 路徑")


class OpenSpecCustomizationDiagnostic(BaseModel):
    """Validation diagnostics。"""

    level: str = Field(description="等級")
    message: str = Field(description="訊息")


class OpenSpecCustomizationValidationResponse(BaseModel):
    """Customization validation 結果。"""

    workspaceId: str = Field(description="Workspace ID")
    targetPath: str = Field(description="驗證來源 path")
    schemaName: str | None = Field(default=None, description="驗證的 schema")
    valid: bool = Field(description="是否通過")
    diagnostics: list[OpenSpecCustomizationDiagnostic] = Field(default_factory=list, description="診斷結果")


class OpenSpecCustomizationResolutionStep(BaseModel):
    """Schema resolution step。"""

    order: int = Field(description="順序")
    label: str = Field(description="步驟名稱")
    value: str | None = Field(default=None, description="該步驟值")
    selected: bool = Field(default=False, description="是否為採用來源")


class OpenSpecCustomizationDebugResponse(BaseModel):
    """Customization debug / schema resolution 結果。"""

    workspaceId: str = Field(description="Workspace ID")
    targetPath: str = Field(description="來源 path")
    schemaName: str | None = Field(default=None, description="推導出的 schema 名稱")
    resolvedName: str | None = Field(default=None, description="最終 resolved schema")
    source: str | None = Field(default=None, description="來源")
    path: str | None = Field(default=None, description="resolved path")
    resolutionOrder: list[OpenSpecCustomizationResolutionStep] = Field(default_factory=list, description="Resolution steps")
