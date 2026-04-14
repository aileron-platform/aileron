import os
import re
from pathlib import Path
from .platform_detector import PlatformDetector

class PathResolver:
    @staticmethod
    def resolve_path(path: str) -> str:
        """
        解析並標準化路徑
        處理:
        1. 相對路徑 -> 絕對路徑
        2. Windows 路徑在 WSL 中的轉換
        3. 用戶主目錄擴展
        """
        if not path:
            return path
            
        # 擴展用戶主目錄
        expanded_path = os.path.expanduser(path)
        
        # 轉換為絕對路徑
        abs_path = os.path.abspath(expanded_path)
        
        # 如果在 WSL 中運行，且路徑是 Windows 格式 (e.g. C:\Users\...)
        if PlatformDetector.is_wsl() and re.match(r'^[a-zA-Z]:\\', abs_path):
            return PathResolver._windows_to_wsl(abs_path)
            
        return abs_path

    @staticmethod
    def _windows_to_wsl(windows_path: str) -> str:
        r"""
        將 Windows 路徑轉換為 WSL 路徑
        C:\Users\Name -> /mnt/c/Users/Name
        """
        # 替換反斜槓
        path = windows_path.replace('\\', '/')
        
        # 提取盤符
        match = re.match(r'^([a-zA-Z]):/(.*)', path)
        if match:
            drive_letter = match.group(1).lower()
            rest_of_path = match.group(2)
            return f"/mnt/{drive_letter}/{rest_of_path}"
            
        return path

    @staticmethod
    def resolve_volume_source(source_path: str, runtime_provisioner: str = "docker") -> str:
        """
        解析 Volume 掛載源路徑
        
        Args:
            source_path: 源路徑
            runtime_provisioner: docker 或 kubernetes

        Returns:
            適合該運行時的路徑
        """
        # 如果是命名 volume (不包含 / 或 \ 或 .)
        if not any(c in source_path for c in ['/', '\\', '.']):
            return source_path
            
        resolved_path = PathResolver.resolve_path(source_path)
        
        # 特殊情況: Docker Desktop on Windows (通過 WSL 調用)
        # 如果我們在 WSL 中，但使用的是 Docker Desktop (Windows)，
        # Docker Desktop 期望的是 Windows 路徑還是 WSL 路徑?
        # 通常 Docker Desktop for Windows 處理 /mnt/c/... 路徑會自動映射
        
        return resolved_path
