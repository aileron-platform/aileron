"""Test shared configuration"""

from __future__ import annotations

import asyncio
import pytest
import uuid
from typing import AsyncGenerator
from unittest.mock import patch

from fastapi.testclient import TestClient
from git import Actor, Repo

from app.main import app
from app.modules.file_system.dependencies import get_file_service_sync
from app.modules.version_control import GitService, get_git_service
from app.services.auth_service import SimpleUser

# Import test infrastructure fixtures
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.redis",
    "tests.fixtures.git",
    "tests.fixtures.websocket",
]


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client and reset file service"""

    # Clear global state
    from app.modules.file_system.dependencies import _file_service
    _file_service.clear() if _file_service else None

    class StubAuthService:
        async def validate_access_token(self, token: str):
            if token == "test-token":
                return SimpleUser(
                    user_id="test-user",
                    email="test@example.com",
                    username="test-user",
                    roles=["tester"],
                )
            return None

    get_git_service.cache_clear()
    with patch("app.middleware.auth.get_auth_service", return_value=StubAuthService()):
        with patch(
            "app.modules.agent_session.websocket.router.get_auth_service",
            return_value=StubAuthService(),
        ):
            with TestClient(app) as test_client:
                test_client.headers.update({"Authorization": "Bearer test-token"})
                yield test_client
    get_git_service.cache_clear()
    _file_service.clear() if _file_service else None


@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def websocket_test_overrides():
    """WebSocket test dependency override fixture"""
    from tests.integration.core.helpers import create_websocket_test_overrides

    overrides = create_websocket_test_overrides()

    # Save original overrides
    original_overrides = {}
    for dependency in overrides:
        if dependency in app.dependency_overrides:
            original_overrides[dependency] = app.dependency_overrides[dependency]

    # Set up test overrides
    for dependency, provider in overrides.items():
        app.dependency_overrides[dependency] = provider

    yield overrides

    # Restore original overrides
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)

    # Restore original overrides
    for dependency, provider in original_overrides.items():
        app.dependency_overrides[dependency] = provider


@pytest.fixture
def git_workspace(tmp_path_factory) -> tuple[str, Repo, GitService]:
    """Create actual Git workspace for version control testing"""

    base_path = tmp_path_factory.mktemp("git-workspaces")
    service = GitService(base_path=base_path)
    get_git_service.cache_clear()
    app.dependency_overrides[get_git_service] = lambda: service

    workspace_id = "ws-" + uuid.uuid4().hex[:8]
    repo_path = base_path / workspace_id
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(repo_path)

    readme = repo_path / "README.md"
    readme.write_text("# Demo\n\nInitial content.\n", encoding="utf-8")
    repo.index.add(["README.md"])
    actor = Actor("Test User", "test@example.com")
    repo.index.commit("Initial commit", author=actor, committer=actor)
    try:
        repo.git.branch("-m", "main")
    except Exception:  # pragma: no cover - branch rename may fail if already main
        pass

    remote_path = base_path / "remote.git"
    remote = Repo.init(remote_path, bare=True)
    if "origin" not in {remote.name for remote in repo.remotes}:
        repo.create_remote("origin", remote_path.as_posix())
    repo.git.push("-u", "origin", repo.active_branch.name)
    repo.remotes.origin.fetch()

    try:
        yield workspace_id, repo, service
    finally:
        app.dependency_overrides.pop(get_git_service, None)
        get_git_service.cache_clear()
