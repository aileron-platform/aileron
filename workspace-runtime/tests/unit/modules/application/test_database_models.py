"""Runtime-owned database mapping contract tests."""

from app.database.models import Base
from app.modules.thread import persistence_models as thread_models  # noqa: F401


def test_runtime_metadata_excludes_manager_workspace_projection() -> None:
    assert "workspaces" not in Base.metadata.tables
    assert "threads" in Base.metadata.tables
