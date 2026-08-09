"""Tests for app/models/common.py"""

from datetime import UTC, datetime
from app.core.models import APIResponse, TimestampMixin


class TestAPIResponse:
    """Test cases for APIResponse model"""

    def test_default_values(self):
        """Test APIResponse with default values"""
        response = APIResponse()

        assert response.status == "success"
        assert response.message is None

    def test_custom_status(self):
        """Test APIResponse with custom status"""
        response = APIResponse(status="error")

        assert response.status == "error"
        assert response.message is None

    def test_with_message(self):
        """Test APIResponse with message"""
        response = APIResponse(message="Operation completed")

        assert response.status == "success"
        assert response.message == "Operation completed"

    def test_custom_status_and_message(self):
        """Test APIResponse with custom status and message"""
        response = APIResponse(status="error", message="Something went wrong")

        assert response.status == "error"
        assert response.message == "Something went wrong"

    def test_dict_serialization(self):
        """Test APIResponse serialization to dict"""
        response = APIResponse(status="success", message="Test message")
        response_dict = response.model_dump()

        assert response_dict == {"status": "success", "message": "Test message"}

    def test_json_serialization(self):
        """Test APIResponse serialization to JSON"""
        response = APIResponse(status="error", message="Error occurred")
        json_str = response.model_dump_json()

        assert '"status":"error"' in json_str
        assert '"message":"Error occurred"' in json_str

    def test_from_dict(self):
        """Test creating APIResponse from dict"""
        data = {"status": "warning", "message": "Warning message"}
        response = APIResponse(**data)

        assert response.status == "warning"
        assert response.message == "Warning message"


class TestTimestampMixin:
    """Test cases for TimestampMixin model"""

    def test_auto_timestamps(self):
        """Test that timestamps are automatically set"""
        timestamp = TimestampMixin()

        assert isinstance(timestamp.created_at, datetime)
        assert isinstance(timestamp.updated_at, datetime)

    def test_timestamps_are_recent(self):
        """Test that auto-generated timestamps are recent"""
        before = datetime.now(UTC)
        timestamp = TimestampMixin()
        after = datetime.now(UTC)

        assert before <= timestamp.created_at <= after
        assert before <= timestamp.updated_at <= after

    def test_custom_timestamps(self):
        """Test TimestampMixin with custom timestamps"""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        timestamp = TimestampMixin(created_at=custom_time, updated_at=custom_time)

        assert timestamp.created_at == custom_time
        assert timestamp.updated_at == custom_time

    def test_different_timestamps(self):
        """Test TimestampMixin with different created_at and updated_at"""
        created = datetime(2024, 1, 1, 12, 0, 0)
        updated = datetime(2024, 1, 2, 12, 0, 0)

        timestamp = TimestampMixin(created_at=created, updated_at=updated)

        assert timestamp.created_at == created
        assert timestamp.updated_at == updated
        assert timestamp.updated_at > timestamp.created_at

    def test_dict_serialization(self):
        """Test TimestampMixin serialization to dict"""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        timestamp = TimestampMixin(created_at=custom_time, updated_at=custom_time)

        timestamp_dict = timestamp.model_dump()

        assert "created_at" in timestamp_dict
        assert "updated_at" in timestamp_dict
        assert timestamp_dict["created_at"] == custom_time
        assert timestamp_dict["updated_at"] == custom_time

    def test_orm_mode_config(self):
        """Test that orm_mode is configured"""
        config = TimestampMixin.model_config

        # In Pydantic v2, orm_mode is replaced with from_attributes
        assert config.get("from_attributes") or hasattr(
            TimestampMixin.Config, "orm_mode"
        )

    def test_json_serialization(self):
        """Test TimestampMixin JSON serialization"""
        timestamp = TimestampMixin()
        json_str = timestamp.model_dump_json()

        assert "created_at" in json_str
        assert "updated_at" in json_str

    def test_from_dict(self):
        """Test creating TimestampMixin from dict"""
        created = datetime(2024, 1, 1, 12, 0, 0)
        updated = datetime(2024, 1, 2, 12, 0, 0)

        data = {"created_at": created, "updated_at": updated}

        timestamp = TimestampMixin(**data)

        assert timestamp.created_at == created
        assert timestamp.updated_at == updated


class TestIntegration:
    """Integration tests for common models"""

    def test_combining_models(self):
        """Test that common models can be combined via inheritance"""

        class CustomModel(TimestampMixin):
            status: str = "active"

        model = CustomModel()

        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")
        assert model.status == "active"

    def test_api_response_in_dict(self):
        """Test APIResponse can be used in nested structures"""
        response = APIResponse(status="success", message="Data retrieved")

        result = {"response": response.model_dump(), "data": {"key": "value"}}

        assert result["response"]["status"] == "success"
        assert result["response"]["message"] == "Data retrieved"

    def test_timestamp_comparison(self):
        """Test timestamp comparison"""
        first = TimestampMixin()
        # Small delay to ensure different timestamps
        import time

        time.sleep(0.001)
        second = TimestampMixin()

        assert second.created_at >= first.created_at
