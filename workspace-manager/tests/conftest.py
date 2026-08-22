"""Common test configurations"""

from __future__ import annotations

import base64
import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Tests must force standalone SQLite instead of the container integration database.
_TEST_DATABASE_URL_FILE = Path("/tmp/aileron-pytest-database-url")
_TEST_DATABASE_URL_FILE.write_text("sqlite:///:memory:\n", encoding="utf-8")
os.environ["DATABASE_URL_FILE"] = str(_TEST_DATABASE_URL_FILE)
os.environ["ENV"] = "testing"
os.environ["PLATFORM_PUBLIC_ORIGIN"] = "https://aileron.test"
os.environ["OIDC_ISSUER_URL"] = "https://oidc.test.example"
os.environ["OIDC_CLIENT_ID"] = "aileron-manager"

from app.config.settings import get_settings
from app.db import models as db_models
from app.db.database import Base, get_db
from app.main import app
from app.modules.identity.user_authorization_policy import canonical_role_issues
from app.modules.settings.models import default_tool_model
from app.modules.workspace.runtime.assertions import get_runtime_assertion_service


@pytest.fixture()
def test_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    """Provide FastAPI client and database Session factory for testing

    Improvements:
    1. Use tmp_path as database path
    2. Use tmp_path for storage paths
    3. Ensure complete test isolation without polluting the real environment
    """

    marketplace_storage_path = tmp_path / "marketplace-storage"
    marketplace_storage_path.mkdir(parents=True, exist_ok=True)
    knowledge_bases_path = tmp_path / "knowledge-bases"
    knowledge_bases_path.mkdir(parents=True, exist_ok=True)
    browser_credential_keyring_file = tmp_path / "browser-credential-keyring.json"
    browser_credential_keyring_file.write_text(
        json.dumps(
            {
                "algorithm": "hkdf-sha256-v1",
                "activeKeyId": "test-browser-key",
                "keys": {
                    "test-browser-key": base64.urlsafe_b64encode(b"b" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                },
            }
        ),
        encoding="utf-8",
    )
    browser_credential_keyring_file.chmod(0o600)
    runtime_database_credential_key_file = tmp_path / "runtime-database-credential.key"
    runtime_database_credential_key_file.write_bytes(b"r" * 32)
    runtime_database_credential_key_file.chmod(0o600)
    runtime_assertion_kid = "test-runtime-assertion-key"
    runtime_assertion_private_key_file = tmp_path / "runtime-assertion-private.pem"
    runtime_assertion_public_key_set_file = tmp_path / "runtime-assertion-jwks.json"
    runtime_assertion_private_key = Ed25519PrivateKey.generate()
    runtime_assertion_private_key_file.write_bytes(
        runtime_assertion_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    runtime_assertion_private_key_file.chmod(0o600)
    runtime_assertion_public_key = runtime_assertion_private_key.public_key()
    encoded_public_key = base64.urlsafe_b64encode(
        runtime_assertion_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).rstrip(b"=")
    runtime_assertion_public_key_set_file.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "use": "sig",
                        "alg": "EdDSA",
                        "kid": runtime_assertion_kid,
                        "x": encoded_public_key.decode("ascii"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runtime_assertion_public_key_set_file.chmod(0o644)

    # Preserve original environment variables
    original_marketplace_path = os.environ.get("MARKETPLACE_STORAGE_PATH")
    original_manager_kb_path = os.environ.get("MANAGER_KNOWLEDGE_BASES_DIR")
    original_host_kb_path = os.environ.get("HOST_KNOWLEDGE_BASES_DIR")
    original_browser_keyring = os.environ.get("BROWSER_CREDENTIAL_KEYRING_FILE")
    original_runtime_database_key = os.environ.get(
        "RUNTIME_DATABASE_CREDENTIAL_KEY_FILE"
    )
    original_runtime_assertion_private_key = os.environ.get(
        "RUNTIME_ASSERTION_PRIVATE_KEY_FILE"
    )
    original_runtime_assertion_public_key_set = os.environ.get(
        "RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE"
    )
    original_runtime_assertion_kid = os.environ.get("RUNTIME_ASSERTION_KID")
    original_platform_public_origin = os.environ.get("PLATFORM_PUBLIC_ORIGIN")

    # Set up test environment variables
    os.environ["MARKETPLACE_STORAGE_PATH"] = str(marketplace_storage_path)
    os.environ["MANAGER_KNOWLEDGE_BASES_DIR"] = str(knowledge_bases_path)
    os.environ["HOST_KNOWLEDGE_BASES_DIR"] = str(knowledge_bases_path)
    os.environ["BROWSER_CREDENTIAL_KEYRING_FILE"] = str(browser_credential_keyring_file)
    os.environ["RUNTIME_DATABASE_CREDENTIAL_KEY_FILE"] = str(
        runtime_database_credential_key_file
    )
    os.environ["RUNTIME_ASSERTION_PRIVATE_KEY_FILE"] = str(
        runtime_assertion_private_key_file
    )
    os.environ["RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE"] = str(
        runtime_assertion_public_key_set_file
    )
    os.environ["RUNTIME_ASSERTION_KID"] = runtime_assertion_kid
    os.environ["PLATFORM_PUBLIC_ORIGIN"] = "https://aileron.test"

    # Clear settings cache to apply new environment variables
    get_settings.cache_clear()
    get_runtime_assertion_service.cache_clear()

    # Set up test database
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", TestingSessionLocal)

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app, base_url="https://aileron.test") as client:
            # Set English locale for all test requests to ensure consistent test results
            client.headers.update({"Accept-Language": "en", "X-Language": "en"})
            yield client, TestingSessionLocal
    finally:
        # Cleanup
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        # Restore original environment variables
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
        if original_browser_keyring is not None:
            os.environ["BROWSER_CREDENTIAL_KEYRING_FILE"] = original_browser_keyring
        else:
            os.environ.pop("BROWSER_CREDENTIAL_KEYRING_FILE", None)
        if original_runtime_database_key is not None:
            os.environ["RUNTIME_DATABASE_CREDENTIAL_KEY_FILE"] = (
                original_runtime_database_key
            )
        else:
            os.environ.pop("RUNTIME_DATABASE_CREDENTIAL_KEY_FILE", None)
        if original_runtime_assertion_private_key is not None:
            os.environ["RUNTIME_ASSERTION_PRIVATE_KEY_FILE"] = (
                original_runtime_assertion_private_key
            )
        else:
            os.environ.pop("RUNTIME_ASSERTION_PRIVATE_KEY_FILE", None)
        if original_runtime_assertion_public_key_set is not None:
            os.environ["RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE"] = (
                original_runtime_assertion_public_key_set
            )
        else:
            os.environ.pop("RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE", None)
        if original_runtime_assertion_kid is not None:
            os.environ["RUNTIME_ASSERTION_KID"] = original_runtime_assertion_kid
        else:
            os.environ.pop("RUNTIME_ASSERTION_KID", None)
        if original_platform_public_origin is not None:
            os.environ["PLATFORM_PUBLIC_ORIGIN"] = original_platform_public_origin
        else:
            os.environ.pop("PLATFORM_PUBLIC_ORIGIN", None)

        # Clear cache again
        get_settings.cache_clear()
        get_runtime_assertion_service.cache_clear()


@pytest.fixture()
def create_user(
    test_app: tuple[TestClient, sessionmaker[Session]],
) -> Callable[..., db_models.User]:
    """Create test user"""

    _, session_factory = test_app
    _user_counter = 0

    def factory(**kwargs: object) -> db_models.User:
        nonlocal _user_counter
        _user_counter += 1
        platform_role = kwargs.get("platform_role")
        role_status = kwargs.get("role_status", "missing")
        is_active = kwargs.get("is_active", True)
        identity_enabled = kwargs.get("identity_enabled", True)
        sync_status = kwargs.get("sync_status", "synced")
        defaults = {
            "id": kwargs.get("id", f"user-{_user_counter}-{uuid.uuid4().hex[:8]}"),
            "username": kwargs.get("username", f"tester-{_user_counter}"),
            "email": kwargs.get("email", f"tester-{_user_counter}@example.com"),
            "first_name": kwargs.get("first_name", "Test"),
            "last_name": kwargs.get("last_name", f"User{_user_counter}"),
            "display_name": kwargs.get("display_name", f"Tester-{_user_counter}"),
            "avatar_url": kwargs.get("avatar_url"),
            "is_active": is_active,
            "oidc_issuer": kwargs.get("oidc_issuer", "https://oidc.test.example"),
            "oidc_subject": kwargs.get("oidc_subject", f"subject-{_user_counter}"),
            "identity_enabled": identity_enabled,
            "sync_status": sync_status,
            "platform_role": platform_role,
            "role_status": role_status,
            "role_issues": kwargs.get(
                "role_issues", canonical_role_issues(str(role_status))
            ),
            "last_synced_at": kwargs.get("last_synced_at"),
        }
        with session_factory() as session:
            user = db_models.User(**defaults)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    return factory


@pytest.fixture
def authenticated_client(
    test_app: tuple[TestClient, sessionmaker[Session]],
    create_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """Authenticated test client"""
    client, session_factory = test_app

    # Create test user, using same ID as authentication middleware
    user = create_user(
        id="internal-test-user",
        username="testuser",
        email="test@example.com",
        platform_role="member",
        role_status="valid",
    )

    # Create default settings for user (referencing default settings in init.sql)
    with session_factory() as session:
        user_setting = db_models.UserSetting(
            id=f"settings-{user.id}",
            user_id=user.id,
            claude_selected_model=default_tool_model("claude"),
            general_settings={
                "theme": "system",
                "language": "zh-TW",
                "timezone": "Asia/Taipei",
                "notifications": {"desktop": True, "email": False, "updates": True},
                "performance": {"autoSave": True, "animationsEnabled": True},
                "privacy": {
                    "analytics": False,
                    "crashReports": True,
                    "usageData": False,
                },
            },
            additional_settings={
                "ssh": {
                    "publicKey": "",
                    "privateKey": "",
                    "fingerprint": None,
                    "lastRotatedAt": None,
                },
                "claudeCode": {
                    "oauth": {
                        "accessToken": None,
                        "refreshToken": None,
                        "expiresAt": None,
                    }
                },
            },
        )
        session.add(user_setting)
        session.commit()

    from app.modules.auth.session import ManagerSessionService
    from tests.helpers.manager_session import csrf_token_for_handle

    monkeypatch.setattr("app.modules.auth.middleware.SessionLocal", session_factory)
    with session_factory() as session:
        service = ManagerSessionService(session)
        issued = service.create(
            user_id=user.id,
            issuer=user.oidc_issuer,
            subject=user.oidc_subject,
            authentication_context={},
        )
        csrf_token = csrf_token_for_handle(session, issued.handle)
    client.cookies.set(
        "aileron_session",
        issued.handle,
        domain="aileron.test",
        path="/api/v1",
    )
    client.headers.update(
        {
            "Origin": "https://aileron.test",
            "X-CSRF-Token": csrf_token,
        }
    )

    return client, user


# Test markers
pytest_plugins = []

# Test configuration


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "auth: marks tests as authentication tests")
    config.addinivalue_line("markers", "workspace: marks tests as workspace tests")
    config.addinivalue_line("markers", "container: marks tests as container tests")


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
