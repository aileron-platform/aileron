import platform
import subprocess
import os

class PlatformDetector:
    @staticmethod
    def detect_os() -> str:
        """檢測作業系統"""
        system = platform.system()
        return {
            "Darwin": "mac",
            "Windows": "windows",
            "Linux": "linux"
        }.get(system, "unknown")

    @staticmethod
    def detect_container_runtime() -> str:
        """檢測容器運行時"""
        # 目前僅支援 docker 與 kubernetes，這裡只檢測 docker
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
            return "docker"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    @staticmethod
    def is_wsl() -> bool:
        """檢測是否在 WSL 中"""
        try:
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    return "microsoft" in f.read().lower()
        except Exception:
            pass
        return False
