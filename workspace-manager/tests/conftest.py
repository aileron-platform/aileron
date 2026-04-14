"""測試共用設定"""

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

# 測試必須強制使用獨立 SQLite，避免容器環境變數把測試導向共享 PostgreSQL。
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

# 導入測試輔助工具
from tests.helpers.auth_helpers import AuthTestHelper
from tests.helpers.fixtures import TestDataFactory, MockResponses
from tests.helpers.workspace_helpers import WorkspaceTestHelper
from tests.helpers.container_helpers import ContainerTestHelper
from tests.helpers.i18n_helpers import I18nTestHelper, get_i18n_test_helper


@pytest.fixture()
def test_app(tmp_path: Path) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    """提供測試用的 FastAPI 客戶端與資料庫 Session 工廠

    改進：
    1. 使用 tmp_path 作為資料庫路徑
    2. 使用 tmp_path 作為模板儲存路徑
    3. 確保測試完全隔離，不污染真實環境
    """

    # 設置臨時模板儲存路徑
    template_storage_path = tmp_path / "template-storage"
    template_storage_path.mkdir(parents=True, exist_ok=True)

    # 創建 plugins 目錄（模板服務需要）
    plugins_dir = template_storage_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # 保存原始環境變數
    original_template_path = os.environ.get("TEMPLATE_STORAGE_PATH")

    # 設置測試環境變數
    os.environ["TEMPLATE_STORAGE_PATH"] = str(template_storage_path)

    # 清除 settings 快取，讓新的環境變數生效
    get_settings.cache_clear()

    # 設置測試資料庫
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # 為測試用資料庫預先載入必要種子資料。
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
            # 為所有測試請求設定英文語系，確保測試結果一致
            client.headers.update({"Accept-Language": "en", "X-Language": "en"})
            yield client, TestingSessionLocal
    finally:
        # 清理
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        # 恢復原始環境變數
        if original_template_path is not None:
            os.environ["TEMPLATE_STORAGE_PATH"] = original_template_path
        else:
            os.environ.pop("TEMPLATE_STORAGE_PATH", None)

        # 再次清除快取
        get_settings.cache_clear()


@pytest.fixture()
def create_user(test_app: tuple[TestClient, sessionmaker[Session]]) -> Callable[..., db_models.User]:
    """建立測試用使用者"""

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
            "display_name": kwargs.get("display_name", f"測試者-{_user_counter}"),
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
    """建立測試用模型設定"""

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
# 新增的測試輔助工具 fixtures
# ============================================================================

@pytest.fixture
def auth_helper():
    """認證測試輔助工具"""
    return AuthTestHelper()


@pytest.fixture
def test_data_factory():
    """測試資料工廠"""
    return TestDataFactory()


@pytest.fixture
def mock_responses():
    """Mock 回應工具"""
    return MockResponses()


@pytest.fixture
def workspace_helper():
    """工作區測試輔助工具"""
    return WorkspaceTestHelper()


@pytest.fixture
def container_helper():
    """容器測試輔助工具"""
    return ContainerTestHelper()


@pytest.fixture
def authenticated_client(
    test_app: tuple[TestClient, sessionmaker[Session]],
    create_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """已認證的測試客戶端"""
    client, session_factory = test_app

    # 創建測試用戶，使用與認證中間件相同的 ID
    user = create_user(id="internal-test-user", username="testuser", email="test@example.com")

    # 為用戶創建默認設定（參考 init.sql 中的默認設定）
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
    """管理員權限的測試客戶端"""
    client, _ = test_app

    # 創建管理員用戶
    admin = create_user(username="admin", email="admin@example.com")

    # 直接使用內部 token，避免 Redis 依賴問題
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    return client, admin


@pytest.fixture
def internal_client(test_app: tuple[TestClient, sessionmaker[Session]]):
    """內部 API 測試客戶端"""
    client, session_factory = test_app

    # 設置內部 API 認證標頭
    client.headers.update({"X-Internal-Token": "test-internal-token"})

    return client, session_factory


@pytest.fixture
def sample_user_data(test_data_factory: TestDataFactory):
    """樣本用戶資料"""
    return test_data_factory.create_user_data()


@pytest.fixture
def sample_team_data(test_data_factory: TestDataFactory):
    """樣本團隊資料"""
    return test_data_factory.create_team_data()


@pytest.fixture
def sample_workspace_data(test_data_factory: TestDataFactory):
    """樣本工作區資料"""
    return test_data_factory.create_workspace_data()


@pytest.fixture
def sample_template_data(test_data_factory: TestDataFactory):
    """樣本範本資料"""
    return test_data_factory.create_template_data()


@pytest.fixture
def i18n_helper() -> I18nTestHelper:
    """多語系測試輔助工具"""
    return get_i18n_test_helper()


# 測試標記
pytest_plugins = []

# 測試組態


def pytest_configure(config):
    """配置 pytest"""
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


# 測試收集配置
def pytest_collection_modifyitems(config, items):
    """修改測試收集"""
    for item in items:
        # 根據檔案路徑自動添加標記
        if "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # 根據檔案名添加特定標記
        if "auth" in str(item.fspath):
            item.add_marker(pytest.mark.auth)
        elif "workspace" in str(item.fspath):
            item.add_marker(pytest.mark.workspace)
        elif "container" in str(item.fspath):
            item.add_marker(pytest.mark.container)
