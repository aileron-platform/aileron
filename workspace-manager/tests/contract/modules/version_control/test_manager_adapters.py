from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aileron_git_core import RepositoryStatus
from pydantic import ValidationError

from app.db import models as db_models
from app.modules.version_control.application import (
    GitIdentityMissingError,
    ManagerActorContextResolver,
    version_control_status_from_core,
)
from app.modules.version_control.models import StageRequest, VersionControlStatus
from app.modules.version_control.target import (
    KnowledgeBaseRepositoryTargetResolver,
    MarketplaceRepositoryTargetResolver,
)


def test_knowledge_base_target_uses_stable_non_path_lock_keys(tmp_path: Path) -> None:
    target = KnowledgeBaseRepositoryTargetResolver(tmp_path).resolve("kb-123")

    assert target.root == tmp_path / "kb-123"
    assert target.lock_scope_keys.common_repository == "knowledge-base:kb-123"
    assert target.lock_scope_keys.working_tree_target == "knowledge-base:kb-123"
    assert str(tmp_path) not in target.lock_scope_keys.common_repository


def test_marketplace_target_is_single_managed_repository(tmp_path: Path) -> None:
    target = MarketplaceRepositoryTargetResolver(tmp_path).resolve()

    assert target.root == tmp_path / "registry"
    assert target.lock_scope_keys.common_repository == "marketplace:registry"
    assert target.lock_scope_keys.working_tree_target == "marketplace:registry"


def test_marketplace_clone_staging_target_stays_under_managed_parent(
    tmp_path: Path,
) -> None:
    resolver = MarketplaceRepositoryTargetResolver(tmp_path / "marketplace")
    staging = tmp_path / "clone-session" / "registry"

    target = resolver.resolve_staging_clone(staging)

    assert target.root == staging
    assert target.lock_scope_keys.common_repository == "marketplace:registry"
    with pytest.raises(ValueError, match="repository_target_invalid"):
        resolver.resolve_staging_clone(tmp_path.parent / "registry")


def test_actor_context_uses_only_system_settings_git_identity() -> None:
    db = MagicMock()
    db.scalar.return_value = db_models.UserSetting(
        id="settings-1",
        user_id="user-1",
        git_user_name="System User",
        git_user_email="system@example.local",
    )

    actor = ManagerActorContextResolver(db).resolve(
        user_id="user-1",
        display_name="Visible User",
    )

    assert actor.display_name == "Visible User"
    assert actor.git_name == "System User"
    assert actor.git_email == "system@example.local"


def test_actor_context_rejects_missing_system_settings_identity() -> None:
    db = MagicMock()
    db.scalar.return_value = None

    with pytest.raises(GitIdentityMissingError, match="git_identity_missing"):
        ManagerActorContextResolver(db).resolve(
            user_id="user-1",
            display_name="Visible User",
        )


def test_status_adapter_emits_only_shared_wire_fields() -> None:
    status = version_control_status_from_core(
        RepositoryStatus(
            is_initialized=True,
            current_branch="main",
            detached_head=False,
            head_sha="abc123",
            has_origin=True,
            upstream="origin/main",
            ahead=1,
            behind=2,
            has_conflicts=False,
            staged_total=3,
            unstaged_total=4,
            untracked_total=5,
            conflict_total=0,
        )
    )

    assert set(status.model_dump(by_alias=True)) == {
        "isInitialized",
        "currentBranch",
        "detachedHead",
        "headSha",
        "hasOrigin",
        "upstream",
        "ahead",
        "behind",
        "hasConflicts",
        "stagedTotal",
        "unstagedTotal",
        "untrackedTotal",
        "conflictTotal",
        "operationStatus",
    }
    assert set(VersionControlStatus.model_json_schema()["properties"]) == set(
        status.model_dump(by_alias=True)
    )


def test_stage_request_rejects_removed_unsafe_flag() -> None:
    with pytest.raises(ValidationError):
        StageRequest.model_validate({"all": True, "includeUntracked": False})
