import json
from pathlib import Path

from aileron_git_core import DEFAULT_LFS_PATTERNS
from aileron_git_core.contracts import (
    ActorContext,
    BranchCreateAndSwitch,
    BranchListQuery,
    LockScopeKeys,
    RepositoryStatusQuery,
    RepositoryTarget,
)


_CHECKOUT_ROOT = (
    Path("/repo-root")
    if Path("/repo-root").is_dir()
    else Path(__file__).resolve().parents[3]
)
CONTRACT_PATH = _CHECKOUT_ROOT / "contracts/version-control/wire-contract.json"


def test_default_lfs_patterns_are_repository_wide_and_exported() -> None:
    assert DEFAULT_LFS_PATTERNS == (
        "*.pdf",
        "*.zip",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.webp",
        "*.pptx",
        "*.docx",
        "*.xlsx",
    )


def test_wire_contract_defines_shared_read_and_mutation_ids() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["version"] == 1
    assert contract["queries"] == [
        "repository.status",
        "branch.list",
        "changes.list",
        "changes.numstat",
        "commit.files",
        "history.list",
        "diff.get",
        "blob.get",
        "remote.settings.get",
        "lfs.patterns.get",
    ]
    assert "branch.createAndSwitch" in contract["mutations"]
    assert "conflict.abort" in contract["mutations"]
    assert "lfs.snapshot.convert" in contract["mutations"]
    assert "operation.cancel" in contract["mutations"]
    assert contract["enums"]["blockingScope"] == [
        "working_tree_target",
        "common_repository",
    ]
    assert contract["readModels"]["RemoteSettings"] == [
        "remoteName",
        "remoteUrl",
        "hasOrigin",
    ]
    assert contract["readModels"]["LfsSnapshotPreview"] == [
        "matchedTotal",
        "totalSize",
        "pathSample",
    ]


def test_wire_contract_forbids_unsafe_client_control_fields() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["forbiddenMutationFields"] == [
        "repositoryPath",
        "actorIdentity",
        "force",
        "amend",
        "commitPaths",
        "autoStash",
        "includeUntracked",
        "hooksBypass",
    ]
    assert contract["errorEnvelope"][-2:] == ["stale", "canForceUnlock"]


def test_typed_contract_keeps_product_identity_out_of_shared_target() -> None:
    target = RepositoryTarget(
        root=Path("/repository"),
        lock_scope_keys=LockScopeKeys(
            common_repository="repository:42",
            working_tree_target="repository:42:primary",
        ),
    )

    assert RepositoryStatusQuery().query_id == "repository.status"
    assert BranchListQuery().query_id == "branch.list"
    assert BranchCreateAndSwitch(name="feature", start_point="HEAD").command_id == (
        "branch.createAndSwitch"
    )
    assert ActorContext(
        display_name="Taylor",
        git_name="Taylor",
        git_email="taylor@example.test",
    ).git_email == "taylor@example.test"
    assert not hasattr(target, "workspace_id")
    assert not hasattr(target, "context_id")
