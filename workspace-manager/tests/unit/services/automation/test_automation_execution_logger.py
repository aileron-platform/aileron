"""AutomationExecutionLogger 單元測試"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.automation_execution_logger import AutomationExecutionLogger


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def execution_logger():
    """基本執行日誌記錄器"""
    return AutomationExecutionLogger(
        execution_id="exec-123",
        job_id="job-123"
    )


@pytest.fixture
def execution_logger_with_workspace():
    """帶工作區的執行日誌記錄器"""
    return AutomationExecutionLogger(
        execution_id="exec-456",
        job_id="job-456",
        workspace_id="ws-123"
    )


# ============================================================================
# 初始化測試
# ============================================================================

@pytest.mark.unit
class TestLoggerInitialization:
    """日誌記錄器初始化測試"""

    def test_init_without_workspace(self):
        """測試：不帶工作區初始化"""
        # Act
        logger = AutomationExecutionLogger(
            execution_id="exec-123",
            job_id="job-123"
        )

        # Assert
        assert logger.execution_id == "exec-123"
        assert logger.job_id == "job-123"
        assert logger.workspace_id is None
        assert logger.logs == []

    def test_init_with_workspace(self):
        """測試：帶工作區初始化"""
        # Act
        logger = AutomationExecutionLogger(
            execution_id="exec-123",
            job_id="job-123",
            workspace_id="ws-123"
        )

        # Assert
        assert logger.execution_id == "exec-123"
        assert logger.job_id == "job-123"
        assert logger.workspace_id == "ws-123"
        assert logger.logs == []


# ============================================================================
# 日誌記錄測試
# ============================================================================

@pytest.mark.unit
class TestLogging:
    """日誌記錄測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_info_level(self, mock_logger, execution_logger):
        """測試：記錄 INFO 級別日誌"""
        # Act
        execution_logger.log("INFO", "Test info message", key1="value1")

        # Assert
        assert len(execution_logger.logs) == 1
        log = execution_logger.logs[0]
        assert log["level"] == "INFO"
        assert log["message"] == "Test info message"
        assert log["execution_id"] == "exec-123"
        assert log["job_id"] == "job-123"
        assert log["key1"] == "value1"
        assert "timestamp" in log
        mock_logger.info.assert_called_once()

    @patch('app.services.automation_execution_logger.logger')
    def test_log_warning_level(self, mock_logger, execution_logger):
        """測試：記錄 WARNING 級別日誌"""
        # Act
        execution_logger.log("WARNING", "Test warning message")

        # Assert
        assert len(execution_logger.logs) == 1
        log = execution_logger.logs[0]
        assert log["level"] == "WARNING"
        assert log["message"] == "Test warning message"
        mock_logger.warning.assert_called_once()

    @patch('app.services.automation_execution_logger.logger')
    def test_log_error_level(self, mock_logger, execution_logger):
        """測試：記錄 ERROR 級別日誌"""
        # Act
        execution_logger.log("ERROR", "Test error message", error_code=500)

        # Assert
        assert len(execution_logger.logs) == 1
        log = execution_logger.logs[0]
        assert log["level"] == "ERROR"
        assert log["message"] == "Test error message"
        assert log["error_code"] == 500
        mock_logger.error.assert_called_once()

    @patch('app.services.automation_execution_logger.logger')
    def test_log_debug_level(self, mock_logger, execution_logger):
        """測試：記錄 DEBUG 級別日誌"""
        # Act
        execution_logger.log("DEBUG", "Test debug message")

        # Assert
        assert len(execution_logger.logs) == 1
        log = execution_logger.logs[0]
        assert log["level"] == "DEBUG"
        assert log["message"] == "Test debug message"
        mock_logger.debug.assert_called_once()

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_workspace_id(self, mock_logger, execution_logger_with_workspace):
        """測試：記錄帶工作區 ID 的日誌"""
        # Act
        execution_logger_with_workspace.log("INFO", "Test message")

        # Assert
        assert len(execution_logger_with_workspace.logs) == 1
        log = execution_logger_with_workspace.logs[0]
        assert log["workspace_id"] == "ws-123"

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_multiple_context(self, mock_logger, execution_logger):
        """測試：記錄帶多個上下文的日誌"""
        # Act
        execution_logger.log(
            "INFO",
            "Test message",
            user_id="user-123",
            action="create",
            resource="template"
        )

        # Assert
        assert len(execution_logger.logs) == 1
        log = execution_logger.logs[0]
        assert log["user_id"] == "user-123"
        assert log["action"] == "create"
        assert log["resource"] == "template"

    @patch('app.services.automation_execution_logger.logger')
    def test_log_lowercase_level(self, mock_logger, execution_logger):
        """測試：小寫日誌級別會被轉換為大寫"""
        # Act
        execution_logger.log("info", "Test message")

        # Assert
        assert execution_logger.logs[0]["level"] == "INFO"


