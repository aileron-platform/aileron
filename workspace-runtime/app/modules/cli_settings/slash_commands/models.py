"""CLI Slash Commands 資料模型"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .config import SlashCommandScope, DocumentFormat


class CliSlashCommandDocumentSummary(BaseModel):
    """Slash Command 檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    namespace: str | None = Field(None, description="命名空間")
    description: str | None = Field(None, description="指令描述")
    scope: SlashCommandScope = Field(..., description="檔案範圍")
    size: str = Field(..., description="檔案大小")
    format: DocumentFormat = Field(..., description="文件格式 (markdown / toml)")

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentDetail(CliSlashCommandDocumentSummary):
    """Slash Command 完整內容"""

    content: str = Field(..., description="檔案原始內容")


class CliSlashCommandScopeGroup(BaseModel):
    """同一範圍的命令清單"""

    scope: SlashCommandScope = Field(..., description="檔案範圍")
    documents: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="檔案列表"
    )


class CliSlashCommandScopesResponse(BaseModel):
    """列出所有範圍的命令"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[CliSlashCommandScopeGroup] = Field(
        default_factory=list, description="依範圍分類的命令"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandScopeResponse(BaseModel):
    """單一範圍命令列表"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="命令範圍")
    documents: List[CliSlashCommandDocumentSummary] = Field(
        default_factory=list, description="檔案列表"
    )

    model_config = {"populate_by_name": True}


class CliSlashCommandDocumentResponse(BaseModel):
    """單一檔案內容"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="檔案範圍")
    document: CliSlashCommandDocumentDetail = Field(..., description="檔案內容")

    model_config = {"populate_by_name": True}


class CliSlashCommandCreateRequest(BaseModel):
    """建立 Slash Command 請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    content: str = Field(..., description="檔案內容")
    namespace: str | None = Field(None, description="命名空間")

    model_config = {"populate_by_name": True}


class CliSlashCommandUpdateRequest(BaseModel):
    """更新 Slash Command 請求"""

    content: str = Field(..., description="檔案內容")
    namespace: str | None = Field(None, description="命名空間")


class CliSlashCommandDeleteResponse(BaseModel):
    """刪除命令的回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: SlashCommandScope = Field(..., description="命令範圍")
    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    deleted: bool = Field(True, description="刪除狀態")

    model_config = {"populate_by_name": True}
