"""模板安裝相關模型"""

from typing import Optional

from pydantic import BaseModel, Field


class TemplateInstallRequest(BaseModel):
    """模板安裝請求"""

    template_id: str = Field(..., alias="templateId", description="模板 ID")
    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")

    model_config = {"populate_by_name": True}


class TemplateInstallItemResult(BaseModel):
    """單項安裝結果"""

    success: bool = Field(..., description="是否成功")
    created: int = Field(default=0, description="新建數量")
    updated: int = Field(default=0, description="更新數量")
    failed: int = Field(default=0, description="失敗數量")


class TemplateInstallResults(BaseModel):
    """模板安裝結果詳情"""

    claudeMd: Optional[TemplateInstallItemResult] = Field(default=None, alias="claudeMd")
    slashCommands: Optional[TemplateInstallItemResult] = Field(default=None, alias="slashCommands")
    subagents: Optional[TemplateInstallItemResult] = Field(default=None, alias="subagents")
    mcp: Optional[TemplateInstallItemResult] = Field(default=None, alias="mcp")
    hooks: Optional[TemplateInstallItemResult] = Field(default=None, alias="hooks")
    scripts: Optional[TemplateInstallItemResult] = Field(default=None, alias="scripts")
    skills: Optional[TemplateInstallItemResult] = Field(default=None, alias="skills")

    model_config = {"populate_by_name": True}


class TemplateInstallResponse(BaseModel):
    """模板安裝回應"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息")
    templateId: str = Field(..., alias="templateId", description="模板 ID")
    templateName: str = Field(..., alias="templateName", description="模板名稱")
    workspaceId: str = Field(..., alias="workspaceId", description="Workspace ID")
    results: Optional[TemplateInstallResults] = Field(default=None, description="安裝結果詳情")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

    model_config = {"populate_by_name": True}
