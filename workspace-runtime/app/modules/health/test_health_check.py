"""健康檢查服務測試

直接測試 health check service，不依賴其他模組以避免循環導入
"""

from __future__ import annotations

import socket
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 直接導入需要的模組，避免循環導入
import sys
from pathlib import Path

# 確保可以導入 app 模組
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from app.database.models import Base, User, Workspace
from app.modules.health.service import HealthCheckService


@pytest.fixture
def test_db():
    """創建測試資料庫"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()
    
    # 創建測試用戶
    user = User(
        id="test-user-1",
        username="testuser",
        email="test@example.com",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    
    # 創建測試 workspace
    workspace = Workspace(
        id="test-workspace-1",
        name="Test Workspace",
        owner_id="test-user-1",
        runtime_status="stopped",
        runtime_container_id=None,
        runtime_last_seen=None,
        created_at=datetime.utcnow(),
    )
    db.add(workspace)
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(engine)


class MockSettings:
    """模擬設定類別"""
    WORKSPACE_ID = "test-workspace-1"
    DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def mock_settings():
    """模擬設定"""
    settings = MockSettings()
    with patch("app.modules.health.service.get_settings", return_value=settings):
        yield settings


def test_get_container_id(test_db, mock_settings):
    """測試獲取容器 ID"""
    service = HealthCheckService(test_db)
    container_id = service.get_container_id()

    # 應該返回 hostname
    assert container_id == socket.gethostname()


def test_check_and_update_workspace_status_first_time(test_db, mock_settings):
    """測試首次健康檢查時更新狀態"""
    service = HealthCheckService(test_db)
    
    with patch.object(service, "get_container_id", return_value="test-container-123"):
        result = service.check_and_update_workspace_status()
    
    # 檢查返回結果
    assert result["status"] == "healthy"
    assert result["workspace_id"] == "test-workspace-1"
    assert result["container_id"] == "test-container-123"
    assert result["runtime_status"] == "running"
    assert result["updated"] is True
    
    # 檢查資料庫更新
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    assert workspace.runtime_status == "running"
    assert workspace.runtime_container_id == "test-container-123"
    assert workspace.runtime_last_seen is not None


def test_check_and_update_workspace_status_already_running(test_db, mock_settings):
    """測試當狀態已經是 running 時的健康檢查"""
    # 先設定為 running
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "test-container-123"
    test_db.commit()

    service = HealthCheckService(test_db)

    with patch.object(service, "get_container_id", return_value="test-container-123"):
        result = service.check_and_update_workspace_status()

    # 檢查返回結果
    assert result["status"] == "healthy"
    assert result["runtime_status"] == "running"
    assert result["updated"] is True  # last_seen 仍會更新


def test_check_and_update_workspace_status_container_id_changed(test_db, mock_settings):
    """測試容器 ID 變更時的健康檢查"""
    # 先設定舊的容器 ID
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "old-container-123"
    test_db.commit()

    service = HealthCheckService(test_db)

    with patch.object(service, "get_container_id", return_value="new-container-456"):
        result = service.check_and_update_workspace_status()

    # 檢查返回結果
    assert result["status"] == "healthy"
    assert result["container_id"] == "new-container-456"
    assert result["updated"] is True

    # 檢查資料庫更新
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    assert workspace.runtime_container_id == "new-container-456"


def test_check_and_update_workspace_status_workspace_not_found(test_db):
    """測試找不到 workspace 的情況"""
    settings = MockSettings()
    settings.WORKSPACE_ID = "non-existent-workspace"

    with patch("app.modules.health.service.get_settings", return_value=settings):
        service = HealthCheckService(test_db)
        result = service.check_and_update_workspace_status()

    # 檢查返回結果
    assert result["status"] == "unhealthy"
    assert "Workspace not found" in result["error"]


def test_check_and_update_workspace_status_database_error(test_db, mock_settings):
    """測試資料庫錯誤的情況"""
    service = HealthCheckService(test_db)

    # 模擬資料庫錯誤
    with patch.object(test_db, "query", side_effect=Exception("Database connection failed")):
        result = service.check_and_update_workspace_status()

    # 檢查返回結果
    assert result["status"] == "degraded"
    assert "Database connection failed" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