# ============================================================================
# 便利方法測試
# ============================================================================

@pytest.mark.unit
class TestConvenienceMethods:
    """便利方法測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_info_method(self, mock_logger, execution_logger):
        """測試：info 便利方法"""
        # Act
        execution_logger.info("Info message", key="value")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "INFO"
        assert execution_logger.logs[0]["message"] == "Info message"
        assert execution_logger.logs[0]["key"] == "value"

    @patch('app.services.automation_execution_logger.logger')
    def test_warning_method(self, mock_logger, execution_logger):
        """測試：warning 便利方法"""
        # Act
        execution_logger.warning("Warning message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "WARNING"

    @patch('app.services.automation_execution_logger.logger')
    def test_error_method(self, mock_logger, execution_logger):
        """測試：error 便利方法"""
        # Act
        execution_logger.error("Error message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "ERROR"

    @patch('app.services.automation_execution_logger.logger')
    def test_debug_method(self, mock_logger, execution_logger):
        """測試：debug 便利方法"""
        # Act
        execution_logger.debug("Debug message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "DEBUG"


# ============================================================================
# 日誌查詢測試
# ============================================================================

@pytest.mark.unit
class TestLogRetrieval:
    """日誌查詢測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_get_logs_empty(self, mock_logger, execution_logger):
        """測試：獲取空日誌列表"""
        # Act
        logs = execution_logger.get_logs()

        # Assert
        assert logs == []

    @patch('app.services.automation_execution_logger.logger')
    def test_get_logs_with_entries(self, mock_logger, execution_logger):
        """測試：獲取有條目的日誌列表"""
        # Arrange
        execution_logger.info("Message 1")
        execution_logger.warning("Message 2")
        execution_logger.error("Message 3")

        # Act
        logs = execution_logger.get_logs()

        # Assert
        assert len(logs) == 3
        assert logs[0]["message"] == "Message 1"
        assert logs[1]["message"] == "Message 2"
        assert logs[2]["message"] == "Message 3"

    @patch('app.services.automation_execution_logger.logger')
    def test_get_logs_preserves_order(self, mock_logger, execution_logger):
        """測試：獲取日誌保持順序"""
        # Arrange
        for i in range(5):
            execution_logger.info(f"Message {i}")

        # Act
        logs = execution_logger.get_logs()

        # Assert
        assert len(logs) == 5
        for i, log in enumerate(logs):
            assert log["message"] == f"Message {i}"


# ============================================================================
# 元數據轉換測試
# ============================================================================

