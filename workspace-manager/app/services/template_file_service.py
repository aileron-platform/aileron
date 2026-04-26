"""Template file management service - Refactored version

Uses unified file management API structure, replaces base_path with scope
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
    """Handles template file system operations (using unified scope constraint)

    Scope definitions:
    - skills: Template skills directory
    - scripts: Template scripts directory
    """

    # Valid scope values
    VALID_SCOPES = {"skills", "scripts"}

    # Directories to skip
    SKIP_DIRECTORIES = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        ".next", "dist", "build", ".cache", ".pytest_cache"
    }

    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Upload-related constants
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
        """Validate and return valid scope

        Args:
            scope: Scope identifier

        Returns:
            Valid scope

        Raises:
            InvalidScopeException: Invalid scope
        """
        if not scope:
            scope = "scripts"  # Default to scripts
        
        if scope not in self.VALID_SCOPES:
            raise InvalidScopeException(f"Invalid scope: {scope}. Must be 'skills' or 'scripts'")
        
        return scope

    def _validate_path(self, path: str) -> str:
        """Verify path security
        
        Args:
            path: relative path
            
        Returns:
            Verified path
            
        Raises:
            InvalidPathException: invalid path
        """
        if not path:
            return ""
        
        # Remove leading slash
        path = path.lstrip("/")
        
        # Check path traversal
        if ".." in path or path.startswith("/"):
            raise InvalidPathException(path, "Path traversal detected")
        
        return path

    def _resolve_path(self, template_id: str, scope: str, relative_path: str) -> Path:
        """Parse complete file system path
        
        Args:
            template_id: Template ID
            scope: scope identifier
            relative_path: relative path
            
        Returns:
            complete file system path
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
        """Scan directory and create file tree
        
        Args:
            directory: directory to scan
            base_path: base path (for calculating relative path)
            include_hidden: whether to include hidden files
            max_depth: maximum depth
            current_depth: current depth
            
        Returns:
            FileNode list
        """
        if not directory.exists() or not directory.is_dir():
            return []
        
        nodes = []
        
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for entry in entries:
                # Skip hidden files
                if not include_hidden and entry.name.startswith("."):
                    continue
                
                # Skip specific directories
                if entry.is_dir() and entry.name in self.SKIP_DIRECTORIES:
                    continue
                
                # Calculate relative path
                try:
                    rel_path = entry.relative_to(base_path)
                    path_str = "/" + str(rel_path).replace("\\", "/")
                except ValueError:
                    continue
                
                # GetFileInformation
                stat = entry.stat()
                updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                
                # CreateNode
                node = FileNode(
                    id=path_str,
                    name=entry.name,
                    path=path_str,
                    type="directory" if entry.is_dir() else "file",
                    scope=None,  # Template files do not use scope in node
                    size=stat.st_size if entry.is_file() else 0,
                    updatedAt=updated_at,
                    depth=current_depth,
                    children=[],
                    hasChildren=False
                )
                
                # If directory and max depth not reached, recursive scan
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
        """Get file tree
        
        Args:
            template_id: Template ID
            path: target path
            scope: scope identifier (skills/scripts)
            include_hidden: whether to include hidden files
            max_depth: maximum depth
            
        Returns:
            File tree response
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")
        
        # Validate scope
        scope = self._validate_scope(scope)
        
        # ParsePath
        fs_path = self._resolve_path(template_id, scope, path)
        
        # Ensure directory exists
        if not fs_path.exists():
            fs_path.mkdir(parents=True, exist_ok=True)
            return FileTreeResponse(
                path=path,
                scope=scope,
                nodes=[],
                total=0
            )
        
        # ScanDirectory
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
        """ReadFileContent
        
        Args:
            template_id: Template ID
            path: FilePath
            scope: scope identifier
            
        Returns:
            FileContentResponse
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")
        
        # Validate scope
        scope = self._validate_scope(scope)
        
        # ParsePath
        fs_path = self._resolve_path(template_id, scope, path)
        
        if not fs_path.exists():
            raise FileNotFoundException(path, scope)
        
        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")
        
        # Check file size
        file_size = fs_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, file_size, self.MAX_FILE_SIZE)
        
        # ReadContent
        try:
            content = fs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # If not UTF-8, try other encodings
            content = fs_path.read_text(encoding="latin-1")
        
        # Calculate version ID and content hash
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
        """WriteFileContent

        Args:
            template_id: Template ID
            path: FilePath
            content: FileContent
            scope: scope identifier
            expected_version_id: expected version ID (conflict detection)

        Returns:
            OperationResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParsePath
        fs_path = self._resolve_path(template_id, scope, path)

        # Check file size
        content_size = len(content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            raise FileTooLargeException(path, content_size, self.MAX_FILE_SIZE)

        # If file exists and expected_version_id provided, check version
        if fs_path.exists() and expected_version_id:
            current_content = fs_path.read_text(encoding="utf-8")
            current_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
            current_version = current_hash[:16]

            if current_version != expected_version_id:
                from app.core.file_management.exceptions import ContentConflictException
                raise ContentConflictException(path, expected_version_id, current_version)

        # Ensure parent directory exists
        fs_path.parent.mkdir(parents=True, exist_ok=True)

        # WriteFile
        fs_path.write_text(content, encoding="utf-8")

        # Calculate new version ID
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
        """Create file or directory

        Args:
            template_id: Template ID
            path: Path
            entry_type: Type (file/directory)
            scope: scope identifier
            content: file content (file only)

        Returns:
            OperationResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParsePath
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
            # Ensure parent directory exists
            fs_path.parent.mkdir(parents=True, exist_ok=True)

            # WriteContent
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
        """Delete file or directory

        Args:
            template_id: Template ID
            path: Path
            scope: scope identifier
            recursive: whether to recursively delete

        Returns:
            OperationResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParsePath
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
        """Copy file or directory

        Args:
            template_id: Template ID
            source_path: source path
            dest_path: target path
            scope: scope identifier
            overwrite: whether to overwrite

        Returns:
            OperationResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParsePath
        source_fs_path = self._resolve_path(template_id, scope, source_path)
        dest_fs_path = self._resolve_path(template_id, scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, scope)

        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, scope)

        # Ensure target parent directory exists
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy
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
        """Move file or directory

        Args:
            template_id: Template ID
            source_path: source path
            dest_path: target path
            scope: scope identifier
            overwrite: whether to overwrite

        Returns:
            OperationResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParsePath
        source_fs_path = self._resolve_path(template_id, scope, source_path)
        dest_fs_path = self._resolve_path(template_id, scope, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, scope)

        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, scope)

        # Ensure target parent directory exists
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        # Move
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
        """Batch delete files

        Args:
            template_id: Template ID
            paths: path list
            scope: scope identifier
            recursive: whether to recursively delete

        Returns:
            batch operation response
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
        """Verify file name

        Args:
            filename: file name

        Returns:
            whether valid
        """
        if not filename:
            return False

        # Do not allow path separators
        if "/" in filename or "\\" in filename:
            return False

        # Do not allow special characters
        if re.search(r'[<>:"|?*]', filename):
            return False

        # Do not allow starting with dot (hidden files)
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
        """Upload file

        Args:
            template_id: Template ID
            target_path: target directory path
            files: list of uploaded files
            overwrite: whether to overwrite
            scope: scope identifier

        Returns:
            upload result
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # Check file count
        if len(files) > self.MAX_UPLOAD_FILES:
            return FileUploadResponse(
                success=False,
                uploaded=[],
                total=len(files),
                succeeded=0,
                failed=len(files),
                message=f"Too many files (max {self.MAX_UPLOAD_FILES})"
            )

        # Parse target directory
        target_dir = self._resolve_path(template_id, scope, target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        results = []
        succeeded = 0
        failed = 0

        for upload_file in files:
            try:
                # Validate file name
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

                # Check file extension
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

                # Check if already exists
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

                # Read and check size
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

                # WriteFile
                file_path.write_bytes(content)

                # Calculate relative path
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
                logger.error(f"file upload failed {upload_file.filename}: {e}")
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
        """SearchFile

        Args:
            template_id: Template ID
            request: SearchRequest
            scope: scope identifier

        Returns:
            SearchResult
        """
        # ValidateTemplate
        db_template = self._get_template(template_id)
        if not db_template:
            raise FileNotFoundException(f"Template {template_id}")

        # Validate scope
        scope = self._validate_scope(scope)

        # ParseSearchDirectory
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

                # Skip specific directories
                if any(skip_dir in item.parts for skip_dir in self.SKIP_DIRECTORIES):
                    continue

                # Calculate relative path
                relative_path = "/" + str(item.relative_to(search_dir)).replace("\\", "/")

                # File name matches
                name_match = query_lower in item.name.lower()

                # FileTypeFilter
                if request.fileTypes and item.is_file():
                    if item.suffix not in request.fileTypes:
                        continue

                content_matches = []
                if request.searchContent and item.is_file():
                    try:
                        if item.stat().st_size < self.MAX_FILE_SIZE:
                            content = item.read_text(encoding="utf-8")
                            if query_lower in content.lower():
                                # Extract matching lines
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if query_lower in line.lower():
                                        content_matches.append(f"Line {i+1}: {line.strip()[:100]}")
                                        if len(content_matches) >= 3:
                                            break
                    except Exception as e:
                        logger.debug(f"cannot read file content {item}: {e}")

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
            logger.error(f"SearchFailed: {e}")
            raise FileManagementException(
                code="SEARCH_FAILED",
                message=f"Search failed: {str(e)}",
                status_code=500
            )
    def load_files(self, template_id: str) -> List:
        """Load file structure (scripts directory)"""
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
                            content=item.read_text(encoding="utf-8", errors="ignore") if item.stat().st_size < 1024 * 1024 else None,  # Limit 1MB
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
                logger.error(f"LoadFileNodeFailed {path}: {e}")

            return nodes

        return build_file_tree(files_dir)

    def load_skills(self, template_id: str) -> List:
        """Load file structure (skills directory)"""
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
                            content=item.read_text(encoding="utf-8", errors="ignore") if item.stat().st_size < 1024 * 1024 else None,  # Limit 1MB
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
                logger.error(f"LoadFileNodeFailed {path}: {e}")

            return nodes

        return build_file_tree(skills_dir)


__all__ = ["TemplateFileService"]

