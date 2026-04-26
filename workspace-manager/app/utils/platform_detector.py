import platform
import subprocess
import os

class PlatformDetector:
    @staticmethod
    def detect_os() -> str:
        """Detect operating system"""
        system = platform.system()
        return {
            "Darwin": "mac",
            "Windows": "windows",
            "Linux": "linux"
        }.get(system, "unknown")

    @staticmethod
    def detect_container_runtime() -> str:
        """Detect container runtime"""
        # Currently only supports docker and kubernetes, here we only detect docker
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
            return "docker"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    @staticmethod
    def is_wsl() -> bool:
        """Detect if running in WSL"""
        try:
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    return "microsoft" in f.read().lower()
        except Exception:
            pass
        return False
