"""重構後的檔案服務實作 - 繼承 BaseFileService"""

from pathlib import Path
from typing import Optional, Union

from .base_service import BaseFileService


class FileService(BaseFileService):
    """一般檔案管理服務
    
    不使用 scope 機制，直接操作 workspace 根目錄
    """
    
    def __init__(self, root_path: Union[str, Path, None] = None):
        """初始化
        
        Args:
            root_path: 根目錄路徑，如果為 None 則從設定檔讀取
        """
        if root_path:
            resolved_path = Path(root_path).resolve()
        else:
            from app.config.settings import get_settings
            settings = get_settings()
            resolved_path = Path(settings.WORKSPACE_PATH).resolve()
        
        super().__init__(resolved_path)
    
    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """解析路徑（Files 不使用 scope）
        
        Args:
            scope: 範圍識別（忽略）
            relative_path: 相對路徑
            
        Returns:
            實際檔案系統路徑
        """
        validated_path = self._validate_path(relative_path)
        return self._root_path / validated_path
    
    def validate_scope(self, scope: Optional[str]) -> bool:
        """驗證 scope（Files 不使用 scope，總是返回 True）
        
        Args:
            scope: 範圍識別
            
        Returns:
            總是返回 True
        """
        return True
    
    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """判斷是否唯讀（Files 沒有唯讀 scope）
        
        Args:
            scope: 範圍識別
            
        Returns:
            總是返回 False
        """
        return False

