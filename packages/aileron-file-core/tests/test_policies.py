from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aileron_file_core.models import (
    FileLocator,
    FileMutationResult,
    FileTree,
    FileTreeNode,
    TreeRequest,
)
from aileron_file_core.policies import (
    DEFAULT_EXCLUDED_NAMES,
    FilePolicy,
    PathExclusionPolicy,
)
from aileron_file_core.versioning import ContentHashVersionStrategy


def test_file_locator_is_domain_neutral_and_frozen() -> None:
    locator = FileLocator(
        domain="workspace",
        resource_id="workspace-1:primary",
        scope="project",
    )

    assert locator.domain == "workspace"
    assert locator.resource_id == "workspace-1:primary"
    assert locator.scope == "project"
    with pytest.raises(FrozenInstanceError):
        locator.scope = "user"  # type: ignore[misc]


def test_file_policy_uses_default_factories() -> None:
    first = FilePolicy(max_read_bytes=10, max_write_bytes=10)
    second = FilePolicy(max_read_bytes=20, max_write_bytes=20)

    assert isinstance(first.version_strategy, ContentHashVersionStrategy)
    assert isinstance(second.version_strategy, ContentHashVersionStrategy)
    assert first.version_strategy is not second.version_strategy
    assert first.read_policy is not second.read_policy


def test_file_tree_models_freeze_nested_containers() -> None:
    child = FileTreeNode(
        name="child.txt",
        path="child.txt",
        type="file",
        size=1,
        updated_at="2026-06-19T00:00:00+00:00",
        depth=1,
    )
    children = [child]
    metadata = {"kind": "text"}

    node = FileTreeNode(
        name="root",
        path="/",
        type="directory",
        size=0,
        updated_at="2026-06-19T00:00:00+00:00",
        depth=0,
        children=children,
        metadata=metadata,
    )
    tree = FileTree(path="/", nodes=[node], total=1)
    result = FileMutationResult(
        path="root",
        operation="write",
        entry_type="file",
        metadata=metadata,
    )

    children.append(
        FileTreeNode(
            name="late.txt",
            path="late.txt",
            type="file",
            size=1,
            updated_at="2026-06-19T00:00:00+00:00",
            depth=1,
        )
    )
    metadata["kind"] = "binary"

    assert node.children == (child,)
    assert node.metadata["kind"] == "text"
    assert tree.nodes == (node,)
    assert result.metadata["kind"] == "text"
    with pytest.raises(TypeError):
        node.metadata["kind"] = "updated"  # type: ignore[index]
    with pytest.raises(TypeError):
        result.metadata["kind"] = "updated"  # type: ignore[index]


def test_default_exclusion_policy_covers_generated_directories() -> None:
    policy = PathExclusionPolicy.defaults()

    for name in DEFAULT_EXCLUDED_NAMES:
        assert policy.is_excluded(Path(name))
        assert policy.is_excluded(Path("src") / name / "file.txt")


def test_exclusion_policy_allows_domain_additions() -> None:
    policy = PathExclusionPolicy.defaults(extra_names={".marketplace"})

    assert policy.is_excluded(Path(".marketplace") / "ssh" / "id")
    assert not policy.is_excluded(Path("docs") / "readme.md")


def test_exclusion_policy_freezes_excluded_names() -> None:
    names = {".custom"}
    policy = PathExclusionPolicy(excluded_names=names)

    names.add(".late")

    assert policy.is_excluded(Path(".custom") / "file.txt")
    assert not policy.is_excluded(Path(".late") / "file.txt")
    assert not hasattr(policy.excluded_names, "add")


def test_tree_request_defaults_to_root_path() -> None:
    request = TreeRequest(locator=FileLocator("knowledge-base", "kb-1"))

    assert request.path == "/"
    assert request.include_hidden is False
    assert request.max_depth == 1
