"""檔案管理基礎服務抽象類"""

from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import shutil
import hashlib

from app.config.settings import get_settings
from .exceptions import (
    FileNotFoundException,
    FileAlreadyExistsException,
    ReadonlyScopeException,
    InvalidPathException,
    DirectoryNotEmptyException,
    FileTooLargeException
)


class BaseFileService(ABC):
    """檔案管理基礎服務
    
    提供統一的檔案操作介面，子類需實作 scope 相關方法
    """
    
    # 跳過的目錄（效能優化）
    SKIP_DIRECTORIES = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', '.nuxt', 'coverage', '.pytest_cache',
        'target', 'out', 'bin', 'obj', '.gradle', '.idea', '.vscode'
    }
    
    # 檔案大小限制（10MB）
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, root_path: Path):
        """初始化
        
        Args:
            root_path: 根目錄路徑
        """
        self._root_path = Path(root_path)
        self._root_path.mkdir(parents=True, exist_ok=True)
    
    # ============ 抽象方法（子類必須實作） ============
    
    @abstractmethod
    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """解析 scope 和相對路徑到實際檔案系統路徑
        
        Args:
            scope: 範圍識別（如 project, user, plugin, skills, scripts 等）
            relative_path: 相對路徑
            
        Returns:
            實際檔案系統路徑
        """
        pass
    
    @abstractmethod
    def validate_scope(self, scope: Optional[str]) -> bool:
        """驗證 scope 是否合法
        
        Args:
            scope: 範圍識別
            
        Returns:
            是否合法
        """
        pass
    
    @abstractmethod
    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """判斷 scope 是否為唯讀
        
        Args:
            scope: 範圍識別
            
        Returns:
            是否唯讀
        """
        pass
    
    # ============ 核心檔案操作方法 ============
    
    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """取得檔案樹

        Args:
            path: 目標路徑
            scope: 範圍識別
            include_hidden: 是否包含隱藏檔
            max_depth: 最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）

        Returns:
            檔案樹資料
        """
        # 使用設定檔中的預設值
        settings = get_settings()
        if max_depth is None:
            max_depth = settings.FILE_TREE_MAX_DEPTH

        # 限制最大深度不超過設定值
        max_depth = min(max_depth, settings.FILE_TREE_MAX_DEPTH)

        fs_path = self.resolve_scope_path(scope, path)

        # 如果目錄不存在
        if not fs_path.exists():
            # 只有根目錄 "/" 才自動創建，其他路徑回傳 404
            if path == "/" or path == "":
                fs_path.mkdir(parents=True, exist_ok=True)
                return {
                    "path": path,
                    "scope": scope,
                    "nodes": [],
                    "total": 0
                }
            else:
                raise FileNotFoundException(path, scope)

        if not fs_path.is_dir():
            raise InvalidPathException(path, "Not a directory")

        # 掃描目錄
        nodes = self._scan_directory(
            fs_path=fs_path,
            relative_path=path,
            current_depth=0,
            max_depth=max_depth,
            include_hidden=include_hidden,
            scope=scope
        )

        return {
            "path": path,
            "scope": scope,
            "nodes": nodes,
            "total": len(nodes)
        }
    
    def read_file(
        self,
        path: str,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """讀取檔案內容（文本模式）

        Args:
            path: 檔案路徑
            scope: 範圍識別

        Returns:
            檔案內容資料
        """
        fs_path = self.resolve_scope_path(scope, path)

        if not fs_path.exists():
            raise FileNotFoundException(path, scope)

        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")

        stat = fs_path.stat()

        # 檢測是否為二進位檔案或大檔案
        if self._is_binary_file(fs_path):
            # 返回友好的二進位檔案訊息
            content = f"Binary file: {path}\n(Binary files cannot be displayed in text editor)"
            content_hash = "binary"
        elif stat.st_size > 1 * 1024 * 1024:  # 超過 1MB
            # 返回大檔案警告
            size_mb = stat.st_size / (1024 * 1024)
            content = f"Large text file: {path}\nSize: {size_mb:.2f} MB\n(File too large to display in editor)"
            content_hash = "large"
        else:
            # 讀取文字內容
            try:
                content = fs_path.read_text(encoding="utf-8")
                # 計算內容雜湊
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # 檢查行數，如果超過 1000 行則截斷
                lines = content.split('\n')
                if len(lines) > 1000:
                    content = '\n'.join(lines[:1000]) + f'\n\n... (truncated, {len(lines) - 1000} more lines)'
                    content_hash = f"truncated:{content_hash}"
            except UnicodeDecodeError:
                # UTF-8 解碼失敗，視為二進位檔案
                content = f"Binary file: {path}\n(File encoding is not UTF-8)"
                content_hash = "binary"

        return {
            "path": path,
            "scope": scope,
            "content": content,
            "size": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "versionId": f"v{stat.st_mtime_ns}",
            "contentHash": f"sha256:{content_hash}"
        }

    def read_file_binary(
        self,
        path: str,
        scope: Optional[str] = None
    ) -> bytes:
        """讀取檔案內容（二進制模式）

        Args:
            path: 檔案路徑
            scope: 範圍識別

        Returns:
            檔案二進制內容
        """
        fs_path = self.resolve_scope_path(scope, path)

        if not fs_path.exists():
            raise FileNotFoundException(path, scope)

        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")

        # 讀取二進制內容
        return fs_path.read_bytes()
    
    def write_file(
        self,
        path: str,
        content: str,
        scope: Optional[str] = None,
        expected_version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """寫入檔案內容
        
        Args:
            path: 檔案路徑
            content: 檔案內容
            scope: 範圍識別
            expected_version_id: 預期版本ID（用於衝突檢測）
            
        Returns:
            寫入結果
        """
        if self.is_readonly_scope(scope):
            raise ReadonlyScopeException(scope)
        
        # 檢查檔案大小
        content_size = len(content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, content_size, self.MAX_FILE_SIZE)
        
        fs_path = self.resolve_scope_path(scope, path)
        
        # 建立父目錄
        fs_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 寫入檔案
        fs_path.write_text(content, encoding="utf-8")
        
        stat = fs_path.stat()
        
        return {
            "path": path,
            "scope": scope,
            "size": stat.st_size,
            "updatedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "versionId": f"v{stat.st_mtime_ns}"
        }
    
    def create_entry(
        self,
        path: str,
        entry_type: str,
        scope: Optional[str] = None,
        content: str = "",
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """建立檔案或目錄

        Args:
            path: 路徑
            entry_type: 類型（file 或 directory）
            scope: 範圍識別
            content: 檔案內容（僅檔案）
            encoding: 內容編碼方式（utf-8 或 base64）

        Returns:
            建立結果
        """
        if self.is_readonly_scope(scope):
            raise ReadonlyScopeException(scope)

        fs_path = self.resolve_scope_path(scope, path)

        if fs_path.exists():
            raise FileAlreadyExistsException(path, scope)

        # 建立父目錄
        fs_path.parent.mkdir(parents=True, exist_ok=True)

        if entry_type == "file":
            # 根據編碼方式寫入檔案
            if encoding == "base64":
                import base64
                # 解碼 base64 內容並寫入二進制檔案
                binary_content = base64.b64decode(content)
                fs_path.write_bytes(binary_content)
            else:
                # 寫入文本檔案
                fs_path.write_text(content, encoding="utf-8")

            stat = fs_path.stat()
            return {
                "path": path,
                "scope": scope,
                "type": "file",
                "size": stat.st_size,
                "createdAt": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat()
            }
        elif entry_type == "directory":
            fs_path.mkdir(parents=True, exist_ok=True)
            return {
                "path": path,
                "scope": scope,
                "type": "directory",
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
        else:
            raise InvalidPathException(path, f"Invalid entry type: {entry_type}")
    
    def delete_entry(
        self,
        path: str,
        scope: Optional[str] = None,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """刪除檔案或目錄
        
        Args:
            path: 路徑
            scope: 範圍識別
            recursive: 是否遞迴刪除目錄
            
        Returns:
            刪除結果
        """
        if self.is_readonly_scope(scope):
            raise ReadonlyScopeException(scope)
        
        fs_path = self.resolve_scope_path(scope, path)
        
        if not fs_path.exists():
            raise FileNotFoundException(path, scope)
        
        entry_type = "directory" if fs_path.is_dir() else "file"
        
        if fs_path.is_dir():
            if not recursive and any(fs_path.iterdir()):
                raise DirectoryNotEmptyException(path)
            shutil.rmtree(fs_path)
        else:
            fs_path.unlink()
        
        # 清理空的父目錄
        self._cleanup_empty_parents(fs_path.parent, scope)
        
        return {
            "path": path,
            "scope": scope,
            "type": entry_type
        }

    def copy_entry(
        self,
        source_path: str,
        dest_path: str,
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """複製檔案或目錄（支援資料夾複製）

        Args:
            source_path: 源路徑
            dest_path: 目標路徑
            source_scope: 源範圍
            dest_scope: 目標範圍
            overwrite: 是否覆蓋

        Returns:
            複製結果
        """
        if self.is_readonly_scope(dest_scope):
            raise ReadonlyScopeException(dest_scope)

        source_fs_path = self.resolve_scope_path(source_scope, source_path)
        dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, source_scope)

        # 如果目標是已存在的目錄，將源名稱附加到目標路徑
        if dest_fs_path.exists() and dest_fs_path.is_dir():
            dest_path = f"{dest_path}/{source_fs_path.name}".replace("//", "/")
            dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        # 檢查目標是否已存在
        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, dest_scope)

        # 建立目標父目錄
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # 執行複製
        if source_fs_path.is_dir():
            # 如果目標已存在且需要覆蓋，先刪除
            if dest_fs_path.exists() and overwrite:
                shutil.rmtree(dest_fs_path)
            # 複製整個目錄樹
            shutil.copytree(str(source_fs_path), str(dest_fs_path))
        else:
            # 複製單一檔案
            shutil.copy2(str(source_fs_path), str(dest_fs_path))

        return {
            "sourcePath": source_path,
            "destPath": dest_path,
            "sourceScope": source_scope,
            "destScope": dest_scope,
            "type": "directory" if dest_fs_path.is_dir() else "file"
        }

    def move_entry(
        self,
        source_path: str,
        dest_path: str,
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """移動或重命名檔案或目錄

        Args:
            source_path: 源路徑
            dest_path: 目標路徑
            source_scope: 源範圍
            dest_scope: 目標範圍
            overwrite: 是否覆蓋

        Returns:
            移動結果
        """
        if self.is_readonly_scope(source_scope):
            raise ReadonlyScopeException(source_scope)

        if self.is_readonly_scope(dest_scope):
            raise ReadonlyScopeException(dest_scope)

        source_fs_path = self.resolve_scope_path(source_scope, source_path)
        dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, source_scope)

        # 如果目標是已存在的目錄，將源名稱附加到目標路徑
        if dest_fs_path.exists() and dest_fs_path.is_dir():
            dest_path = f"{dest_path}/{source_fs_path.name}".replace("//", "/")
            dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        # 檢查目標是否已存在
        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, dest_scope)

        # 建立目標父目錄
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # 執行移動
        shutil.move(str(source_fs_path), str(dest_fs_path))

        # 清理空的源父目錄
        self._cleanup_empty_parents(source_fs_path.parent, source_scope)

        return {
            "sourcePath": source_path,
            "destPath": dest_path,
            "sourceScope": source_scope,
            "destScope": dest_scope,
            "type": "directory" if dest_fs_path.is_dir() else "file"
        }

    # ============ 批次操作方法 ============

    def batch_delete(
        self,
        paths: List[str],
        scope: Optional[str] = None,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """批次刪除

        Args:
            paths: 路徑列表
            scope: 範圍識別
            recursive: 是否遞迴刪除目錄

        Returns:
            批次操作結果
        """
        results = []

        for path in paths:
            try:
                self.delete_entry(path, scope, recursive)
                results.append({
                    "path": path,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "path": path,
                    "status": "failed",
                    "error": str(e)
                })

        succeeded = sum(1 for r in results if r["status"] == "success")

        return {
            "total": len(paths),
            "succeeded": succeeded,
            "failed": len(paths) - succeeded,
            "results": results
        }

    def batch_write(
        self,
        files: List[Dict[str, Any]],
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """批次寫入檔案

        Args:
            files: 檔案列表 [{"path": "...", "content": "..."}, ...]
            scope: 範圍識別

        Returns:
            批次操作結果
        """
        results = []

        for file_info in files:
            try:
                result = self.write_file(
                    path=file_info["path"],
                    content=file_info["content"],
                    scope=scope
                )
                results.append({
                    "path": file_info["path"],
                    "status": "success",
                    "size": result["size"]
                })
            except Exception as e:
                results.append({
                    "path": file_info["path"],
                    "status": "failed",
                    "error": str(e)
                })

        succeeded = sum(1 for r in results if r["status"] == "success")

        return {
            "results": results,
            "total": len(files),
            "succeeded": succeeded,
            "failed": len(files) - succeeded
        }

    # ============ 工具方法 ============

    def _scan_directory(
        self,
        fs_path: Path,
        relative_path: str,
        current_depth: int,
        max_depth: int,
        include_hidden: bool,
        scope: Optional[str]
    ) -> List[Dict[str, Any]]:
        """掃描目錄（效能優化版本）

        Args:
            fs_path: 檔案系統路徑
            relative_path: 相對路徑
            current_depth: 當前深度
            max_depth: 最大深度
            include_hidden: 是否包含隱藏檔
            scope: 範圍識別

        Returns:
            節點列表
        """
        if current_depth > max_depth:
            return []

        nodes = []

        try:
            items: list[tuple[os.DirEntry[str], bool]] = []
            with os.scandir(fs_path) as entries:
                for entry in entries:
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except (PermissionError, OSError):
                        continue
                    items.append((entry, is_directory))

            # 排序：目錄優先，然後按名稱
            items.sort(key=lambda item: (not item[1], item[0].name.lower()))

            for entry, is_directory in items:
                # 跳過隱藏檔
                if not include_hidden and entry.name.startswith('.'):
                    continue

                # 跳過特定目錄
                if entry.name in self.SKIP_DIRECTORIES:
                    continue

                item_relative_path = f"{relative_path}/{entry.name}".replace("//", "/")

                try:
                    stat = entry.stat(follow_symlinks=False)
                    updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()

                    if not is_directory:
                        nodes.append({
                            "id": item_relative_path,
                            "name": entry.name,
                            "path": item_relative_path,
                            "type": "file",
                            "scope": scope,
                            "size": stat.st_size,
                            "updatedAt": updated_at,
                            "depth": current_depth
                        })

                    else:
                        item_path = Path(entry.path)
                        # 遞迴掃描子目錄
                        children = self._scan_directory(
                            fs_path=item_path,
                            relative_path=item_relative_path,
                            current_depth=current_depth + 1,
                            max_depth=max_depth,
                            include_hidden=include_hidden,
                            scope=scope
                        )

                        # 對受 depth 限制而被截斷的目錄保留可展開提示，避免額外 I/O 驗證空目錄。
                        has_children = len(children) > 0 or current_depth >= max_depth

                        nodes.append({
                            "id": item_relative_path,
                            "name": entry.name,
                            "path": item_relative_path,
                            "type": "directory",
                            "scope": scope,
                            "size": 0,
                            "updatedAt": updated_at,
                            "depth": current_depth,
                            "children": children,
                            "hasChildren": has_children
                        })

                except (PermissionError, OSError):
                    continue

        except (PermissionError, OSError):
            pass

        return nodes

    def _cleanup_empty_parents(self, parent_path: Path, scope: Optional[str]):
        """清理空的父目錄

        Args:
            parent_path: 父目錄路徑
            scope: 範圍識別
        """
        scope_root = self.resolve_scope_path(scope, "/")

        while parent_path != scope_root and parent_path.exists():
            try:
                if not any(parent_path.iterdir()):
                    parent_path.rmdir()
                    parent_path = parent_path.parent
                else:
                    break
            except Exception:
                break

    def _is_binary_file(self, file_path: Path) -> bool:
        """檢測檔案是否為二進位檔案

        Args:
            file_path: 檔案路徑

        Returns:
            是否為二進位檔案
        """
        try:
            # 檢查檔案大小（超過 10MB 視為二進位）
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return True

            # 讀取前 8192 bytes 檢測
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)

            # 檢查是否包含 null byte（二進位檔案的特徵）
            if b'\x00' in chunk:
                return True

            # 嘗試解碼為 UTF-8
            # 使用 errors='ignore' 來處理邊界處被切斷的多字節字符
            try:
                chunk.decode('utf-8', errors='ignore')
                # 額外檢查：如果解碼後的字符串長度與原始字節長度差異過大，可能是二進制文件
                # 但這個檢查可能會誤判，所以我們只依賴 null byte 和基本的 UTF-8 解碼
                return False
            except UnicodeDecodeError:
                return True

        except (OSError, IOError):
            return True

    def _validate_path(self, path: str) -> str:
        """驗證路徑安全性（防止路徑穿越）

        Args:
            path: 路徑

        Returns:
            驗證後的路徑

        Raises:
            InvalidPathException: 路徑不合法
        """
        # 移除開頭的斜線
        path = path.lstrip("/")

        # 檢查是否包含危險字符
        if ".." in path:
            raise InvalidPathException(path, "Path traversal not allowed")

        # 檢查是否為絕對路徑（Windows）
        if Path(path).is_absolute():
            raise InvalidPathException(path, "Absolute paths not allowed")

        return path
