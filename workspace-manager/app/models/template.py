"""模板模型"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .common import TimestampMixin


class TemplateAuthor(BaseModel):
    """模板作者資訊"""

    name: str = Field(description="作者名稱")
    email: Optional[str] = Field(default=None, description="作者電子郵件")
    url: Optional[str] = Field(default=None, description="作者個人頁面")


class TemplateCreate(BaseModel):
    """建立模板請求"""

    template_id: str = Field(description="模板代號（kebab-case，只能英文）", alias="templateId")
    name: str = Field(description="模板名稱")
    description: Optional[str] = Field(default=None, description="模板描述")
    version: Optional[str] = Field(default="1.0.0", description="版本號")
    author: TemplateAuthor = Field(description="作者資訊")
    keywords: Optional[List[str]] = Field(default_factory=list, description="關鍵字陣列")
    cli_type: Literal["claude-code", "codex", "gemini"] = Field(
        default="claude-code", description="CLI 類型"
    )
    status: Literal["draft", "released"] = Field(default="draft", description="模板狀態")
    init_commands: Optional[str] = Field(default=None, description="初始化指令", alias="initCommands")

    model_config = {"populate_by_name": True}


class TemplateUpdate(BaseModel):
    """更新模板請求"""

    name: Optional[str] = Field(default=None, description="模板名稱")
    description: Optional[str] = Field(default=None, description="模板描述")
    version: Optional[str] = Field(default=None, description="版本號")
    author: Optional[TemplateAuthor] = Field(default=None, description="作者資訊")
    keywords: Optional[List[str]] = Field(default=None, description="關鍵字陣列")
    categoryId: Optional[str] = Field(default=None, description="分類 ID", alias="categoryId")
    cli_type: Optional[Literal["claude-code", "codex", "gemini"]] = Field(
        default=None, description="CLI 類型"
    )
    status: Optional[Literal["draft", "released"]] = Field(default=None, description="模板狀態")
    init_commands: Optional[str] = Field(default=None, description="初始化指令", alias="initCommands")

    model_config = {"populate_by_name": True}


class TemplateMcpServer(BaseModel):
    """MCP 伺服器配置"""

    id: str = Field(description="伺服器 ID")
    name: str = Field(description="伺服器名稱")
    type: Literal["stdio", "http", "sse"] = Field(default="stdio", description="傳輸類型")
    command: Optional[str] = Field(default=None, description="執行命令")
    args: Optional[List[str]] = Field(default=None, description="命令參數")
    url: Optional[str] = Field(default=None, description="伺服器 URL")
    description: Optional[str] = Field(default=None, description="伺服器描述")
    env: Optional[Dict[str, str]] = Field(default=None, description="環境變數")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP 標頭")


class TemplateSlashCommand(BaseModel):
    """Slash 命令配置"""

    id: str = Field(description="命令 ID")
    fileName: str = Field(description="檔案名稱")
    description: Optional[str] = Field(default=None, description="命令描述")
    content: str = Field(description="命令內容")


class TemplateHook(BaseModel):
    """Hook 配置"""

    id: str = Field(description="Hook ID")
    name: str = Field(description="Hook 名稱")
    event: str = Field(description="事件名稱")
    matcher: Optional[str] = Field(default=None, description="匹配器")
    action: Literal["command", "script"] = Field(default="command", description="動作類型")
    command: Optional[str] = Field(default=None, description="執行命令")
    script: Optional[str] = Field(default=None, description="腳本內容")
    timeout: Optional[int] = Field(default=None, description="逾時秒數")


class TemplateSubAgent(BaseModel):
    """SubAgent 配置"""

    id: str = Field(description="SubAgent ID")
    fileName: str = Field(description="檔案名稱")
    description: Optional[str] = Field(default=None, description="描述")
    content: str = Field(description="檔案內容")


class TemplateOutputStyle(BaseModel):
    """輸出樣式配置"""

    id: str = Field(description="樣式 ID")
    fileName: str = Field(description="檔案名稱")
    description: Optional[str] = Field(default=None, description="描述")
    content: str = Field(description="檔案內容")


class TemplateFileNode(BaseModel):
    """檔案節點"""

    id: str = Field(description="節點 ID")
    name: str = Field(description="節點名稱")
    path: str = Field(description="檔案路徑")
    type: Literal["file", "directory"] = Field(description="節點類型")
    size: Optional[int] = Field(default=None, description="檔案大小")
    content: Optional[str] = Field(default=None, description="檔案內容")
    children: Optional[List["TemplateFileNode"]] = Field(default=None, description="子節點")


class Template(TimestampMixin):
    """模板回應模型"""

    id: str = Field(description="模板 ID")
    name: str = Field(description="模板名稱")
    description: Optional[str] = Field(default=None, description="模板描述")
    version: str = Field(default="1.0.0", description="版本號")
    author: TemplateAuthor = Field(description="作者資訊")
    keywords: List[str] = Field(default_factory=list, description="關鍵字陣列")
    categoryId: Optional[str] = Field(default=None, description="分類 ID", alias="categoryId")
    cliType: str = Field(default="claude-code", description="CLI 類型", alias="cliType")
    status: str = Field(default="draft", description="模板狀態")
    documentation: Optional[str] = Field(default=None, description="文檔")
    claudeMd: Optional[str] = Field(default=None, description="Claude.md 內容", alias="claudeMd")
    isActive: bool = Field(default=True, description="是否啟用", alias="isActive")
    storage_path: Optional[str] = Field(default=None, description="儲存路徑", alias="storagePath")
    initCommands: Optional[str] = Field(default=None, description="初始化指令", alias="initCommands")

    # 配置數據
    mcpServers: List[TemplateMcpServer] = Field(default_factory=list, description="MCP 伺服器", alias="mcpServers")
    slashCommands: List[TemplateSlashCommand] = Field(default_factory=list, description="Slash 命令", alias="slashCommands")
    hooks: List[TemplateHook] = Field(default_factory=list, description="Hooks", alias="hooks")
    subAgents: List[TemplateSubAgent] = Field(default_factory=list, description="SubAgents", alias="subAgents")
    outputStyles: List[TemplateOutputStyle] = Field(default_factory=list, description="輸出樣式", alias="outputStyles")
    scripts: List[TemplateFileNode] = Field(default_factory=list, description="腳本", alias="scripts")
    skills: List[TemplateFileNode] = Field(default_factory=list, description="技能", alias="skills")

    model_config = {"from_attributes": True, "populate_by_name": True}


class TemplateListResponse(BaseModel):
    """模板列表回應"""

    items: List[Template]
    total: int
    page: Optional[int] = Field(default=None, description="當前頁碼")
    limit: Optional[int] = Field(default=None, description="每頁數量")
    total_pages: Optional[int] = Field(default=None, description="總頁數", alias="totalPages")

    model_config = {"populate_by_name": True}


class TemplateFeatureListResponse(BaseModel):
    """依 CLI 類型回傳可用功能鍵列表"""

    items: list[str]


class TemplateCategory(BaseModel):
    """模板分類"""

    id: str = Field(description="分類 ID")
    name: str = Field(description="分類名稱")
    description: Optional[str] = Field(default=None, description="分類描述")
    icon: Optional[str] = Field(default=None, description="圖示名稱")
    sortOrder: int = Field(default=0, description="排序順序", alias="sortOrder")
    isActive: bool = Field(default=True, description="是否啟用", alias="isActive")

    model_config = {"from_attributes": True, "populate_by_name": True}


class TemplateCategoryListResponse(BaseModel):
    """模板分類列表回應"""

    items: List[TemplateCategory]


# ============ Feature 索引相關模型 ============

class TemplateFeatureInfo(BaseModel):
    """模板 Feature 資訊"""

    templateId: str = Field(description="模板 ID", alias="templateId")
    features: List[str] = Field(description="Feature 列表")
    indexedAt: Optional[str] = Field(default=None, description="索引時間", alias="indexedAt")

    model_config = {"populate_by_name": True}


class FeatureStatItem(BaseModel):
    """單個 Feature 統計資訊"""

    name: str = Field(description="Feature 名稱")
    count: int = Field(description="擁有此 Feature 的模板數量")
    description: Optional[str] = Field(default=None, description="Feature 描述")


class FeatureStatsResponse(BaseModel):
    """Feature 統計回應"""

    stats: Dict[str, FeatureStatItem] = Field(description="Feature 統計資訊")
