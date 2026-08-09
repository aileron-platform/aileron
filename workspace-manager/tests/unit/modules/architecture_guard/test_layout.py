"""Architecture contract for the Workspace Manager Python layout."""

from __future__ import annotations

import ast
import re
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[4]
APP_ROOT = SERVICE_ROOT / "app"
MODULES_ROOT = APP_ROOT / "modules"
TESTS_ROOT = SERVICE_ROOT / "tests"

LEGACY_APP_DIRECTORIES = {
    "contracts",
    "models",
    "repositories",
    "routers",
    "services",
    "translations",
    "utils",
}
LEGACY_IMPORT_PREFIXES = tuple(f"app.{name}" for name in LEGACY_APP_DIRECTORIES)
VAGUE_MODULE_FILENAMES = {
    "common.py",
    "helpers.py",
    "service.py",
    "shared.py",
    "support.py",
    "utils.py",
}
VAGUE_MODULE_SUFFIXES = ("_helpers.py", "_support.py", "_utils.py")
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return ",".join(alias.name for alias in node.names)


def test_legacy_horizontal_app_directories_are_absent() -> None:
    violations = [
        str(APP_ROOT / directory)
        for directory in sorted(LEGACY_APP_DIRECTORIES)
        if (APP_ROOT / directory).exists()
    ]

    assert not violations, "Legacy horizontal app directories remain:\n" + "\n".join(
        violations
    )


def test_domain_module_paths_and_filenames_are_explicit() -> None:
    violations: list[str] = []
    for path in _python_files(MODULES_ROOT):
        relative = path.relative_to(MODULES_ROOT)
        for directory in relative.parts[:-1]:
            if not SNAKE_CASE.fullmatch(directory):
                violations.append(f"{relative}: directory is not snake_case")

        filename = relative.name
        stem = path.stem
        if filename != "__init__.py" and not SNAKE_CASE.fullmatch(stem):
            violations.append(f"{relative}: filename is not snake_case")
        if filename in VAGUE_MODULE_FILENAMES or filename.endswith(
            VAGUE_MODULE_SUFFIXES
        ):
            violations.append(f"{relative}: vague module filename")

    assert not violations, "Invalid domain module paths:\n" + "\n".join(violations)


def test_domain_package_initializers_are_not_barrels() -> None:
    violations: list[str] = []
    for path in sorted(MODULES_ROOT.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                violations.append(
                    f"{path.relative_to(SERVICE_ROOT)}: re-export import "
                    f"{_module_name(node)}"
                )
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in targets
                ):
                    violations.append(
                        f"{path.relative_to(SERVICE_ROOT)}: __all__ barrel"
                    )

    assert not violations, "Domain package barrels remain:\n" + "\n".join(violations)


def test_legacy_import_paths_are_absent() -> None:
    violations: list[str] = []
    for path in _python_files(SERVICE_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            imported = _module_name(node)
            if imported.startswith(LEGACY_IMPORT_PREFIXES):
                violations.append(
                    f"{path.relative_to(SERVICE_ROOT)}:{node.lineno}: {imported}"
                )

    assert not violations, "Legacy import paths remain:\n" + "\n".join(violations)


def test_tests_use_the_domain_mirror() -> None:
    violations: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        relative = path.relative_to(TESTS_ROOT)
        parts = relative.parts
        if (
            len(parts) < 4
            or parts[0] not in {"unit", "integration", "contract"}
            or parts[1] != "modules"
        ):
            violations.append(str(relative))
        if relative.name in {"test_helpers.py", "test_utils.py", "test_common.py"}:
            violations.append(f"{relative}: vague test filename")

    assert not violations, "Tests outside the domain mirror:\n" + "\n".join(violations)


def test_localization_resources_have_one_owner() -> None:
    expected = MODULES_ROOT / "localization" / "translations"
    assert (expected / "en.json").is_file()
    assert (expected / "zh-TW.json").is_file()

    translation_directories = sorted(
        path for path in APP_ROOT.rglob("translations") if path.is_dir()
    )
    assert translation_directories == [expected]
