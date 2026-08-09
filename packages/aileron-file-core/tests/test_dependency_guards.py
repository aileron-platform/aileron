import ast
from pathlib import Path

import aileron_file_core

EXPECTED_PUBLIC_EXPORTS = {
    "ArchiveBuildResult",
    "ArchiveBytesResult",
    "ArchiveEntry",
    "ArchiveMemoryEntry",
    "BatchDeleteRequest",
    "BatchItemResult",
    "BatchMutationResult",
    "BatchWriteItem",
    "BatchWriteRequest",
    "BackgroundFileOperation",
    "BackgroundFileOperationStore",
    "BuildArchiveRequest",
    "ContentHashVersionStrategy",
    "CopyEntriesRequest",
    "CopyEntryRequest",
    "CreateEntryRequest",
    "DEFAULT_EXCLUDED_NAMES",
    "DeleteEntryRequest",
    "DynamicRootResolver",
    "ExtractArchiveRequest",
    "ExtractArchiveStreamRequest",
    "FileConflictItem",
    "FileConflictPreflight",
    "FileConflictResolution",
    "FileBytes",
    "FileContent",
    "FileArchivePolicy",
    "FileList",
    "FileListItem",
    "FileCoreError",
    "FileLocator",
    "FileMutationHooks",
    "FileMutationResult",
    "FileOperationAdapter",
    "FileOperationEngine",
    "FilePolicy",
    "FileReadPolicy",
    "FileTree",
    "FileTreeNode",
    "JsonLocalHistoryStore",
    "LocalHistoryEntry",
    "LocalHistoryOperation",
    "LocalHistoryService",
    "ListFilesRequest",
    "MTimeVersionStrategy",
    "MoveEntryRequest",
    "NoopMutationHooks",
    "NoopQuotaHook",
    "NoopValidationHook",
    "PathOutsideRootError",
    "PathExclusionPolicy",
    "ReadBytesRequest",
    "ReadTextRequest",
    "ResourceWriteLockKey",
    "ResourceWriteLockManager",
    "ResourceWriteLockTimeoutError",
    "RootedFileAdapter",
    "SafePath",
    "SearchMatch",
    "SearchRequest",
    "SearchResult",
    "SyncTreeItem",
    "SyncTreeRequest",
    "ScopedRootResolver",
    "SnapshotResult",
    "StaticRootResolver",
    "TreeRequest",
    "UploadBatchResult",
    "UploadFilesRequest",
    "UploadItem",
    "UploadItemResult",
    "UploadStreamItem",
    "VersionConflictError",
    "VersionStrategy",
    "WriteResult",
    "WriteBytesRequest",
    "WriteTextRequest",
    "compare_and_write_text",
    "resolve_safe_path",
    "snapshot_file",
    "to_file_operation_data",
    "to_file_conflict_preflight",
    "to_tree_nodes",
    "to_upload_batch_result",
    "to_upload_items",
}


def test_file_core_public_exports_are_available() -> None:
    assert set(aileron_file_core.__all__) == EXPECTED_PUBLIC_EXPORTS
    for name in EXPECTED_PUBLIC_EXPORTS:
        assert getattr(aileron_file_core, name)


def test_file_core_does_not_import_domain_or_web_frameworks() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "aileron_file_core"
    forbidden = {
        "fastapi",
        "sqlalchemy",
        "workspace-runtime",
        "workspace_manager",
        "workspace-manager",
        "workspace_runtime",
        "marketplace_workflows",
        "knowledge_base_file_service",
    }

    violations: list[str] = []
    for file_path in source_root.rglob("*.py"):
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        for module_name in imported_modules:
            module_parts = module_name.split(".")
            for token in forbidden:
                if token == module_name or token in module_parts:
                    violations.append(
                        f"{file_path.relative_to(source_root)}:{module_name}"
                    )

    assert violations == []


def test_shared_conformance_checks_hook_and_quota_order() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "aileron_file_core"
        / "conformance.py"
    ).read_text(encoding="utf-8")

    assert "check_quota" in source
    assert "after_size_change" in source
    assert "snapshot_existing" in source
    assert "quota:" in source
    assert "snapshot:" in source
    assert "quota:5" in source
    assert "quota:-5" in source
    assert "validate:copy" in source
    assert "validate:move" in source
    assert "validate:delete" in source
    assert "snapshot:{base_path}/copy.md:move" in source
    assert "snapshot:{base_path}/moved.md:delete" in source
