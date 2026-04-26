import os
import re
from pathlib import Path
from .platform_detector import PlatformDetector

class PathResolver:
    @staticmethod
    def resolve_path(path: str) -> str:
        """
        Parse and normalize path
        Handle:
        1. Relative path -> Absolute path
        2. Windows path conversion in WSL
        3. User home directory expansion
        """
        if not path:
            return path
            
        # Expand user home directory
        expanded_path = os.path.expanduser(path)
        
        # Convert to absolute path
        abs_path = os.path.abspath(expanded_path)
        
        # If running in WSL and path is Windows format (e.g. C:\Users\...)
        if PlatformDetector.is_wsl() and re.match(r'^[a-zA-Z]:\\', abs_path):
            return PathResolver._windows_to_wsl(abs_path)
            
        return abs_path

    @staticmethod
    def _windows_to_wsl(windows_path: str) -> str:
        r"""
        Convert Windows path to WSL path
        C:\Users\Name -> /mnt/c/Users/Name
        """
        # Replace backslashes
        path = windows_path.replace('\\', '/')
        
        # Extract drive letter
        match = re.match(r'^([a-zA-Z]):/(.*)', path)
        if match:
            drive_letter = match.group(1).lower()
            rest_of_path = match.group(2)
            return f"/mnt/{drive_letter}/{rest_of_path}"
            
        return path

    @staticmethod
    def resolve_volume_source(source_path: str, runtime_provisioner: str = "docker") -> str:
        """
        Parse volume mount source path

        Args:
            source_path: Source path
            runtime_provisioner: docker or kubernetes

        Returns:
            Path suitable for the runtime
        """
        # If is named volume (does not contain / or \ or .)
        if not any(c in source_path for c in ['/', '\\', '.']):
            return source_path
            
        resolved_path = PathResolver.resolve_path(source_path)
        
        # Special case: Docker Desktop on Windows (called through WSL)
        # If we are in WSL, but using Docker Desktop (Windows),
        # Does Docker Desktop expect Windows path or WSL path?
        # Usually Docker Desktop for Windows handles /mnt/c/... paths with auto-mapping
        
        return resolved_path
