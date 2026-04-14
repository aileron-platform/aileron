import pytest
import sys
from unittest.mock import patch, mock_open
from app.utils.platform_detector import PlatformDetector
from app.utils.path_resolver import PathResolver

class TestPlatformDetector:
    @patch('platform.system')
    def test_detect_os_mac(self, mock_system):
        mock_system.return_value = "Darwin"
        assert PlatformDetector.detect_os() == "mac"

    @patch('platform.system')
    def test_detect_os_windows(self, mock_system):
        mock_system.return_value = "Windows"
        assert PlatformDetector.detect_os() == "windows"

    @patch('platform.system')
    def test_detect_os_linux(self, mock_system):
        mock_system.return_value = "Linux"
        assert PlatformDetector.detect_os() == "linux"

    @patch('subprocess.run')
    def test_detect_container_runtime_returns_docker(self, mock_run):
        mock_run.return_value = None
        assert PlatformDetector.detect_container_runtime() == "docker"
        mock_run.assert_called_once_with(["docker", "--version"], capture_output=True, check=True)

    @patch('subprocess.run', side_effect=FileNotFoundError)
    def test_detect_container_runtime_returns_unknown_without_docker(self, mock_run):
        assert PlatformDetector.detect_container_runtime() == "unknown"
        mock_run.assert_called_once_with(["docker", "--version"], capture_output=True, check=True)

    @patch('builtins.open', new_callable=mock_open, read_data="Linux version ... microsoft-standard-WSL2 ...")
    @patch('os.path.exists')
    def test_is_wsl_true(self, mock_exists, mock_file):
        mock_exists.return_value = True
        assert PlatformDetector.is_wsl() is True

    @patch('builtins.open', new_callable=mock_open, read_data="Linux version ... generic ...")
    @patch('os.path.exists')
    def test_is_wsl_false(self, mock_exists, mock_file):
        mock_exists.return_value = True
        assert PlatformDetector.is_wsl() is False

class TestPathResolver:
    @patch('app.utils.platform_detector.PlatformDetector.is_wsl')
    def test_resolve_path_wsl_conversion(self, mock_is_wsl):
        mock_is_wsl.return_value = True
        # Test Windows path conversion in WSL
        windows_path = r"C:\Users\Test\Project"
        expected_wsl_path = "/mnt/c/Users/Test/Project"
        
        # We need to mock os.path.abspath because on non-Windows it won't handle C: correctly as absolute
        # But for this test logic, we are testing _windows_to_wsl mainly
        
        converted = PathResolver._windows_to_wsl(windows_path)
        assert converted == expected_wsl_path

    def test_resolve_volume_source_named_volume(self):
        assert PathResolver.resolve_volume_source("my-volume") == "my-volume"
