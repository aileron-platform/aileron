from pathlib import Path

import pytest

from aileron_file_core import PathOutsideRootError
from aileron_file_core.adapters import (
    DynamicRootResolver,
    RootedFileAdapter,
    ScopedRootResolver,
    StaticRootResolver,
)
from aileron_file_core.models import FileLocator
from aileron_file_core.policies import PathExclusionPolicy


def test_rooted_file_adapter_resolves_safe_path(tmp_path: Path) -> None:
    adapter = RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path))
    locator = FileLocator(domain="knowledge-base", resource_id="kb-1")

    safe_path = adapter.resolve_path(locator, "/docs/readme.md")

    assert safe_path.relative_path == "docs/readme.md"
    assert safe_path.absolute_path == tmp_path / "docs" / "readme.md"


def test_rooted_file_adapter_rejects_escape(tmp_path: Path) -> None:
    adapter = RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path))

    with pytest.raises(PathOutsideRootError) as exc:
        adapter.resolve_path(FileLocator("workspace", "w1"), "../secret")

    assert exc.value.code == "PATH_OUTSIDE_ROOT"


def test_rooted_file_adapter_default_lock_key_uses_canonical_path(
    tmp_path: Path,
) -> None:
    adapter = RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path))
    locator = FileLocator(domain="workspace", resource_id="w1:primary", scope="project")

    assert adapter.lock_key_for(locator, "/src/app.py", "write") == (
        "workspace",
        "w1:primary",
        "project",
        "src/app.py",
    )


def test_scoped_root_resolver_selects_root_by_scope(tmp_path: Path) -> None:
    resolver = ScopedRootResolver(
        default_scope="project",
        roots={
            "project": tmp_path / "project",
            "user": tmp_path / "user",
        },
    )
    adapter = RootedFileAdapter(root_resolver=resolver)

    assert adapter.root_for(FileLocator("workspace", "w1", scope="user")) == (
        tmp_path / "user"
    )
    assert adapter.root_for(FileLocator("workspace", "w1")) == tmp_path / "project"


def test_dynamic_root_resolver_delegates_to_callback(tmp_path: Path) -> None:
    resolver = DynamicRootResolver(
        lambda locator: tmp_path / (locator.scope or "default")
    )
    adapter = RootedFileAdapter(root_resolver=resolver)

    assert adapter.root_for(FileLocator("workspace", "w1", scope="project")) == (
        tmp_path / "project"
    )


def test_adapter_can_read_rejects_excluded_paths(tmp_path: Path) -> None:
    adapter = RootedFileAdapter(
        root_resolver=StaticRootResolver(tmp_path),
        path_exclusion=PathExclusionPolicy.defaults(extra_names={".marketplace"}),
    )

    with pytest.raises(PathOutsideRootError):
        adapter.can_read(FileLocator("marketplace", "registry"), ".marketplace/ssh/id")
