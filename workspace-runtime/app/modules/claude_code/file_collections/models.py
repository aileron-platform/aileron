"""File Collections 資料模型"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FileCollectionType(str, Enum):
    """檔案集合類型"""

    SKILLS = "skills"
    PLUGINS = "plugins"
    SCRIPTS = "scripts"


class FileType(str, Enum):
    """支援的檔案類型"""

    MARKDOWN = "markdown"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    YAML = "yaml"
    JSON = "json"
    PYTHON = "python"
    SHELL = "shell"
    OTHER = "other"


class FileSummary(BaseModel):
    """檔案摘要"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱")
    file_path: str = Field(..., alias="filePath", description="檔案相對路徑（不含 scope 前綴）")
    file_type: FileType = Field(..., alias="fileType", description="檔案類型")
    scope: str = Field(..., description="檔案範圍：project, user, plugin")
    size_bytes: int = Field(..., alias="sizeBytes", description="檔案大小（位元組）")
    size_label: str = Field(..., alias="sizeLabel", description="檔案大小（人類可讀）")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="更新時間")

    # Front Matter 元數據（如果是 Markdown）
    name: Optional[str] = Field(None, description="顯示名稱（來自 Front Matter）")
    description: Optional[str] = Field(None, description="描述（來自 Front Matter）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元數據")

    model_config = {"populate_by_name": True}


class FileDetail(FileSummary):
    """檔案詳細資訊"""

    content: str = Field(..., description="檔案內容")


class FileTreeNode(BaseModel):
    """檔案樹節點"""

    id: str = Field(..., description="節點唯一識別碼")
    name: str = Field(..., description="節點名稱")
    path: str = Field(..., description="節點路徑")
    type: str = Field(..., description="節點類型：file 或 directory")
    file_type: Optional[FileType] = Field(None, alias="fileType", description="檔案類型（僅檔案）")
    scope: Optional[str] = Field(None, description="檔案範圍：project, user, plugin（僅檔案）")
    children: Optional[List[FileTreeNode]] = Field(None, description="子節點（僅目錄）")
    size_bytes: Optional[int] = Field(None, alias="sizeBytes", description="檔案大小（僅檔案）")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", description="更新時間（僅檔案）")

    model_config = {"populate_by_name": True}


class FileCollectionResponse(BaseModel):
    """檔案集合回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="集合類型")
    files: List[FileSummary] = Field(..., description="檔案列表")
    tree: List[FileTreeNode] = Field(..., description="檔案樹")

    model_config = {"populate_by_name": True}


class FileResponse(BaseModel):
    """單一檔案回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="集合類型")
    file: FileDetail = Field(..., description="檔案詳細資訊")

    model_config = {"populate_by_name": True}


class FileCreateRequest(BaseModel):
    """建立檔案請求"""

    file_name: str = Field(..., alias="fileName", description="檔案名稱（可包含子目錄路徑，如 folder/file.md）")
    content: str = Field(..., description="檔案內容")
    scope: Optional[str] = Field("project", description="檔案範圍：project, user（預設為 project）")

    model_config = {"populate_by_name": True}


class FileUpdateRequest(BaseModel):
    """更新檔案請求"""

    content: str = Field(..., description="檔案內容")
    scope: Optional[str] = Field(None, description="檔案範圍：project, user（可選，用於指定要更新哪個 scope 的檔案）")


class FileMoveRequest(BaseModel):
    """移動/重新命名檔案請求"""

    source_path: str = Field(..., alias="sourcePath", description="源檔案相對路徑（不含 scope 前綴）")
    dest_path: str = Field(..., alias="destPath", description="目標檔案相對路徑（不含 scope 前綴）")

    model_config = {"populate_by_name": True}


class FileCopyRequest(BaseModel):
    """複製檔案請求"""

    source_path: str = Field(..., alias="sourcePath", description="源檔案相對路徑（不含 scope 前綴）")
    dest_path: str = Field(..., alias="destPath", description="目標檔案相對路徑（不含 scope 前綴）")

    model_config = {"populate_by_name": True}


class FileDeleteResponse(BaseModel):
    """刪除檔案回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    collection_type: FileCollectionType = Field(..., alias="collectionType", description="集合類型")
    file_path: str = Field(..., alias="filePath", description="檔案路徑")
    deleted: bool = Field(..., description="是否成功刪除")

    model_config = {"populate_by_name": True}


class PluginSkillInfo(BaseModel):
    """Plugin Skill 資訊"""

    plugin_id: str = Field(..., alias="pluginId", description="Plugin ID (格式: name@marketplace)")
    plugin_name: str = Field(..., alias="pluginName", description="Plugin 名稱")
    marketplace_name: str = Field(..., alias="marketplaceName", description="Marketplace 名稱")
    skill_name: str = Field(..., alias="skillName", description="Skill 名稱")
    skill_path: str = Field(..., alias="skillPath", description="Skill 目錄路徑")

    model_config = {"populate_by_name": True}


class PluginSkillsResponse(BaseModel):
    """Plugin Skills 列表回應"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    plugins: List[PluginSkillInfo] = Field(..., description="Plugin Skills 列表")

    model_config = {"populate_by_name": True}

