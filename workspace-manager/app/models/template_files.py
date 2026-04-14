"""模板檔案管理相關資料模型"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============ 請求模型 ============

class CreateFileRequest(BaseModel):
    """建立檔案或目錄請求"""
    path: str = Field(..., description="檔案或目錄路徑")
    type: Literal["file", "directory"] = Field(..., description="類型")
    content: Optional[str] = Field(default="", description="檔案內容(僅檔案)")
    
    model_config = {"json_schema_extra": {
        "example": {
            "path": "src/main.py",
            "type": "file",
            "content": "print('Hello World')"
        }
    }}

class UpdateFileContentRequest(BaseModel):
    """更新檔案內容請求"""
    path: str = Field(..., description="檔案路徑")
    content: str = Field(..., description="新內容")
    
    model_config = {"json_schema_extra": {
        "example": {
            "path": "src/main.py",
            "content": "print('Updated')"
        }
    }}

class RenameFileRequest(BaseModel):
    """重命名請求"""
    old_path: str = Field(..., description="原路徑")
    new_name: str = Field(..., description="新名稱")
    
    model_config = {"json_schema_extra": {
        "example": {
            "old_path": "src/old.py",
            "new_name": "new.py"
        }
    }}

class MoveFileRequest(BaseModel):
    """移動請求"""
    source_path: str = Field(..., description="來源路徑")
    target_path: str = Field(..., description="目標路徑")
    overwrite: bool = Field(default=False, description="是否覆蓋")
    
    model_config = {"json_schema_extra": {
        "example": {
            "source_path": "src/old.py",
            "target_path": "lib/new.py",
            "overwrite": False
        }
    }}

class CopyFileRequest(BaseModel):
    """複製請求"""
    source_path: str = Field(..., description="來源路徑")
    target_path: str = Field(..., description="目標路徑")
    overwrite: bool = Field(default=False, description="是否覆蓋")
    
    model_config = {"json_schema_extra": {
        "example": {
            "source_path": "src/main.py",
            "target_path": "src/main_backup.py",
            "overwrite": False
        }
    }}

class BatchDeleteRequest(BaseModel):
    """批次刪除請求"""
    paths: List[str] = Field(..., description="要刪除的路徑列表")
    recursive: bool = Field(default=False, description="是否遞迴刪除目錄")
    
    model_config = {"json_schema_extra": {
        "example": {
            "paths": ["src/temp.py", "lib/old/"],
            "recursive": True
        }
    }}

# FileSearchRequest 已移至 app.core.file_management.models

# ============ 回應模型 ============

class FileNodeInfo(BaseModel):
    """檔案節點資訊"""
    id: str = Field(description="節點 ID")
    name: str = Field(description="名稱")
    path: str = Field(description="相對路徑")
    type: Literal["file", "directory"] = Field(description="類型")
    size: Optional[int] = Field(default=None, description="檔案大小(bytes)")
    content: Optional[str] = Field(default=None, description="檔案內容")
    extension: Optional[str] = Field(default=None, description="副檔名")
    created_at: Optional[datetime] = Field(default=None, description="建立時間")
    modified_at: Optional[datetime] = Field(default=None, description="修改時間")
    children: Optional[List["FileNodeInfo"]] = Field(default=None, description="子節點")
    
    model_config = {"from_attributes": True}

class TemplateFilesResponse(BaseModel):
    """檔案樹回應"""
    success: bool = Field(description="是否成功")
    data: Optional[List[FileNodeInfo]] = Field(default=None, description="檔案樹")
    total_files: int = Field(default=0, description="總檔案數")
    total_size: int = Field(default=0, description="總大小(bytes)")
    message: Optional[str] = Field(default=None, description="訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

class FileContentResponse(BaseModel):
    """檔案內容回應"""
    success: bool = Field(description="是否成功")
    data: Optional[FileNodeInfo] = Field(default=None, description="檔案資訊")
    message: Optional[str] = Field(default=None, description="訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

class FileOperationResponse(BaseModel):
    """檔案操作回應"""
    success: bool = Field(description="是否成功")
    data: Optional[FileNodeInfo] = Field(default=None, description="操作後的檔案資訊")
    message: Optional[str] = Field(default=None, description="訊息")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

class UploadedFileInfo(BaseModel):
    """上傳檔案資訊"""
    filename: str = Field(description="檔案名稱")
    path: str = Field(description="儲存路徑")
    size: int = Field(description="檔案大小")
    success: bool = Field(description="是否成功")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

class FileUploadResponse(BaseModel):
    """檔案上傳回應"""
    success: bool = Field(description="整體是否成功")
    uploaded: List[UploadedFileInfo] = Field(default_factory=list, description="上傳結果")
    total: int = Field(description="總檔案數")
    succeeded: int = Field(description="成功數")
    failed: int = Field(description="失敗數")
    message: Optional[str] = Field(default=None, description="訊息")

class BatchOperationResult(BaseModel):
    """批次操作結果"""
    path: str = Field(description="路徑")
    success: bool = Field(description="是否成功")
    error: Optional[str] = Field(default=None, description="錯誤訊息")

class BatchOperationResponse(BaseModel):
    """批次操作回應"""
    success: bool = Field(description="整體是否成功")
    results: List[BatchOperationResult] = Field(default_factory=list, description="操作結果")
    total: int = Field(description="總數")
    succeeded: int = Field(description="成功數")
    failed: int = Field(description="失敗數")
    message: Optional[str] = Field(default=None, description="訊息")

# FileSearchResult, FileSearchResponse 已移至 app.core.file_management.models


__all__ = [
    "CreateFileRequest",
    "UpdateFileContentRequest",
    "RenameFileRequest",
    "MoveFileRequest",
    "CopyFileRequest",
    "BatchDeleteRequest",
    "FileNodeInfo",
    "TemplateFilesResponse",
    "FileContentResponse",
    "FileOperationResponse",
    "UploadedFileInfo",
    "FileUploadResponse",
    "BatchOperationResult",
    "BatchOperationResponse",
]

