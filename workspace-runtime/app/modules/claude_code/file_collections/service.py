"""File Collections 服務層 - 重構版本

繼承自 BaseFileService，支援 Skills 和 Scripts 的檔案管理
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.modules.file_system import (
    BaseFileService,
    FileNode,
    FileManagementException,
    InvalidScopeException,
    ReadonlyScopeException,
)
from ..common import DocumentScope, resolve_scope_root
from ..plugins.loader import get_plugin_loader
from ..settings.service import SettingsService
from .models import (
    FileCollectionType,
    FileType,
    PluginSkillInfo,
)


class FileCollectionService(BaseFileService):
    """檔案集合服務 - 統一處理 Skills 和 Scripts
    
    支援的 scope:
    - project: 專案級別
    - user: 使用者級別
    - plugin: 插件級別（唯讀）
    """

    # 檔案類型映射
    FILE_TYPE_MAP = {
        ".md": FileType.MARKDOWN,
        ".ts": FileType.TYPESCRIPT,
        ".js": FileType.JAVASCRIPT,
        ".yaml": FileType.YAML,
        ".yml": FileType.YAML,
        ".json": FileType.JSON,
        ".py": FileType.PYTHON,
        ".sh": FileType.SHELL,
    }

    # 有效的 scope 值
    VALID_SCOPES = {DocumentScope.PROJECT, DocumentScope.USER, DocumentScope.PLUGIN}

    def __init__(self, collection_type: FileCollectionType, workspace_id: str):
        """初始化服務

        Args:
            collection_type: 集合類型（SKILLS 或 SCRIPTS）
            workspace_id: Workspace ID
        """
        # 不需要 root_path，因為我們使用 scope 來解析路徑
        super().__init__(root_path=Path("/tmp"))  # 臨時路徑，不會被使用
        
        self.collection_type = collection_type
        self.workspace_id = workspace_id
        self.settings_service = SettingsService()
        self.plugin_loader = get_plugin_loader(self.settings_service)

    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """解析 scope 和相對路徑到實際檔案系統路徑
        
        Args:
            scope: 範圍識別 (project/user/plugin)
            relative_path: 相對路徑
            
        Returns:
            實際檔案系統路徑
            
        Raises:
            InvalidScopeException: 無效的 scope
        """
        # 預設使用 project scope
        if not scope:
            scope = DocumentScope.PROJECT
        
        # 驗證 scope
        if not self.validate_scope(scope):
            raise InvalidScopeException(f"Invalid scope: {scope}")
        
        # 解析 scope 根目錄
        scope_root = resolve_scope_root(self.workspace_id, scope)
        
        # 根據集合類型添加子目錄
        if self.collection_type == FileCollectionType.SKILLS:
            collection_dir = scope_root / "skills"
        else:  # SCRIPTS
            collection_dir = scope_root / "scripts"
        
        # 驗證並解析相對路徑
        validated_path = self._validate_path(relative_path)
        
        return collection_dir / validated_path

    def validate_scope(self, scope: Optional[str]) -> bool:
        """驗證 scope 是否有效
        
        Args:
            scope: 範圍識別
            
        Returns:
            是否有效
        """
        if not scope:
            return True  # None 會被轉換為預設的 project
        
        return scope in self.VALID_SCOPES

    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """檢查 scope 是否為唯讀
        
        Args:
            scope: 範圍識別
            
        Returns:
            是否唯讀
        """
        return scope == DocumentScope.PLUGIN

    def _get_file_type(self, file_path: Path) -> FileType:
        """取得檔案類型"""
        suffix = file_path.suffix.lower()
        return self.FILE_TYPE_MAP.get(suffix, FileType.OTHER)

    def _parse_front_matter(self, content: str) -> tuple[Optional[Dict], str]:
        """解析 Front Matter
        
        Args:
            content: 檔案內容
            
        Returns:
            (front_matter_dict, content_without_front_matter)
        """
        # 檢查是否有 YAML Front Matter
        if not content.startswith("---\n"):
            return None, content
        
        # 找到第二個 ---
        end_marker = content.find("\n---\n", 4)
        if end_marker == -1:
            return None, content
        
        # 提取 Front Matter
        front_matter_str = content[4:end_marker]
        remaining_content = content[end_marker + 5:]
        
        try:
            front_matter = yaml.safe_load(front_matter_str)
            return front_matter, remaining_content
        except yaml.YAMLError:
            return None, content

    def get_tree_with_metadata(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: int = 1
    ) -> List[FileNode]:
        """取得檔案樹（帶 Front Matter 元數據）
        
        Args:
            path: 目標路徑
            scope: 範圍識別
            include_hidden: 是否包含隱藏檔
            max_depth: 最大深度
            
        Returns:
            檔案節點列表（包含 metadata）
        """
        # 使用父類的 get_tree 方法
        tree_response = self.get_tree(path, scope, include_hidden, max_depth)
        nodes = tree_response["nodes"]
        
        # 為每個檔案節點添加 Front Matter 元數據
        for node in nodes:
            if node["type"] == "file":
                try:
                    # 讀取檔案內容
                    content_response = self.read_file(node["path"], scope)
                    content = content_response["content"]
                    
                    # 解析 Front Matter
                    front_matter, _ = self._parse_front_matter(content)
                    
                    if front_matter:
                        # 將 Front Matter 添加到 metadata
                        if node.get("metadata") is None:
                            node["metadata"] = {}
                        node["metadata"]["frontMatter"] = front_matter
                        
                        # 添加檔案類型
                        file_type = self._get_file_type(Path(node["path"]))
                        node["fileType"] = file_type.value
                        
                except Exception:
                    # 如果讀取失敗，跳過元數據
                    pass
        
        return nodes

    def get_plugin_skills(self) -> List[PluginSkillInfo]:
        """取得所有插件的 Skills
        
        Returns:
            插件 Skills 列表
        """
        plugin_skills = []
        
        try:
            # 取得所有已安裝的插件
            plugins = self.plugin_loader.get_installed_plugins()
            
            for plugin in plugins:
                # 取得插件的 skills 目錄
                plugin_root = resolve_scope_root(self.workspace_id, DocumentScope.PLUGIN)
                skills_dir = plugin_root / plugin.name / "skills"
                
                if not skills_dir.exists():
                    continue
                
                # 掃描 skills 目錄
                for skill_file in skills_dir.glob("*.md"):
                    try:
                        content = skill_file.read_text(encoding="utf-8")
                        front_matter, _ = self._parse_front_matter(content)
                        
                        plugin_skills.append(PluginSkillInfo(
                            pluginName=plugin.name,
                            pluginVersion=plugin.version,
                            skillName=skill_file.stem,
                            skillPath=str(skill_file.relative_to(plugin_root)),
                            description=front_matter.get("description", "") if front_matter else "",
                            metadata=front_matter
                        ))
                    except Exception:
                        # 跳過無法讀取的檔案
                        continue
        
        except Exception:
            # 如果取得插件失敗，返回空列表
            pass
        
        return plugin_skills


__all__ = ["FileCollectionService"]

