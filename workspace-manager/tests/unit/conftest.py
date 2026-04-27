"""UnitTest共用Settingsand Mock Fixtures"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

# SetupTestEnvironment
os.environ.setdefault("ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db import models as db_models


# ============================================================================
# Database Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.count.return_value = 0
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    session.delete = MagicMock()
    session.flush = MagicMock()
    return session


# ============================================================================
# Outside部Service Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis 客Household端"""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.ttl.return_value = -1
    redis_mock.hget.return_value = None
    redis_mock.hset.return_value = True
    redis_mock.hdel.return_value = 1
    return redis_mock


@pytest.fixture
def mock_git_service():
    """Mock Git Service"""
    git_mock = MagicMock()
    git_mock.init_repo.return_value = True
    git_mock.get_status.return_value = {"modified": [], "untracked": [], "staged": []}
    git_mock.commit.return_value = "commit-hash-123"
    git_mock.create_branch.return_value = True
    git_mock.checkout.return_value = True
    git_mock.push.return_value = True
    git_mock.pull.return_value = True
    git_mock.clone.return_value = True
    return git_mock


@pytest.fixture
def mock_docker_client():
    """Mock Docker Client"""
    docker_mock = MagicMock()
    docker_mock.images.build.return_value = (MagicMock(id="image-id-123"), [])
    docker_mock.images.push.return_value = "pushed"
    docker_mock.images.get.return_value = MagicMock(
        id="image-id-123",
        tags=["test:latest"]
    )
    docker_mock.containers.run.return_value = MagicMock(
        id="container-id-123",
        status="running"
    )
    docker_mock.containers.get.return_value = MagicMock(
        id="container-id-123",
        status="running"
    )
    return docker_mock


@pytest.fixture
def mock_celery_app():
    """Mock Celery Application"""
    celery_mock = MagicMock()
    celery_mock.send_task.return_value = MagicMock(id="task-id-123")

    task_mock = MagicMock()
    task_mock.apply_async.return_value = MagicMock(
        id="task-id-123",
        status="PENDING"
    )
    celery_mock.tasks = {"test_task": task_mock}

    return celery_mock


@pytest.fixture
def mock_filesystem():
    """Mock DocumentSystemOperation"""
    fs_mock = MagicMock()
    fs_mock.exists.return_value = True
    fs_mock.is_file.return_value = True
    fs_mock.is_dir.return_value = True
    fs_mock.read_text.return_value = ""
    fs_mock.write_text.return_value = None
    fs_mock.mkdir.return_value = None
    fs_mock.unlink.return_value = None
    fs_mock.rmdir.return_value = None
    return fs_mock


# ============================================================================
# DataFactory Fixtures
# ============================================================================

