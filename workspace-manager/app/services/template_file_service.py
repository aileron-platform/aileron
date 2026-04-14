"""模板檔案管理服務 - 重構版本

使用統一的檔案管理 API 結構，將 base_path 改為 scope
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_management import (
    FileNode,
    FileTreeResponse,
    FileContentResponse,
    FileOperationResponse,
    BatchOperationResponse,
    FileError,
    FileManagementException,
    FileNotFoundException,
    FileAlreadyExistsException,
    InvalidScopeException,
    InvalidPathException,
    FileTooLargeException,
    DirectoryNotEmptyException,
)
from app.core.file_management import (
    FileSearchRequest,
    FileSearchResponse,
    FileSearchResult,
)
from app.models import (
    FileUploadResponse,
    UploadedFileInfo,
)
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class TemplateFileService(TemplateBaseService):
    """處理模板的檔案系統操作（使用統一的 scope 機制）
    
    Scope 定義：
    - skills: 模板的 skills 目錄
    - scripts: 模板的 scripts 目錄
    """

    # 有效的 scope 值
    VALID_SCOPES = {"skills", "scripts"}

    # 跳過的目錄
    SKIP_DIRECTORIES = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        ".next", "dist", "build", ".cache", ".pytest_cache"
    }

    # 最大檔案大小（10MB）
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 上傳相關常數
    MAX_UPLOAD_FILES = 50
    ALLOWED_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
        ".md", ".txt", ".sh", ".bash", ".zsh", ".fish",
        ".html", ".css", ".scss", ".sass", ".less",
        ".sql", ".graphql", ".proto", ".toml", ".ini", ".cfg",
        ".xml", ".csv", ".env", ".gitignore", ".dockerignore",
        ".vue", ".svelte", ".astro", ".go", ".rs", ".java", ".kt",
        ".swift", ".rb", ".php", ".c", ".cpp", ".h", ".hpp"
    }

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def _validate_scope(self, scope: Optional[str]) -> str:
        """驗證並返回有效的 scope
        
        Args:
            scope: 範圍識別
            
        Returns:
            有效的 scope
            
        Raises:
            InvalidScopeException: 無效的 scope
        """
        if not scope:
            scope = "scripts"  # 預設為 scripts
        
        if scope not in self.VALID_SCOPES:
            raise InvalidScopeException(f"Invalid scope: {scope}. Must be 'skills' or 'scripts'")
        
        return scope

    def _validate_path(self, path: str) -> str:
        """驗證路徑安全性
        
        Args:
            path: 相對路徑
            
        Returns:
            驗證後的路徑
            
        Raises:
            InvalidPathException: 無效的路徑
        """
        if not path:
            return ""
        
        # 移除開頭的斜線
        path = path.lstrip("/")
        
        # 檢查路徑穿越
        if ".." in path or path.startswith("/"):
            raise InvalidPathException(path, "Path traversal detected")
        
        return path

    def _resolve_path(self, template_id: str, scope: str, relative_path: str) -> Path:
        """解析完整的檔案系統路徑
        
        Args:
            template_id: 模板 ID
            scope: 範圍識別
            relative_path: 相對路徑
            
        Returns:
            完整的檔案系統路徑
        """
        template_dir = self._get_template_dir(template_id)
        scope_dir = template_dir / scope
        
        if not relative_path or relative_path == "/":
            return scope_dir
        
        validated_path = self._validate_path(relative_path)
        return scope_dir / validated_path

    def _scan_directory(
        self,
        directory: Path,
        base_path: Path,
        include_hidden: bool = False,
        max_depth: int = 1,
        current_depth: int = 0
    ) -> List[FileNode]:
        """掃描目錄並建立檔案樹
        
        Args:
            directory: 要掃描的目錄
            base_path: 基礎路徑（用於計算相對路徑）
            include_hidden: 是否包含隱藏檔
            max_depth: 最大深度
            current_depth: 當前深度
            
        Returns:
            檔案節點列表
        """
        if not directory.exists() or not directory.is_dir():
            return []
        
        nodes = []
        
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for entry in entries:
                # 跳過隱藏檔
                if not include_hidden and entry.name.startswith("."):
                    continue
                
                # 跳過特定目錄
                if entry.is_dir() and entry.name in self.SKIP_DIRECTORIES:
                    continue
                
                # 計算相對路徑
                try:
                    rel_path = entry.relative_to(base_path)
                    path_str = "/" + str(rel_path).replace("\\", "/")
                except ValueError:
                    continue
                
                # 取得檔案資訊
                stat = entry.stat()
                updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                
                # 建立節點
                node = FileNode(
                    id=path_str,
                    name=entry.name,
                    path=path_str,
                    type="directory" if entry.is_dir() else "file",
                    scope=None,  # Template files 不使用 scope 在節點中
                    size=stat.st_size if entry.is_file() else 0,
                    updatedAt=updated_at,
                    depth=current_depth,
                    children=[],
                    hasChildren=False
                )
                
                # 如果是目錄且未達最大深度，遞迴掃描
                if entry.is_dir():
                    if current_depth < max_depth:
                        node.children = self._scan_directory(
                            entry,
                            base_path,
                            include_hidden,
                            max_depth,
                            current_depth + 1
                        )
                    node.hasChildren = any(entry.iterdir()) if entry.is_dir() else False
                
                nodes.append(node)
        
        except PermissionError:
            logger.warning(f"Permission denied accessing directory: {directory}")
        
        return nodes

    def get_tree(
        self,
        template_id: str,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: int = 1
    ) -> FileTreeResponse:
        """取得檔案樹
        
        Args:
            template_id: 模板 ID
            path: 目標路徑
            scope: 範圍識別 (skills/scripts)
            include_hidden: 是否包含隱藏檔
            max_depth: 最大深度
            
        Returns:
            檔案樹回應
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")
        
        # 驗證 scope
        scope = self._validate_scope(scope)
        
        # 解析路徑
        fs_path = self._resolve_path(template_id, scope, path)
        
        # 確保目錄存在
        if not fs_path.exists():
            fs_path.mkdir(parents=True, exist_ok=True)
            return FileTreeResponse(
                path=path,
                scope=scope,
                nodes=[],
                total=0
            )
        
        # 掃描目錄
        base_path = self._get_template_dir(template_id) / scope
        nodes = self._scan_directory(fs_path, base_path, include_hidden, max_depth, 0)
        
        return FileTreeResponse(
            path=path,
            scope=scope,
            nodes=nodes,
            total=len(nodes)
        )

    def read_file(
        self,
        template_id: str,
        path: str,
        scope: Optional[str] = None
    ) -> FileContentResponse:
        """讀取檔案內容
        
        Args:
            template_id: 模板 ID
            path: 檔案路徑
            scope: 範圍識別
            
        Returns:
            檔案內容回應
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")
        
        # 驗證 scope
        scope = self._validate_scope(scope)
        
        # 解析路徑
        fs_path = self._resolve_path(template_id, scope, path)
        
        if not fs_path.exists():
            raise FileNotFoundException(path, scope)
        
        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")
        
        # 檢查檔案大小
        file_size = fs_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, file_size, self.MAX_FILE_SIZE)
        
        # 讀取內容
        try:
            content = fs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # 如果不是 UTF-8，嘗試其他編碼
            content = fs_path.read_text(encoding="latin-1")
        
        # 計算版本 ID 和內容雜湊
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        version_id = content_hash[:16]
        
        updated_at = datetime.fromtimestamp(fs_path.stat().st_mtime, tz=timezone.utc).isoformat()
        
        return FileContentResponse(
            path=path,
            scope=scope,
            content=content,
            size=file_size,
            updatedAt=updated_at,
            versionId=version_id,
            contentHash=content_hash
        )

    def write_file(
        self,
        template_id: str,
        path: str,
        content: str,
        scope: Optional[str] = None,
        expected_version_id: Optional[str] = None
    ) -> Dict:
        """寫入檔案內容

        Args:
            template_id: 模板 ID
            path: 檔案路徑
            content: 檔案內容
            scope: 範圍識別
            expected_version_id: 預期版本ID（衝突檢測）

        Returns:
            操作結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析路徑
        fs_path = self._resolve_path(template_id, scope, path)

        # 檢查檔案大小
        content_size = len(content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, content_size, self.MAX_FILE_SIZE)

        # 如果檔案存在且提供了 expected_version_id，檢查版本
        if fs_path.exists() and expected_version_id:
            current_content = fs_path.read_text(encoding="utf-8")
            current_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
            current_version = current_hash[:16]

            if current_version != expected_version_id:
                from app.core.file_management.exceptions import ContentConflictException
                raise ContentConflictException(path, expected_version_id, current_version)

        # 確保父目錄存在
        fs_path.parent.mkdir(parents=True, exist_ok=True)

        # 寫入檔案
        fs_path.write_text(content, encoding="utf-8")

        # 計算新的版本 ID
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        version_id = content_hash[:16]

        updated_at = datetime.now(timezone.utc).isoformat()

        return {
            "updatedAt": updated_at,
            "versionId": version_id,
            "size": content_size
        }

    def create_entry(
        self,
        template_id: str,
        path: str,
        entry_type: str,
        scope: Optional[str] = None,
        content: Optional[str] = ""
    ) -> Dict:
        """建立檔案或目錄

        Args:
            template_id: 模板 ID
            path: 路徑
            entry_type: 類型 (file/directory)
            scope: 範圍識別
            content: 檔案內容（僅檔案）

        Returns:
            操作結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析路徑
        fs_path = self._resolve_path(template_id, scope, path)

        if fs_path.exists():
            raise FileAlreadyExistsException(path, scope)

        created_at = datetime.now(timezone.utc).isoformat()

        if entry_type == "directory":
            fs_path.mkdir(parents=True, exist_ok=True)
            return {
                "createdAt": created_at,
                "type": "directory"
            }
        else:  # file
            # 確保父目錄存在
            fs_path.parent.mkdir(parents=True, exist_ok=True)

            # 寫入內容
            fs_path.write_text(content or "", encoding="utf-8")

            return {
                "createdAt": created_at,
                "type": "file",
                "size": len((content or "").encode("utf-8"))
            }

    def delete_entry(
        self,
        template_id: str,
        path: str,
        scope: Optional[str] = None,
        recursive: bool = False
    ) -> Dict:
        """刪除檔案或目錄

        Args:
            template_id: 模板 ID
            path: 路徑
            scope: 範圍識別
            recursive: 是否遞迴刪除

        Returns:
            操作結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析路徑
        fs_path = self._resolve_path(template_id, scope, path)

        if not fs_path.exists():
            raise FileNotFoundException(path, scope)

        entry_type = "directory" if fs_path.is_dir() else "file"

        if fs_path.is_dir():
            if not recursive and any(fs_path.iterdir()):
                raise DirectoryNotEmptyException(path)
            shutil.rmtree(fs_path)
        else:
            fs_path.unlink()

        return {"type": entry_type}

    def copy_entry(
        self,
        template_id: str,
        source_path: str,
        dest_path: str,
        scope: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict:
        """複製檔案或目錄

        Args:
            template_id: 模板 ID
            source_path: 來源路徑
            dest_path: 目標路徑
            scope: 範圍識別
            overwrite: 是否覆蓋

        Returns:
            操作結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析路徑
        source_fs_path = self._resolve_path(template_id, scope, source_path)
        dest_fs_path = self._resolve_path(template_id, scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, scope)

        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, scope)

        # 確保目標父目錄存在
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # 複製
        if source_fs_path.is_dir():
            if dest_fs_path.exists() and overwrite:
                shutil.rmtree(dest_fs_path)
            shutil.copytree(str(source_fs_path), str(dest_fs_path))
        else:
            shutil.copy2(str(source_fs_path), str(dest_fs_path))

        return {
            "type": "directory" if source_fs_path.is_dir() else "file",
            "size": dest_fs_path.stat().st_size if dest_fs_path.is_file() else 0
        }

    def move_entry(
        self,
        template_id: str,
        source_path: str,
        dest_path: str,
        scope: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict:
        """移動檔案或目錄

        Args:
            template_id: 模板 ID
            source_path: 來源路徑
            dest_path: 目標路徑
            scope: 範圍識別
            overwrite: 是否覆蓋

        Returns:
            操作結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析路徑
        source_fs_path = self._resolve_path(template_id, scope, source_path)
        dest_fs_path = self._resolve_path(template_id, scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, scope)

        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, scope)

        # 確保目標父目錄存在
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # 移動
        if dest_fs_path.exists() and overwrite:
            if dest_fs_path.is_dir():
                shutil.rmtree(dest_fs_path)
            else:
                dest_fs_path.unlink()

        shutil.move(str(source_fs_path), str(dest_fs_path))

        return {
            "type": "directory" if dest_fs_path.is_dir() else "file",
            "size": dest_fs_path.stat().st_size if dest_fs_path.is_file() else 0
        }

    def batch_delete(
        self,
        template_id: str,
        paths: List[str],
        scope: Optional[str] = None,
        recursive: bool = False
    ) -> BatchOperationResponse:
        """批次刪除檔案

        Args:
            template_id: 模板 ID
            paths: 路徑列表
            scope: 範圍識別
            recursive: 是否遞迴刪除

        Returns:
            批次操作回應
        """
        results = []
        success_count = 0

        for path in paths:
            try:
                self.delete_entry(template_id, path, scope, recursive)
                results.append({
                    "path": path,
                    "success": True
                })
                success_count += 1
            except Exception as e:
                results.append({
                    "path": path,
                    "success": False,
                    "error": str(e)
                })

        return BatchOperationResponse(
            success=success_count == len(paths),
            total=len(paths),
            succeeded=success_count,
            failed=len(paths) - success_count,
            results=results
        )

    def _validate_filename(self, filename: str) -> bool:
        """驗證檔案名稱

        Args:
            filename: 檔案名稱

        Returns:
            是否有效
        """
        if not filename:
            return False

        # 不允許路徑分隔符
        if "/" in filename or "\\" in filename:
            return False

        # 不允許特殊字元
        if re.search(r'[<>:"|?*]', filename):
            return False

        # 不允許以點開頭（隱藏檔）
        if filename.startswith("."):
            return False

        return True

    async def upload_files(
        self,
        template_id: str,
        target_path: str,
        files: List[UploadFile],
        overwrite: bool = False,
        scope: Optional[str] = None
    ) -> FileUploadResponse:
        """上傳檔案

        Args:
            template_id: 模板 ID
            target_path: 目標目錄路徑
            files: 上傳的檔案列表
            overwrite: 是否覆蓋
            scope: 範圍識別

        Returns:
            上傳結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 檢查檔案數量
        if len(files) > self.MAX_UPLOAD_FILES:
            return FileUploadResponse(
                success=False,
                uploaded=[],
                total=len(files),
                succeeded=0,
                failed=len(files),
                message=f"Too many files (max {self.MAX_UPLOAD_FILES})"
            )

        # 解析目標目錄
        target_dir = self._resolve_path(template_id, scope, target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        results = []
        succeeded = 0
        failed = 0

        for upload_file in files:
            try:
                # 驗證檔案名稱
                if not self._validate_filename(upload_file.filename):
                    results.append(UploadedFileInfo(
                        filename=upload_file.filename,
                        path="",
                        size=0,
                        success=False,
                        error="Invalid filename"
                    ))
                    failed += 1
                    continue

                # 檢查副檔名
                file_ext = Path(upload_file.filename).suffix.lower()
                if file_ext and file_ext not in self.ALLOWED_EXTENSIONS:
                    results.append(UploadedFileInfo(
                        filename=upload_file.filename,
                        path="",
                        size=0,
                        success=False,
                        error=f"File extension {file_ext} not allowed"
                    ))
                    failed += 1
                    continue

                file_path = target_dir / upload_file.filename

                # 檢查是否已存在
                if file_path.exists() and not overwrite:
                    results.append(UploadedFileInfo(
                        filename=upload_file.filename,
                        path="",
                        size=0,
                        success=False,
                        error="File already exists"
                    ))
                    failed += 1
                    continue

                # 讀取並檢查大小
                content = await upload_file.read()
                if len(content) > self.MAX_FILE_SIZE:
                    results.append(UploadedFileInfo(
                        filename=upload_file.filename,
                        path="",
                        size=len(content),
                        success=False,
                        error=f"File too large (max {self.MAX_FILE_SIZE / 1024 / 1024}MB)"
                    ))
                    failed += 1
                    continue

                # 寫入檔案
                file_path.write_bytes(content)

                # 計算相對路徑
                scope_dir = self._get_template_dir(template_id) / scope
                relative_path = "/" + str(file_path.relative_to(scope_dir)).replace("\\", "/")

                results.append(UploadedFileInfo(
                    filename=upload_file.filename,
                    path=relative_path,
                    size=len(content),
                    success=True
                ))
                succeeded += 1

            except Exception as e:
                logger.error(f"上傳檔案失敗 {upload_file.filename}: {e}")
                results.append(UploadedFileInfo(
                    filename=upload_file.filename,
                    path="",
                    size=0,
                    success=False,
                    error=str(e)
                ))
                failed += 1

        return FileUploadResponse(
            success=failed == 0,
            uploaded=results,
            total=len(files),
            succeeded=succeeded,
            failed=failed,
            message=f"Uploaded {succeeded}/{len(files)} files successfully"
        )

    def search_files(
        self,
        template_id: str,
        request: FileSearchRequest,
        scope: Optional[str] = None
    ) -> FileSearchResponse:
        """搜尋檔案

        Args:
            template_id: 模板 ID
            request: 搜尋請求
            scope: 範圍識別

        Returns:
            搜尋結果
        """
        # 驗證模板
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # 驗證 scope
        scope = self._validate_scope(scope)

        # 解析搜尋目錄
        search_dir = self._get_template_dir(template_id) / scope

        if not search_dir.exists():
            return FileSearchResponse(
                query=request.query,
                path="/",
                scope=scope,
                results=[],
                total=0
            )

        try:
            results = []
            query_lower = request.query.lower()

            for item in search_dir.rglob("*"):
                if len(results) >= request.maxResults:
                    break

                # 跳過特定目錄
                if any(skip_dir in item.parts for skip_dir in self.SKIP_DIRECTORIES):
                    continue

                # 計算相對路徑
                relative_path = "/" + str(item.relative_to(search_dir)).replace("\\", "/")

                # 檔案名稱匹配
                name_match = query_lower in item.name.lower()

                # 檔案類型篩選
                if request.fileTypes and item.is_file():
                    if item.suffix not in request.fileTypes:
                        continue

                content_matches = []
                if request.searchContent and item.is_file():
                    try:
                        if item.stat().st_size < self.MAX_FILE_SIZE:
                            content = item.read_text(encoding="utf-8")
                            if query_lower in content.lower():
                                # 提取匹配的行
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if query_lower in line.lower():
                                        content_matches.append(f"Line {i+1}: {line.strip()[:100]}")
                                        if len(content_matches) >= 3:
                                            break
                    except Exception as e:
                        logger.debug(f"無法讀取檔案內容 {item}: {e}")

                if name_match or content_matches:
                    stat_info = item.stat()
                    results.append(FileSearchResult(
                        path=relative_path,
                        name=item.name,
                        type="directory" if item.is_dir() else "file",
                        size=stat_info.st_size if item.is_file() else 0,
                        updatedAt=datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).isoformat(),
                        matches=content_matches if content_matches else None
                    ))

            return FileSearchResponse(
                query=request.query,
                path="/",
                scope=scope,
                results=results,
                total=len(results)
            )
        except Exception as e:
            logger.error(f"搜尋失敗: {e}")
            raise FileManagementException(
                code="SEARCH_FAILED",
                message=f"Search failed: {str(e)}",
                status_code=500
            )
    def load_files(self, template_id: str) -> List:
        """載入檔案結構 (scripts 目錄)"""
        from app.models.template import TemplateFileNode

        files_dir = self._get_template_dir(template_id) / "scripts"
        if not files_dir.exists():
            return []

        def build_file_tree(path: Path, parent_id: str = "root") -> List:
            nodes = []
            try:
                for item in path.iterdir():
                    node_id = f"{parent_id}/{item.name}"
                    if item.is_file():
                        nodes.append(TemplateFileNode(
                            id=node_id,
                            name=item.name,
                            path=str(item.relative_to(files_dir)),
                            type="file",
                            size=item.stat().st_size,
                            content=item.read_text(encoding="utf-8", errors="ignore") if item.stat().st_size < 1024 * 1024 else None,  # 限制 1MB
                        ))
                    elif item.is_dir():
                        children = build_file_tree(item, node_id)
                        nodes.append(TemplateFileNode(
                            id=node_id,
                            name=item.name,
                            path=str(item.relative_to(files_dir)),
                            type="directory",
                            children=children,
                        ))
            except Exception as e:
                logger.error(f"載入檔案節點失敗 {path}: {e}")

            return nodes

        return build_file_tree(files_dir)

    def load_skills(self, template_id: str) -> List:
        """載入檔案結構 (skills 目錄)"""
        from app.models.template import TemplateFileNode

        skills_dir = self._get_template_dir(template_id) / "skills"
        if not skills_dir.exists():
            return []

        def build_file_tree(path: Path, parent_id: str = "root") -> List:
            nodes = []
            try:
                for item in path.iterdir():
                    node_id = f"{parent_id}/{item.name}"
                    if item.is_file():
                        nodes.append(TemplateFileNode(
                            id=node_id,
                            name=item.name,
                            path=str(item.relative_to(skills_dir)),
                            type="file",
                            size=item.stat().st_size,
                            content=item.read_text(encoding="utf-8", errors="ignore") if item.stat().st_size < 1024 * 1024 else None,  # 限制 1MB
                        ))
                    elif item.is_dir():
                        children = build_file_tree(item, node_id)
                        nodes.append(TemplateFileNode(
                            id=node_id,
                            name=item.name,
                            path=str(item.relative_to(skills_dir)),
                            type="directory",
                            children=children,
                        ))
            except Exception as e:
                logger.error(f"載入檔案節點失敗 {path}: {e}")

            return nodes

        return build_file_tree(skills_dir)


__all__ = ["TemplateFileService"]

