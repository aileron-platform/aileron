"""Base file service abstract class"""

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
    """Base file service
    
    Provides unified file operation interface, subclasses must implement scope-related methods
    """
    
    # Directories to skip (performance optimization)
    SKIP_DIRECTORIES = {
        '.git', 'node_modules', '__pycache__', '.venv', 'venv',
        'dist', 'build', '.next', '.nuxt', 'coverage', '.pytest_cache',
        'target', 'out', 'bin', 'obj', '.gradle', '.idea', '.vscode'
    }
    
    # File size limit (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, root_path: Path):
        """Initialize
        
        Args:
            root_path: Root directory path
        """
        self._root_path = Path(root_path)
        self._root_path.mkdir(parents=True, exist_ok=True)
    
    # ============ Abstract Methods (Must Implement) ============
    
    @abstractmethod
    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """Resolve scope and relative path to actual file system path
        
        Args:
            scope: Scope identifier (e.g., project, user, plugin, skills, scripts, etc.)
            relative_path: Relative path
            
        Returns:
            Actual file system path
        """
        pass
    
    @abstractmethod
    def validate_scope(self, scope: Optional[str]) -> bool:
        """Validate if scope is valid
        
        Args:
            scope: Scope identifier
            
        Returns:
            Whether valid
        """
        pass
    
    @abstractmethod
    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """Check if scope is read-only
        
        Args:
            scope: Scope identifier
            
        Returns:
            Whether read-only
        """
        pass
    
    # ============ Core File Operations ============
    
    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get file tree

        Args:
            path: Target path
            scope: Scope identifier
            include_hidden: Whether to include hidden files
            max_depth: Maximum depth (defaults to FILE_TREE_MAX_DEPTH in settings)

        Returns:
            File tree data
        """
        # Use default value from settings
        settings = get_settings()
        if max_depth is None:
            max_depth = settings.FILE_TREE_MAX_DEPTH

        # Limit max depth to settings value
        max_depth = min(max_depth, settings.FILE_TREE_MAX_DEPTH)

        fs_path = self.resolve_scope_path(scope, path)

        # If directory does not exist
        if not fs_path.exists():
            # Only auto-create root directory "/", other paths return 404
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

        # Scan directory
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
        """Read file content (text mode)

        Args:
            path: File path
            scope: Scope identifier

        Returns:
            File content data
        """
        fs_path = self.resolve_scope_path(scope, path)

        if not fs_path.exists():
            raise FileNotFoundException(path, scope)

        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")

        stat = fs_path.stat()

        # Check if binary or large file
        if self._is_binary_file(fs_path):
            # Return friendly binary file message
            content = f"Binary file: {path}\n(Binary files cannot be displayed in text editor)"
            content_hash = "binary"
        elif stat.st_size > 1 * 1024 * 1024:  # Over 1MB
            # Return large file warning
            size_mb = stat.st_size / (1024 * 1024)
            content = f"Large text file: {path}\nSize: {size_mb:.2f} MB\n(File too large to display in editor)"
            content_hash = "large"
        else:
            # Read text content
            try:
                content = fs_path.read_text(encoding="utf-8")
                # Calculate content hash
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Check line count, truncate if over 1000 lines
                lines = content.split('\n')
                if len(lines) > 1000:
                    content = '\n'.join(lines[:1000]) + f'\n\n... (truncated, {len(lines) - 1000} more lines)'
                    content_hash = f"truncated:{content_hash}"
            except UnicodeDecodeError:
                # UTF-8 decode failed, treat as binary file
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
        """Read file content (binary mode)

        Args:
            path: File path
            scope: Scope identifier

        Returns:
            File binary content
        """
        fs_path = self.resolve_scope_path(scope, path)

        if not fs_path.exists():
            raise FileNotFoundException(path, scope)

        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")

        # Read binary content
        return fs_path.read_bytes()
    
    def write_file(
        self,
        path: str,
        content: str,
        scope: Optional[str] = None,
        expected_version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Write file content
        
        Args:
            path: File path
            content: File content
            scope: Scope identifier
            expected_version_id: Expected version ID (for conflict detection)
            
        Returns:
            Write result
        """
        if self.is_readonly_scope(scope):
            raise ReadonlyScopeException(scope)
        
        # Check file size
        content_size = len(content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, content_size, self.MAX_FILE_SIZE)
        
        fs_path = self.resolve_scope_path(scope, path)
        
        # Create parent directory
        fs_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
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
        """Create file or directory

        Args:
            path: Path
            entry_type: Type (file or directory)
            scope: Scope identifier
            content: File content (files only)
            encoding: Content encoding (utf-8 or base64)

        Returns:
            Creation result
        """
        if self.is_readonly_scope(scope):
            raise ReadonlyScopeException(scope)

        fs_path = self.resolve_scope_path(scope, path)

        if fs_path.exists():
            raise FileAlreadyExistsException(path, scope)

        # Create parent directory
        fs_path.parent.mkdir(parents=True, exist_ok=True)

        if entry_type == "file":
            # Write file based on encoding
            if encoding == "base64":
                import base64
                # Decode base64 content and write binary file
                binary_content = base64.b64decode(content)
                fs_path.write_bytes(binary_content)
            else:
                # Write text file
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
        """Delete file or directory
        
        Args:
            path: Path
            scope: Scope identifier
            recursive: Whether to recursively delete directory
            
        Returns:
            Deletion result
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
        
        # Clean up empty parent directories
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
        """Copy file or directory (supports folder copy)

        Args:
            source_path: Source path
            dest_path: Destination path
            source_scope: Source scope
            dest_scope: Destination scope
            overwrite: Whether to overwrite

        Returns:
            Copy result
        """
        if self.is_readonly_scope(dest_scope):
            raise ReadonlyScopeException(dest_scope)

        source_fs_path = self.resolve_scope_path(source_scope, source_path)
        dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, source_scope)

        # If destination is existing directory, append source name to destination path
        if dest_fs_path.exists() and dest_fs_path.is_dir():
            dest_path = f"{dest_path}/{source_fs_path.name}".replace("//", "/")
            dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        # Check if destination already exists
        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, dest_scope)

        # Create destination parent directory
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform copy
        if source_fs_path.is_dir():
            # If destination exists and overwrite required, delete first
            if dest_fs_path.exists() and overwrite:
                shutil.rmtree(dest_fs_path)
            # Copy entire directory tree
            shutil.copytree(str(source_fs_path), str(dest_fs_path))
        else:
            # Copy single file
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
        """Move or rename file or directory

        Args:
            source_path: Source path
            dest_path: Destination path
            source_scope: Source scope
            dest_scope: Destination scope
            overwrite: Whether to overwrite

        Returns:
            Move result
        """
        if self.is_readonly_scope(source_scope):
            raise ReadonlyScopeException(source_scope)

        if self.is_readonly_scope(dest_scope):
            raise ReadonlyScopeException(dest_scope)

        source_fs_path = self.resolve_scope_path(source_scope, source_path)
        dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, source_scope)

        # If destination is existing directory, append source name to destination path
        if dest_fs_path.exists() and dest_fs_path.is_dir():
            dest_path = f"{dest_path}/{source_fs_path.name}".replace("//", "/")
            dest_fs_path = self.resolve_scope_path(dest_scope, dest_path)

        # Check if destination already exists
        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, dest_scope)

        # Create destination parent directory
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform move
        shutil.move(str(source_fs_path), str(dest_fs_path))

        # Clean up empty source parent directories
        self._cleanup_empty_parents(source_fs_path.parent, source_scope)

        return {
            "sourcePath": source_path,
            "destPath": dest_path,
            "sourceScope": source_scope,
            "destScope": dest_scope,
            "type": "directory" if dest_fs_path.is_dir() else "file"
        }

    # ============ Batch Operations ============

    def batch_delete(
        self,
        paths: List[str],
        scope: Optional[str] = None,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """Batch delete

        Args:
            paths: Path list
            scope: Scope identifier
            recursive: Whether to recursively delete directories

        Returns:
            Batch operation result
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
        """Batch write files

        Args:
            files: File list [{"path": "...", "content": "..."}, ...]
            scope: Scope identifier

        Returns:
            Batch operation result
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

    # ============ Utility Methods ============

    def _scan_directory(
        self,
        fs_path: Path,
        relative_path: str,
        current_depth: int,
        max_depth: int,
        include_hidden: bool,
        scope: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Scan directory (performance optimized version)

        Args:
            fs_path: File system path
            relative_path: Relative path
            current_depth: Current depth
            max_depth: Maximum depth
            include_hidden: Whether to include hidden files
            scope: Scope identifier

        Returns:
            Node list
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

            # Sort: directories first, then by name
            items.sort(key=lambda item: (not item[1], item[0].name.lower()))

            for entry, is_directory in items:
                # Skip hidden files
                if not include_hidden and entry.name.startswith('.'):
                    continue

                # Skip specific directories
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
                        # Recursively scan subdirectories
                        children = self._scan_directory(
                            fs_path=item_path,
                            relative_path=item_relative_path,
                            current_depth=current_depth + 1,
                            max_depth=max_depth,
                            include_hidden=include_hidden,
                            scope=scope
                        )

                        # Keep expandable hint for directories truncated by depth limit to avoid extra I/O for empty directory validation.
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
        """Clean up empty parent directories

        Args:
            parent_path: Parent directory path
            scope: Scope identifier
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
        """Detect if file is binary

        Args:
            file_path: File path

        Returns:
            Whether file is binary
        """
        try:
            # Check file size (over 10MB treated as binary)
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return True

            # Read first 8192 bytes for detection
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)

            # Check for null byte (binary file characteristic)
            if b'\x00' in chunk:
                return True

            # Try UTF-8 decoding
            # Use errors='ignore' to handle multi-byte characters cut off at boundaries
            try:
                chunk.decode('utf-8', errors='ignore')
                # Additional check: if decoded string length differs greatly from original byte length, might be binary file
                # But this check may misclassify, so we only rely on null byte and basic UTF-8 decoding
                return False
            except UnicodeDecodeError:
                return True

        except (OSError, IOError):
            return True

    def _validate_path(self, path: str) -> str:
        """Validate path security (prevent path traversal)

        Args:
            path: Path

        Returns:
            Validated path

        Raises:
            InvalidPathException: Invalid path
        """
        # Remove leading slash
        path = path.lstrip("/")

        # Check for dangerous characters
        if ".." in path:
            raise InvalidPathException(path, "Path traversal not allowed")

        # Check if absolute path (Windows)
        if Path(path).is_absolute():
            raise InvalidPathException(path, "Absolute paths not allowed")

        return path