@pytest.fixture
def user_factory():
    """UserFactory"""
    _counter = 0

    def create_user(**kwargs) -> db_models.User:
        nonlocal _counter
        _counter += 1

        defaults = {
            "id": kwargs.get("id", f"user-{_counter}"),
            "username": kwargs.get("username", f"testuser-{_counter}"),
            "email": kwargs.get("email", f"testuser-{_counter}@example.com"),
            "first_name": kwargs.get("first_name", "Test"),
            "last_name": kwargs.get("last_name", f"User{_counter}"),
            "display_name": kwargs.get("display_name", f"Test User {_counter}"),
            "avatar_url": kwargs.get("avatar_url"),
            "is_active": kwargs.get("is_active", True),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        user = db_models.User(**defaults)
        return user

    return create_user


@pytest.fixture
def team_factory():
    """TeamFactory"""
    _counter = 0

    def create_team(**kwargs) -> db_models.Team:
        nonlocal _counter
        _counter += 1

        defaults = {
            "id": kwargs.get("id", f"team-{_counter}"),
            "name": kwargs.get("name", f"Test Team {_counter}"),
            "description": kwargs.get("description", "Test team description"),
            "owner_id": kwargs.get("owner_id", "user-1"),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        team = db_models.Team(**defaults)
        return team

    return create_team


@pytest.fixture
def workspace_factory():
    """WorkspaceFactory"""
    _counter = 0

    def create_workspace(**kwargs) -> db_models.Workspace:
        nonlocal _counter
        _counter += 1

        defaults = {
            "id": kwargs.get("id", f"workspace-{_counter}"),
            "name": kwargs.get("name", f"Test Workspace {_counter}"),
            "description": kwargs.get("description", "Test workspace description"),
            "owner_id": kwargs.get("owner_id", "user-1"),
            "owner_type": kwargs.get("owner_type", "user"),
            "visibility": kwargs.get("visibility", "private"),
            "status": kwargs.get("status", "active"),
            "runtime_id": kwargs.get("runtime_id"),
            "template_id": kwargs.get("template_id"),
            "settings": kwargs.get("settings", {}),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        workspace = db_models.Workspace(**defaults)
        return workspace

    return create_workspace


@pytest.fixture
def template_factory():
    """TemplateFactory"""
    _counter = 0

    def create_template(**kwargs) -> db_models.Template:
        nonlocal _counter
        _counter += 1

        defaults = {
            "id": kwargs.get("id", f"template-{_counter}"),
            "name": kwargs.get("name", f"Test Template {_counter}"),
            "description": kwargs.get("description", "Test template description"),
            "version": kwargs.get("version", "1.0.0"),
            "owner_id": kwargs.get("owner_id", "user-1"),
            "visibility": kwargs.get("visibility", "private"),
            "category": kwargs.get("category", "general"),
            "config": kwargs.get("config", {}),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        template = db_models.Template(**defaults)
        return template

    return create_template


@pytest.fixture
def automation_factory():
    """自動化TaskFactory"""
    _counter = 0

    def create_automation(**kwargs) -> db_models.Automation:
        nonlocal _counter
        _counter += 1

        defaults = {
            "id": kwargs.get("id", f"automation-{_counter}"),
            "name": kwargs.get("name", f"Test Automation {_counter}"),
            "description": kwargs.get("description", "Test automation description"),
            "workspace_id": kwargs.get("workspace_id", "workspace-1"),
            "trigger_type": kwargs.get("trigger_type", "manual"),
            "trigger_config": kwargs.get("trigger_config", {}),
            "action_type": kwargs.get("action_type", "script"),
            "action_config": kwargs.get("action_config", {}),
            "status": kwargs.get("status", "active"),
            "created_at": kwargs.get("created_at", datetime.now()),
            "updated_at": kwargs.get("updated_at", datetime.now()),
        }

        automation = db_models.Automation(**defaults)
        return automation

    return create_automation


@pytest.fixture
def token_factory():
    """Token Factory"""
    _counter = 0

    def create_token(**kwargs) -> dict[str, Any]:
        nonlocal _counter
        _counter += 1

        return {
            "access_token": kwargs.get("access_token", f"access-token-{_counter}"),
            "refresh_token": kwargs.get("refresh_token", f"refresh-token-{_counter}"),
            "token_type": kwargs.get("token_type", "Bearer"),
            "expires_in": kwargs.get("expires_in", 3600),
            "expires_at": kwargs.get("expires_at", datetime.now() + timedelta(hours=1)),
            "user_id": kwargs.get("user_id", f"user-{_counter}"),
        }

    return create_token


# ============================================================================
# Mock OAuth Back應
# ============================================================================

@pytest.fixture
def mock_oauth_response():
    """Mock OAuth Back應"""
    return {
        "access_token": "oauth-access-token",
        "refresh_token": "oauth-refresh-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "read write",
        "user": {
            "id": "oauth-user-123",
            "email": "oauth@example.com",
            "name": "OAuth User",
            "avatar_url": "https://example.com/avatar.jpg",
        }
    }


@pytest.fixture
def mock_oauth_user_info():
    """Mock OAuth UserInformation"""
    return {
        "id": "oauth-user-123",
        "email": "oauth@example.com",
        "name": "OAuth User",
        "username": "oauthuser",
        "avatar_url": "https://example.com/avatar.jpg",
        "verified": True,
    }


# ============================================================================
# CommonTest輔助
# ============================================================================

@pytest.fixture
def mock_datetime():
    """Mock datetime 以便TestTimeRelatedFunction"""
    test_now = datetime(2025, 1, 1, 12, 0, 0)

    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = test_now
        mock_dt.utcnow.return_value = test_now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield mock_dt


@pytest.fixture
def mock_uuid():
    """Mock UUID Generating以便Test"""
    _counter = 0

    def mock_uuid4():
        nonlocal _counter
        _counter += 1
        mock = MagicMock()
        mock.hex = f"uuid{_counter:032d}"
        return mock

    with patch("uuid.uuid4", side_effect=mock_uuid4):
        yield


@pytest.fixture
def request_factory():
    """Create具備一致 state / headers Structure的 Request mock"""

    def build_request(
        path: str, headers: dict[str, str] | None = None, method: str = "GET"
    ) -> Mock:
        request = Mock(spec=Request)
        request.url = Mock(path=path)
        request.method = method
        request.headers = headers or {}
        request.state = SimpleNamespace()
        return request

    return build_request


@pytest.fixture
def httpx_response_factory():
    """Create可客製化的 httpx Back應 mock"""

    def build_response(
        *,
        status_code: int = 200,
        json_data: Any | None = None,
        text: str = "",
        raise_error: Exception | None = None,
        headers: dict[str, str] | None = None,
    ) -> Mock:
        response = Mock()
        response.status_code = status_code
        response.text = text
        response.headers = headers or {"content-type": "application/json"}
        response.json = Mock(return_value=json_data if json_data is not None else {"success": True})
        response.raise_for_status = Mock()
        if raise_error is not None:
            response.raise_for_status.side_effect = raise_error
        return response

    return build_response


@pytest.fixture
def upload_file_factory():
    """Create具備固定 filename/read 介Surface的 UploadFile mock"""

    def build_upload_file(filename: str, content: bytes) -> AsyncMock:
        file = AsyncMock()
        file.filename = filename
        file.read = AsyncMock(return_value=content)
        return file

    return build_upload_file


# ============================================================================
# TestMarkConfiguration
# ============================================================================

def pytest_configure(config):
    """ConfigurationUnitTestMark"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "auth: marks tests as authentication tests"
    )
    config.addinivalue_line(
        "markers", "workspace: marks tests as workspace tests"
    )
    config.addinivalue_line(
        "markers", "template: marks tests as template tests"
    )
    config.addinivalue_line(
        "markers", "automation: marks tests as automation tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "high_priority: marks high priority tests"
    )
