"""Test shared configuration"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aileron_git_core.testkit import Actor, Repo
from fastapi.testclient import TestClient

_RUNTIME_SECRET_ROOT = Path("/tmp/aileron-runtime-tests")
_RUNTIME_SECRET_ROOT.mkdir(parents=True, exist_ok=True)
_RUNTIME_DATABASE_FILE = Path(
    os.environ.get(
        "AILERON_RUNTIME_DATABASE_CONNECTION_FILE",
        _RUNTIME_SECRET_ROOT / "runtime-database-connection",
    )
)
_RUNTIME_CONTROL_TOKEN_FILE = Path(
    os.environ.get(
        "AILERON_RUNTIME_CONTROL_TOKEN_FILE",
        _RUNTIME_SECRET_ROOT / "runtime-control-token",
    )
)
if "AILERON_RUNTIME_DATABASE_CONNECTION_FILE" not in os.environ:
    _RUNTIME_DATABASE_FILE.write_text(
        "postgresql://test:test@127.0.0.1/test",
        encoding="utf-8",
    )
if "AILERON_RUNTIME_CONTROL_TOKEN_FILE" not in os.environ:
    _RUNTIME_CONTROL_TOKEN_FILE.write_text(
        "test-runtime-control-token",
        encoding="utf-8",
    )

_PLATFORM_ENVIRONMENT = {
    "AILERON_WORKSPACE_ID": "test-workspace",
    "AILERON_WORKSPACE_PATH": "/workspace",
    "AILERON_RUNTIME_INSTANCE_ID": "11111111-1111-4111-8111-111111111111",
    "AILERON_RUNTIME_ACCESS_REVISION": "0",
    "AILERON_KB_MOUNT_REVISION": "0",
    "AILERON_WORKTREE_SUBDIR": ".worktrees",
    "AILERON_RUNTIME_DATABASE_CONNECTION_FILE": str(_RUNTIME_DATABASE_FILE),
    "AILERON_RUNTIME_CONTROL_TOKEN_FILE": str(_RUNTIME_CONTROL_TOKEN_FILE),
    "AILERON_MANAGER_INTERNAL_URL": "http://workspace-manager:8000",
    "AILERON_PLATFORM_PUBLIC_ORIGIN": "http://frontend.test",
    "AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE": "/tmp/runtime-jwks.json",
    "AILERON_RUNTIME_ASSERTION_ISSUER": "workspace-manager",
    "AILERON_BROWSER_SERVICE_NAME": "workspace-browser-test",
    "AILERON_BROWSER_WEBRTC_INTERNAL_URL": "http://workspace-browser-test:6080",
    "AILERON_BROWSER_CDP_URL": "http://workspace-browser-test:9223",
    "AILERON_CANVAS_SERVICE_NAME": "workspace-canvas-test",
    "AILERON_CANVAS_INTERNAL_URL": "http://workspace-canvas-test:3003",
    "AILERON_CANVAS_API_URL": "http://workspace-canvas-test:3013",
}
for _name, _value in _PLATFORM_ENVIRONMENT.items():
    os.environ.setdefault(_name, _value)

from app.main import app
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.git_operations import GitService

# Import test infrastructure fixtures
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.git",
]


class _AllowExecutionGrantVerifier:
    def verify(self, grant: str, *, action: str):
        if grant != "test-token":
            raise AssertionError("Unexpected execution grant fixture")
        return SimpleNamespace(subject="test-user", actions=(action,))


@pytest.fixture(autouse=True)
def stub_runtime_admission_state(monkeypatch):
    """Reset Runtime admission state around each test."""
    from app.modules.runtime_control import drain, state

    monkeypatch.setattr(
        state,
        "_runtime_admission_state",
        state.RuntimeAdmissionState(),
    )
    monkeypatch.setattr(
        drain,
        "_runtime_drain_service",
        drain.RuntimeDrainService(),
    )


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client and reset file service"""

    # Clear global state
    from app.modules.file_system.dependencies import _file_service

    _file_service.clear() if _file_service else None

    get_git_service.cache_clear()
    resource_telemetry_reporter = MagicMock()
    resource_telemetry_reporter.start = AsyncMock()
    resource_telemetry_reporter.stop = AsyncMock()
    with (
        patch(
            "app.middleware.auth.get_execution_grant_verifier",
            return_value=_AllowExecutionGrantVerifier(),
        ),
        patch("app.main.AutomationRunner.start", new_callable=AsyncMock),
        patch("app.main.AutomationRunner.shutdown", new_callable=AsyncMock),
        patch("app.main.AutomationControlPlaneClient.close", new_callable=AsyncMock),
        patch(
            "app.main.build_resource_telemetry_reporter",
            return_value=resource_telemetry_reporter,
        ),
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
    Repo.init(remote_path, bare=True)
    if "origin" not in {remote.name for remote in repo.remotes}:
        repo.create_remote("origin", remote_path.as_posix())
    repo.git.push("-u", "origin", repo.active_branch.name)
    repo.remotes.origin.fetch()

    try:
        yield workspace_id, repo, service
    finally:
        app.dependency_overrides.pop(get_git_service, None)
        get_git_service.cache_clear()