@pytest.mark.unit
class TestMetadataConversion:
    """元數據轉換測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_to_metadata_empty_logs(self, mock_logger, execution_logger):
        """測試：空日誌轉換為元數據"""
        # Act
        metadata = execution_logger.to_metadata()

        # Assert
        assert metadata["execution_logs"] == []
        assert metadata["total_logs"] == 0
        assert metadata["log_levels"] == []
        assert metadata["has_errors"] is False
        assert metadata["has_warnings"] is False

    @patch('app.services.automation_execution_logger.logger')
    def test_to_metadata_with_logs(self, mock_logger, execution_logger):
        """測試：有日誌轉換為元數據"""
        # Arrange
        execution_logger.info("Info message")
        execution_logger.warning("Warning message")
        execution_logger.error("Error message")

        # Act
        metadata = execution_logger.to_metadata()

        # Assert
        assert metadata["total_logs"] == 3
        assert set(metadata["log_levels"]) == {"INFO", "WARNING", "ERROR"}
        assert metadata["has_errors"] is True
        assert metadata["has_warnings"] is True

    @patch('app.services.automation_execution_logger.logger')
    def test_to_metadata_only_info_logs(self, mock_logger, execution_logger):
        """測試：只有 INFO 日誌的元數據"""
        # Arrange
        execution_logger.info("Info message 1")
        execution_logger.info("Info message 2")

        # Act
        metadata = execution_logger.to_metadata()

        # Assert
        assert metadata["total_logs"] == 2
        assert metadata["log_levels"] == ["INFO"]
        assert metadata["has_errors"] is False
        assert metadata["has_warnings"] is False

    @patch('app.services.automation_execution_logger.logger')
    def test_to_metadata_warnings_only(self, mock_logger, execution_logger):
        """測試：只有警告的元數據"""
        # Arrange
        execution_logger.warning("Warning 1")
        execution_logger.warning("Warning 2")

        # Act
        metadata = execution_logger.to_metadata()

        # Assert
        assert metadata["has_errors"] is False
        assert metadata["has_warnings"] is True


# ============================================================================
# 日誌摘要測試
# ============================================================================

@pytest.mark.unit
class TestLogSummary:
    """日誌摘要測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_empty(self, mock_logger, execution_logger):
        """測試：空日誌的摘要"""
        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert summary == "共 0 條日誌"

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_info_only(self, mock_logger, execution_logger):
        """測試：只有 INFO 日誌的摘要"""
        # Arrange
        execution_logger.info("Info 1")
        execution_logger.info("Info 2")
        execution_logger.info("Info 3")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert summary == "共 3 條日誌"

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_errors(self, mock_logger, execution_logger):
        """測試：帶錯誤的摘要"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.error("Error 1")
        execution_logger.error("Error 2")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "共 3 條日誌" in summary
        assert "2 個錯誤" in summary

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_warnings(self, mock_logger, execution_logger):
        """測試：帶警告的摘要"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.warning("Warning 1")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "共 2 條日誌" in summary
        assert "1 個警告" in summary

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_errors_and_warnings(self, mock_logger, execution_logger):
        """測試：帶錯誤和警告的摘要"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.warning("Warning 1")
        execution_logger.warning("Warning 2")
        execution_logger.error("Error 1")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "共 4 條日誌" in summary
        assert "1 個錯誤" in summary
        assert "2 個警告" in summary


# ============================================================================
# 時間戳測試
# ============================================================================

@pytest.mark.unit
class TestTimestamp:
    """時間戳測試"""

    @patch('app.services.automation_execution_logger.logger')
    @patch('app.services.automation_execution_logger.datetime')
    def test_log_timestamp_format(self, mock_datetime, mock_logger, execution_logger):
        """測試：日誌時間戳格式正確"""
        # Arrange
        fixed_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = fixed_time

        # Act
        execution_logger.info("Test message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["timestamp"] == "2025-01-01T12:00:00"


# ============================================================================
# 多次日誌記錄測試
# ============================================================================

@pytest.mark.unit
class TestMultipleLogEntries:
    """多次日誌記錄測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_multiple_log_entries_accumulate(self, mock_logger, execution_logger):
        """測試：多次日誌記錄會累積"""
        # Act
        for i in range(10):
            execution_logger.info(f"Message {i}")

        # Assert
        assert len(execution_logger.logs) == 10
        assert mock_logger.info.call_count == 10

    @patch('app.services.automation_execution_logger.logger')
    def test_mixed_level_logs(self, mock_logger, execution_logger):
        """測試：混合級別的日誌記錄"""
        # Act
        execution_logger.info("Info")
        execution_logger.debug("Debug")
        execution_logger.warning("Warning")
        execution_logger.error("Error")
        execution_logger.info("Info 2")

        # Assert
        assert len(execution_logger.logs) == 5
        levels = [log["level"] for log in execution_logger.logs]
        assert levels == ["INFO", "DEBUG", "WARNING", "ERROR", "INFO"]


# ============================================================================
# 邊界情況測試
# ============================================================================

@pytest.mark.unit
class TestEdgeCases:
    """邊界情況測試"""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_empty_message(self, mock_logger, execution_logger):
        """測試：空消息的日誌"""
        # Act
        execution_logger.info("")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["message"] == ""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_special_characters(self, mock_logger, execution_logger):
        """測試：特殊字符的日誌"""
        # Act
        execution_logger.info("Message with 中文 and émojis 🎉")

        # Assert
        assert len(execution_logger.logs) == 1
        assert "中文" in execution_logger.logs[0]["message"]
        assert "🎉" in execution_logger.logs[0]["message"]

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_none_context_value(self, mock_logger, execution_logger):
        """測試：None 值的上下文"""
        # Act
        execution_logger.info("Message", key1=None, key2="value")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["key1"] is None
        assert execution_logger.logs[0]["key2"] == "value"

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_complex_context_values(self, mock_logger, execution_logger):
        """測試：複雜類型的上下文值"""
        # Act
        execution_logger.info(
            "Message",
            list_value=[1, 2, 3],
            dict_value={"key": "value"},
            int_value=123,
            float_value=45.67
        )

        # Assert
        log = execution_logger.logs[0]
        assert log["list_value"] == [1, 2, 3]
        assert log["dict_value"] == {"key": "value"}
        assert log["int_value"] == 123
        assert log["float_value"] == 45.67
