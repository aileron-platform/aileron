"""Unit Tests for AutomationExecutionLogger"""

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
    """Basic Execution Logger"""
    return AutomationExecutionLogger(
        execution_id="exec-123",
        job_id="job-123"
    )


@pytest.fixture
def execution_logger_with_workspace():
    """Execution Logger With Workspace"""
    return AutomationExecutionLogger(
        execution_id="exec-456",
        job_id="job-456",
        workspace_id="ws-123"
    )


# ============================================================================
# Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestLoggerInitialization:
    """Logger Initialization Tests"""

    def test_init_without_workspace(self):
        """Test: Initialize Without Workspace"""
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
        """Test: Initialize With Workspace"""
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
# Logging Tests
# ============================================================================

@pytest.mark.unit
class TestLogging:
    """Logging Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_info_level(self, mock_logger, execution_logger):
        """Test: Record INFO Level Log"""
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
        """Test: Record WARNING Level Log"""
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
        """Test: Record ERROR Level Log"""
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
        """Test: Record DEBUG Level Log"""
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
        """Test: Record Log With Workspace ID"""
        # Act
        execution_logger_with_workspace.log("INFO", "Test message")

        # Assert
        assert len(execution_logger_with_workspace.logs) == 1
        log = execution_logger_with_workspace.logs[0]
        assert log["workspace_id"] == "ws-123"

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_multiple_context(self, mock_logger, execution_logger):
        """Test: Record Log With Multiple Contexts"""
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
        """Test: Lowercase Log Level Will Be Converted to Uppercase"""
        # Act
        execution_logger.log("info", "Test message")

        # Assert
        assert execution_logger.logs[0]["level"] == "INFO"


# ============================================================================
# Convenience Method Tests
# ============================================================================

@pytest.mark.unit
class TestConvenienceMethods:
    """Convenience Method Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_info_method(self, mock_logger, execution_logger):
        """Test: info Convenience Method"""
        # Act
        execution_logger.info("Info message", key="value")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "INFO"
        assert execution_logger.logs[0]["message"] == "Info message"
        assert execution_logger.logs[0]["key"] == "value"

    @patch('app.services.automation_execution_logger.logger')
    def test_warning_method(self, mock_logger, execution_logger):
        """Test: warning Convenience Method"""
        # Act
        execution_logger.warning("Warning message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "WARNING"

    @patch('app.services.automation_execution_logger.logger')
    def test_error_method(self, mock_logger, execution_logger):
        """Test: error Convenience Method"""
        # Act
        execution_logger.error("Error message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "ERROR"

    @patch('app.services.automation_execution_logger.logger')
    def test_debug_method(self, mock_logger, execution_logger):
        """Test: debug Convenience Method"""
        # Act
        execution_logger.debug("Debug message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["level"] == "DEBUG"


# ============================================================================
# Log Query Tests
# ============================================================================

@pytest.mark.unit
class TestLogRetrieval:
    """Log Query Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_get_logs_empty(self, mock_logger, execution_logger):
        """Test: Get Empty Log List"""
        # Act
        logs = execution_logger.get_logs()

        # Assert
        assert logs == []

    @patch('app.services.automation_execution_logger.logger')
    def test_get_logs_with_entries(self, mock_logger, execution_logger):
        """Test: Get Log List With Entries"""
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
        """Test: Get Logs Maintain Order"""
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
# Metadata Conversion Tests
# ============================================================================

@pytest.mark.unit
class TestMetadataConversion:
    """Metadata Conversion Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_to_metadata_empty_logs(self, mock_logger, execution_logger):
        """Test: Empty Logs Convert to Metadata"""
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
        """Test: Logs With Metadata Conversion"""
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
        """Test: Metadata With Only INFO Logs"""
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
        """Test: Metadata With Only Warnings"""
        # Arrange
        execution_logger.warning("Warning 1")
        execution_logger.warning("Warning 2")

        # Act
        metadata = execution_logger.to_metadata()

        # Assert
        assert metadata["has_errors"] is False
        assert metadata["has_warnings"] is True


# ============================================================================
# Log Summary Tests
# ============================================================================

@pytest.mark.unit
class TestLogSummary:
    """Log Summary Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_empty(self, mock_logger, execution_logger):
        """Test: Summary of Empty Logs"""
        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert summary == "Total 0 logs"

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_info_only(self, mock_logger, execution_logger):
        """Test: Summary With Only INFO Logs"""
        # Arrange
        execution_logger.info("Info 1")
        execution_logger.info("Info 2")
        execution_logger.info("Info 3")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert summary == "Total 3 logs"

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_errors(self, mock_logger, execution_logger):
        """Test: Summary With Errors"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.error("Error 1")
        execution_logger.error("Error 2")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "Total 3 logs" in summary
        assert "2 errors" in summary

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_warnings(self, mock_logger, execution_logger):
        """Test: Summary With Warnings"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.warning("Warning 1")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "Total 2 logs" in summary
        assert "1 warning" in summary

    @patch('app.services.automation_execution_logger.logger')
    def test_get_summary_with_errors_and_warnings(self, mock_logger, execution_logger):
        """Test: Summary With Errors and Warnings"""
        # Arrange
        execution_logger.info("Info")
        execution_logger.warning("Warning 1")
        execution_logger.warning("Warning 2")
        execution_logger.error("Error 1")

        # Act
        summary = execution_logger.get_summary()

        # Assert
        assert "Total 4 logs" in summary
        assert "1 error" in summary
        assert "2 warnings" in summary


# ============================================================================
# Timestamp Tests
# ============================================================================

@pytest.mark.unit
class TestTimestamp:
    """Timestamp Tests"""

    @patch('app.services.automation_execution_logger.logger')
    @patch('app.services.automation_execution_logger.datetime')
    def test_log_timestamp_format(self, mock_datetime, mock_logger, execution_logger):
        """Test: Log Timestamp Format Correct"""
        # Arrange
        fixed_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = fixed_time

        # Act
        execution_logger.info("Test message")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["timestamp"] == "2025-01-01T12:00:00"


# ============================================================================
# Multiple Log Entry Tests
# ============================================================================

@pytest.mark.unit
class TestMultipleLogEntries:
    """Multiple Log Entry Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_multiple_log_entries_accumulate(self, mock_logger, execution_logger):
        """Test: Multiple Log Entries Will Accumulate"""
        # Act
        for i in range(10):
            execution_logger.info(f"Message {i}")

        # Assert
        assert len(execution_logger.logs) == 10
        assert mock_logger.info.call_count == 10

    @patch('app.services.automation_execution_logger.logger')
    def test_mixed_level_logs(self, mock_logger, execution_logger):
        """Test: Mixed Level Log Entries"""
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
# Edge Case Tests
# ============================================================================

@pytest.mark.unit
class TestEdgeCases:
    """Edge Case Tests"""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_empty_message(self, mock_logger, execution_logger):
        """Test: Log With Empty Message"""
        # Act
        execution_logger.info("")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["message"] == ""

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_special_characters(self, mock_logger, execution_logger):
        """Test: Log With Special Characters"""
        # Act
        execution_logger.info("Message with Chinese and émojis 🎉")

        # Assert
        assert len(execution_logger.logs) == 1
        assert "Chinese" in execution_logger.logs[0]["message"]
        assert "🎉" in execution_logger.logs[0]["message"]

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_none_context_value(self, mock_logger, execution_logger):
        """Test: None Value Context"""
        # Act
        execution_logger.info("Message", key1=None, key2="value")

        # Assert
        assert len(execution_logger.logs) == 1
        assert execution_logger.logs[0]["key1"] is None
        assert execution_logger.logs[0]["key2"] == "value"

    @patch('app.services.automation_execution_logger.logger')
    def test_log_with_complex_context_values(self, mock_logger, execution_logger):
        """Test: Complex Type Context Values"""
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
