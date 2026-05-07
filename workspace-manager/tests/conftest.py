"""Common test configurations"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Tests must force using standalone SQLite to avoid container environment variables directing tests to shared PostgreSQL.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "testing"

from app.db import models as db_models
from app.db.database import Base, get_db
from app.db.seed import (
    create_default_model_configs,
    create_default_template_categories,
    create_default_template_features,
)
from app.main import app
from app.config.settings import get_settings

# Import test helper utilities
from tests.helpers.auth_helpers import AuthTestHelper
from tests.helpers.fixtures import TestDataFactory, MockResponses
from tests.helpers.workspace_helpers import WorkspaceTestHelper
from tests.helpers.container_helpers import ContainerTestHelper
from tests.helpers.i18n_helpers import I18nTestHelper, get_i18n_test_helper


@pytest.fixture()
def test_app(tmp_path: Path) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    """Provide FastAPI client and database Session factory for testing

    Improvements:
    1. Use tmp_path as database path
    2. Use tmp_path as template storage path
    3. Ensure complete test isolation without polluting the real environment
    """

    # Set up temporary template storage path
    template_storage_path = tmp_path / "template-storage"
    template_storage_path.mkdir(parents=True, exist_ok=True)
    marketplace_storage_path = tmp_path / "marketplace-storage"
    marketplace_storage_path.mkdir(parents=True, exist_ok=True)
    knowledge_bases_path = tmp_path / "knowledge-bases"
    knowledge_bases_path.mkdir(parents=True, exist_ok=True)

    # Create plugins directory (required by template service)
    plugins_dir = template_storage_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # Preserve original environment variables
    original_template_path = os.environ.get("TEMPLATE_STORAGE_PATH")
    original_marketplace_path = os.environ.get("MARKETPLACE_STORAGE_PATH")
    original_manager_kb_path = os.environ.get("MANAGER_KNOWLEDGE_BASES_DIR")
    original_host_kb_path = os.environ.get("HOST_KNOWLEDGE_BASES_DIR")

    # Set up test environment variables
    os.environ["TEMPLATE_STORAGE_PATH"] = str(template_storage_path)
    os.environ["MARKETPLACE_STORAGE_PATH"] = str(marketplace_storage_path)
    os.environ["MANAGER_KNOWLEDGE_BASES_DIR"] = str(knowledge_bases_path)
    os.environ["HOST_KNOWLEDGE_BASES_DIR"] = str(knowledge_bases_path)

    # Clear settings cache to apply new environment variables
    get_settings.cache_clear()

    # Set up test database
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Preload necessary seed data for test database.
    with TestingSessionLocal() as seed_db:
        create_default_model_configs(seed_db)
        create_default_template_categories(seed_db)
        create_default_template_features(seed_db)
        seed_db.commit()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            # Set English locale for all test requests to ensure consistent test results
            client.headers.update({"Accept-Language": "en", "X-Language": "en"})
            yield client, TestingSessionLocal
    finally:
        # Cleanup
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        # Restore original environment variables
        if original_template_path is not None:
            os.environ["TEMPLATE_STORAGE_PATH"] = original_template_path
        else:
            os.environ.pop("TEMPLATE_STORAGE_PATH", None)
        if original_marketplace_path is not None:
            os.environ["MARKETPLACE_STORAGE_PATH"] = original_marketplace_path
        else:
            os.environ.pop("MARKETPLACE_STORAGE_PATH", None)
        if original_manager_kb_path is not None:
            os.environ["MANAGER_KNOWLEDGE_BASES_DIR"] = original_manager_kb_path
        else:
            os.environ.pop("MANAGER_KNOWLEDGE_BASES_DIR", None)
        if original_host_kb_path is not None:
            os.environ["HOST_KNOWLEDGE_BASES_DIR"] = original_host_kb_path
        else:
            os.environ.pop("HOST_KNOWLEDGE_BASES_DIR", None)

        # Clear cache again
        get_settings.cache_clear()


@pytest.fixture()
def create_user(test_app: tuple[TestClient, sessionmaker[Session]]) -> Callable[..., db_models.User]:
    """Create test user"""

    _, session_factory = test_app
    _user_counter = 0

    def factory(**kwargs: object) -> db_models.User:
        nonlocal _user_counter
        _user_counter += 1
        defaults = {
            "id": kwargs.get("id", f"user-{_user_counter}-{uuid.uuid4().hex[:8]}"),
            "username": kwargs.get("username", f"tester-{_user_counter}"),
            "email": kwargs.get("email", f"tester-{_user_counter}@example.com"),
            "first_name": kwargs.get("first_name", "Test"),
            "last_name": kwargs.get("last_name", f"User{_user_counter}"),
            "display_name": kwargs.get("display_name", f"Tester-{_user_counter}"),
            "avatar_url": kwargs.get("avatar_url"),
        }
        with session_factory() as session:
            user = db_models.User(**defaults)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    return factory


@pytest.fixture()
def create_model_config(
    test_app: tuple[TestClient, sessionmaker[Session]]
) -> Callable[..., db_models.ModelConfig]:
    """Create test model configuration"""

    _, session_factory = test_app

    def factory(**kwargs: object) -> db_models.ModelConfig:
        defaults = {
            "id": kwargs.get("id", "model-1"),
            "model_key": kwargs.get("model_key", "claude-3-7-sonnet-20250219"),
            "model_name": kwargs.get("model_name", "Claude 3.7 Sonnet"),
            "is_active": kwargs.get("is_active", True),
            "sort_order": kwargs.get("sort_order", 0),
        }
        with session_factory() as session:
            record = db_models.ModelConfig(**defaults)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    return factory


# ============================================================================
# New test helper fixtures
# ============================================================================

@pytest.fixture
def auth_helper():
    """Authentication test helper"""
    return AuthTestHelper()


@pytest.fixture
def test_data_factory():
    """Test data factory"""
    return TestDataFactory()


@pytest.fixture
def mock_responses():
    """Mock response utility"""
    return MockResponses()


@pytest.fixture
def workspace_helper():
    """Workspace test helper"""
    return WorkspaceTestHelper()


@pytest.fixture
def container_helper():
    """Container test helper"""
    return ContainerTestHelper()


@pytest.fixture
def authenticated_client(
    test_app: tuple[TestClient, sessionmaker[Session]],
    create_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """Authenticated test client"""
    client, session_factory = test_app

    # Create test user, using same ID as authentication middleware
    user = create_user(id="internal-test-user", username="testuser", email="test@example.com")

    # Create default settings for user (referencing default settings in init.sql)
    with session_factory() as session:
        user_setting = db_models.UserSetting(
            id=f"settings-{user.id}",
            user_id=user.id,
            claude_selected_model="claude-sonnet-4-20250514",
            claude_selected_provider="anthropic",
            general_settings={
                "theme": "system",
                "language": "zh-TW",
                "timezone": "Asia/Taipei",
                "notifications": {
                    "desktop": True,
                    "email": False,
                    "updates": True
                },
                "performance": {
                    "autoSave": True,
                    "animationsEnabled": True
                },
                "privacy": {
                    "analytics": False,
                    "crashReports": True,
                    "usageData": False
                }
            },
            additional_settings={
                "ssh": {
                    "publicKey": "",
                    "privateKey": "",
                    "fingerprint": None,
                    "lastRotatedAt": None
                },
                "claudeCode": {
                    "oauth": {
                        "accessToken": None,
                        "refreshToken": None,
                        "expiresAt": None
                    }
                }
            }
        )
        session.add(user_setting)
        session.commit()

    async def mock_validate_token(self, token: str) -> dict[str, str]:
        return {
            "sub": "test-keycloak-user",
            "preferred_username": user.username,
            "email": user.email,
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )

    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": "Bearer test-access-token"})

    return client, user


@pytest.fixture
def admin_client(test_app: tuple[TestClient, sessionmaker[Session]], create_user):
    """Test client with admin privileges"""
    client, _ = test_app

    # Create admin user
    admin = create_user(username="admin", email="admin@example.com")

    # Use internal token directly to avoid Redis dependency issues
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    return client, admin


@pytest.fixture
def internal_client(test_app: tuple[TestClient, sessionmaker[Session]]):
    """Internal API test client"""
    client, session_factory = test_app

    # Set up internal API authentication headers
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    return client, session_factory


@pytest.fixture
def sample_user_data(test_data_factory: TestDataFactory):
    """Sample user data"""
    return test_data_factory.create_user_data()


@pytest.fixture
def sample_team_data(test_data_factory: TestDataFactory):
    """Sample team data"""
    return test_data_factory.create_team_data()


@pytest.fixture
def sample_workspace_data(test_data_factory: TestDataFactory):
    """Sample workspace data"""
    return test_data_factory.create_workspace_data()


@pytest.fixture
def sample_template_data(test_data_factory: TestDataFactory):
    """Sample template data"""
    return test_data_factory.create_template_data()


@pytest.fixture
def i18n_helper() -> I18nTestHelper:
    """Multilingual test helper"""
    return get_i18n_test_helper()


# Test markers
pytest_plugins = []

# Test configuration


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
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
        "markers", "container: marks tests as container tests"
    )


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        # Automatically add markers based on file path
        if "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add specific markers based on filename
        if "auth" in str(item.fspath):
            item.add_marker(pytest.mark.auth)
        elif "workspace" in str(item.fspath):
            item.add_marker(pytest.mark.workspace)
        elif "container" in str(item.fspath):
            item.add_marker(pytest.mark.container)
