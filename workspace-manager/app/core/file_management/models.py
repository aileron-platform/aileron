"""統一的檔案管理資料模型"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# ============ 檔案樹節點 ============

class FileNode(BaseModel):
    """統一的檔案樹節點"""
    id: str = Field(description="節點唯一識別（通常為路徑）")
    name: str = Field(description="節點名稱")
    path: str = Field(description="相對路徑（不含 scope 前綴）")
    type: Literal["file", "directory"] = Field(description="節點類型")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    size: int = Field(default=0, description="檔案大小（bytes）")
    updatedAt: str = Field(description="最後修改時間（ISO8601）")
    depth: int = Field(default=0, description="樹中的層級")
    children: List["FileNode"] = Field(default_factory=list, description="子節點")
    hasChildren: bool = Field(default=False, description="是否有子節點")
    
    # 可選的擴展欄位
    extension: Optional[str] = Field(default=None, description="副檔名")
    fileType: Optional[str] = Field(default=None, description="檔案類型")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="額外元數據")


# ============ 請求模型 ============

class FileTreeRequest(BaseModel):
    """檔案樹請求"""
    path: str = Field(default="/", description="目標路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    includeHidden: bool = Field(default=False, description="是否包含隱藏檔")
    maxDepth: int = Field(default=1, ge=1, le=3, description="最大深度")


class FileContentRequest(BaseModel):
    """讀取檔案請求"""
    path: str = Field(description="檔案路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")


class FileWriteRequest(BaseModel):
    """寫入檔案請求"""
    path: str = Field(description="檔案路徑")
    content: str = Field(description="檔案內容")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    expectedVersionId: Optional[str] = Field(default=None, description="預期版本ID（衝突檢測）")


class FileCreateRequest(BaseModel):
    """建立檔案或目錄請求"""
    path: str = Field(description="路徑")
    type: Literal["file", "directory"] = Field(description="類型")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    content: Optional[str] = Field(default="", description="檔案內容（僅檔案）")


class FileDeleteRequest(BaseModel):
    """刪除請求"""
    path: str = Field(description="路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    recursive: bool = Field(default=False, description="是否遞迴刪除目錄")


class FileCopyRequest(BaseModel):
    """複製請求"""
    sourcePath: str = Field(description="源路徑")
    destPath: str = Field(description="目標路徑")
    sourceScope: Optional[str] = Field(default=None, description="源範圍")
    destScope: Optional[str] = Field(default=None, description="目標範圍")
    overwrite: bool = Field(default=False, description="是否覆蓋")


class FileMoveRequest(BaseModel):
    """移動請求"""
    sourcePath: str = Field(description="源路徑")
    destPath: str = Field(description="目標路徑")
    sourceScope: Optional[str] = Field(default=None, description="源範圍")
    destScope: Optional[str] = Field(default=None, description="目標範圍")
    overwrite: bool = Field(default=False, description="是否覆蓋")


class BatchDeleteRequest(BaseModel):
    """批次刪除請求"""
    paths: List[str] = Field(description="路徑列表")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    recursive: bool = Field(default=False, description="是否遞迴刪除目錄")


class BatchWriteRequest(BaseModel):
    """批次寫入請求"""
    files: List[Dict[str, str]] = Field(description="檔案列表 [{'path': '...', 'content': '...'}, ...]")
    scope: Optional[str] = Field(default=None, description="範圍識別")


# ============ 回應模型 ============

class FileTreeResponse(BaseModel):
    """檔案樹回應"""
    path: str = Field(description="路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    nodes: List[FileNode] = Field(description="節點列表")
    total: int = Field(description="總節點數")


class FileContentResponse(BaseModel):
    """檔案內容回應"""
    path: str = Field(description="檔案路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小")
    updatedAt: str = Field(description="最後修改時間")
    versionId: Optional[str] = Field(default=None, description="版本ID")
    contentHash: Optional[str] = Field(default=None, description="內容雜湊")


class FileOperationResponse(BaseModel):
    """檔案操作回應"""
    success: bool = Field(description="是否成功")
    path: Optional[str] = Field(default=None, description="路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    message: Optional[str] = Field(default=None, description="訊息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="額外資料")


class BatchOperationResponse(BaseModel):
    """批次操作回應"""
    total: int = Field(description="總數")
    succeeded: int = Field(description="成功數")
    failed: int = Field(description="失敗數")
    results: List[Dict[str, Any]] = Field(description="詳細結果")


class FileError(BaseModel):
    """檔案錯誤"""
    code: str = Field(description="錯誤代碼")
    message: str = Field(description="錯誤訊息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="錯誤細節")


class FileSearchRequest(BaseModel):
    """檔案搜尋請求"""
    query: str = Field(description="搜尋關鍵字")
    path: str = Field(default="/", description="搜尋路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    fileTypes: Optional[List[str]] = Field(default=None, description="檔案類型過濾")
    searchContent: bool = Field(default=False, description="是否搜尋檔案內容")
    caseSensitive: bool = Field(default=False, description="是否區分大小寫")
    maxResults: int = Field(default=100, ge=1, le=1000, description="最大結果數")


class FileSearchResult(BaseModel):
    """檔案搜尋結果項"""
    path: str = Field(description="檔案路徑")
    name: str = Field(description="檔案名稱")
    type: Literal["file", "directory"] = Field(description="類型")
    size: int = Field(description="檔案大小")
    updatedAt: str = Field(description="最後修改時間")
    matches: Optional[List[str]] = Field(default=None, description="匹配的內容片段")


class FileSearchResponse(BaseModel):
    """檔案搜尋回應"""
    query: str = Field(description="搜尋關鍵字")
    path: str = Field(description="搜尋路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    results: List[FileSearchResult] = Field(description="搜尋結果")
    total: int = Field(description="總結果數")


class FileUploadResult(BaseModel):
    """檔案上傳結果項"""
    filename: str = Field(description="檔案名稱")
    path: str = Field(description="儲存路徑")
    size: int = Field(description="檔案大小")
    success: bool = Field(description="是否成功")
    message: Optional[str] = Field(default=None, description="訊息")


class FileUploadResponse(BaseModel):
    """檔案上傳回應"""
    total: int = Field(description="總檔案數")
    succeeded: int = Field(description="成功數")
    failed: int = Field(description="失敗數")
    results: List[FileUploadResult] = Field(description="上傳結果")

