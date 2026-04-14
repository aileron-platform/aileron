"""統一的檔案管理資料模型"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


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
    encoding: Optional[Literal["utf-8", "base64"]] = Field(default="utf-8", description="內容編碼方式")


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

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "nodes" not in value:
            data = value.get("data") or {}
            return {
                "path": data.get("path", "/"),
                "scope": data.get("scope"),
                "nodes": data.get("children", []),
                "total": data.get("total", len(data.get("children", []))),
            }
        return value


class FileContentResponse(BaseModel):
    """檔案內容回應"""
    path: str = Field(description="檔案路徑")
    scope: Optional[str] = Field(default=None, description="範圍識別")
    content: str = Field(description="檔案內容")
    size: int = Field(description="檔案大小")
    updatedAt: str = Field(description="最後修改時間")
    versionId: Optional[str] = Field(default=None, description="版本ID")
    contentHash: Optional[str] = Field(default=None, description="內容雜湊")

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "content" not in value:
            data = value.get("data") or {}
            return {
                "path": data.get("path", ""),
                "scope": data.get("scope"),
                "content": data.get("content", ""),
                "size": data.get("size", len(data.get("content", ""))),
                "updatedAt": data.get("updatedAt", ""),
                "versionId": data.get("versionId"),
                "contentHash": data.get("contentHash"),
            }
        return value


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

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "results" not in value:
            data = value.get("data") or {}
            results = data.get("results", [])
            succeeded = sum(1 for item in results if item.get("success"))
            failed = len(results) - succeeded
            return {
                "total": len(results),
                "succeeded": succeeded,
                "failed": failed,
                "results": results,
            }
        return value


class FileError(BaseModel):
    """檔案錯誤"""
    code: str = Field(description="錯誤代碼")
    message: str = Field(description="錯誤訊息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="錯誤細節")

class UploadResult(BaseModel):
    """單一檔案上傳結果"""
    path: str = Field(description="檔案儲存路徑")
    size: int = Field(description="檔案大小")
    lastModified: str = Field(description="最後修改時間")
    type: Literal["file", "directory"] = Field(default="file", description="結果類型")


class UploadResponse(BaseModel):
    """上傳檔案回應"""
    uploaded: List[UploadResult] = Field(description="成功上傳清單")
    extracted: List[UploadResult] = Field(default_factory=list, description="成功解壓清單")
    skipped: List[str] = Field(default_factory=list, description="略過的檔案")


class ExtractArchiveRequest(BaseModel):
    """解壓縮請求"""
    archivePath: str = Field(description="既有 ZIP 檔案路徑")
    targetPath: Optional[str] = Field(default=None, description="解壓目標目錄，預設為 ZIP 所在目錄")
    conflictStrategy: Literal["rename", "overwrite", "reject"] = Field(
        default="rename",
        description="衝突處理策略",
    )


class ExtractArchiveAcceptedResponse(BaseModel):
    """接受背景解壓請求的回應"""
    operationId: str = Field(description="背景解壓 operation ID")
    status: Literal["pending", "running"] = Field(description="目前狀態")
    message: str = Field(description="狀態訊息")
    startedAt: datetime = Field(description="建立時間")


class ExtractArchiveResult(BaseModel):
    """背景解壓結果"""
    extracted: List[UploadResult] = Field(default_factory=list, description="成功解壓的項目")
    extractedPaths: List[str] = Field(default_factory=list, description="成功解壓的路徑")


class ExtractArchiveStatusResponse(BaseModel):
    """背景解壓狀態回應"""
    operationId: str = Field(description="背景解壓 operation ID")
    status: Literal["pending", "running", "completed", "failed"] = Field(description="目前狀態")
    progress: float = Field(default=0.0, description="進度 0.0-1.0", ge=0.0, le=1.0)
    message: str = Field(description="狀態訊息")
    startedAt: datetime = Field(description="建立時間")
    completedAt: Optional[datetime] = Field(default=None, description="完成時間")
    error: Optional[str] = Field(default=None, description="失敗訊息")
    result: Optional[ExtractArchiveResult] = Field(default=None, description="成功結果")
