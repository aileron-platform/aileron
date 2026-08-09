from pathlib import Path

from aileron_file_core import ContentHashVersionStrategy, resolve_safe_path
from aileron_git_core import OperationKind, OperationManager, run_git


def test_shared_core_imports_are_available(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    readme_path = root / "README.md"
    readme_path.write_text("hello\n", encoding="utf-8")

    safe_path = resolve_safe_path(root, "README.md")
    version_strategy = ContentHashVersionStrategy()
    manager = OperationManager()

    assert safe_path.relative_path == "README.md"
    assert len(version_strategy.read_version(safe_path.absolute_path)) == 64
    assert callable(run_git)
    assert OperationKind.READ.value == "read"
    assert manager is not None
