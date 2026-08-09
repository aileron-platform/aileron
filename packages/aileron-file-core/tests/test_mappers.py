from aileron_file_core.hooks import FileMutationHooks, NoopMutationHooks
from aileron_file_core.mappers import (
    to_file_conflict_preflight,
    to_file_operation_data,
    to_tree_nodes,
    to_upload_batch_result,
    to_upload_items,
)
from aileron_file_core.models import (
    FileConflictItem,
    FileConflictPreflight,
    FileLocator,
    FileMutationResult,
    FileTreeNode,
    UploadBatchResult,
    UploadItemResult,
)


def test_noop_hooks_are_callable_contexts() -> None:
    hooks: FileMutationHooks = NoopMutationHooks()
    locator = FileLocator("workspace", "w1")

    with hooks.write_barrier(locator, "write"):
        hooks.check_quota(locator, 10)
        hooks.after_size_change(locator, 10)
        hooks.validate_after_mutation(locator, "write", ["a.txt"])
        hooks.after_mutation(locator, "write", ["a.txt"])


def test_file_operation_mapper_keeps_domain_neutral_fields() -> None:
    result = FileMutationResult(
        path="docs/readme.md",
        operation="write",
        entry_type="file",
        size=10,
        version_id="sha256:abc",
        updated_at="2026-06-19T00:00:00+00:00",
    )

    assert to_file_operation_data(result) == {
        "path": "docs/readme.md",
        "operation": "write",
        "type": "file",
        "size": 10,
        "versionId": "sha256:abc",
        "updatedAt": "2026-06-19T00:00:00+00:00",
    }


def test_file_operation_mapper_core_fields_override_metadata() -> None:
    result = FileMutationResult(
        path="docs/readme.md",
        operation="write",
        entry_type="file",
        size=10,
        version_id="sha256:abc",
        updated_at="2026-06-19T00:00:00+00:00",
        metadata={
            "path": "wrong",
            "operation": "delete",
            "type": "directory",
            "size": 999,
            "versionId": "wrong",
            "updatedAt": "wrong",
            "domainFlag": True,
        },
    )

    assert to_file_operation_data(result) == {
        "path": "docs/readme.md",
        "operation": "write",
        "type": "file",
        "size": 10,
        "versionId": "sha256:abc",
        "updatedAt": "2026-06-19T00:00:00+00:00",
        "domainFlag": True,
    }


def test_tree_mapper_returns_camel_case_node_data() -> None:
    nodes = [
        FileTreeNode(
            name="readme.md",
            path="docs/readme.md",
            type="file",
            size=5,
            updated_at="2026-06-19T00:00:00+00:00",
            depth=1,
            has_children=False,
            extension=".md",
        )
    ]

    assert to_tree_nodes(nodes) == [
        {
            "name": "readme.md",
            "path": "docs/readme.md",
            "type": "file",
            "size": 5,
            "updatedAt": "2026-06-19T00:00:00+00:00",
            "depth": 1,
            "children": [],
            "hasChildren": False,
            "extension": ".md",
            "metadata": {},
        }
    ]


def test_upload_item_mapper_returns_domain_neutral_payloads() -> None:
    result = UploadBatchResult(
        items=[
            UploadItemResult(
                source_path="readme.md",
                final_path="docs/readme.md",
                status="created",
                size=5,
                updated_at="2026-06-19T00:00:00+00:00",
                entry_type="file",
            ),
            UploadItemResult(
                source_path="bad.md",
                final_path=None,
                status="failed",
                size=0,
                error="FILE_TOO_LARGE",
            ),
        ],
        total=2,
        succeeded=1,
        skipped=0,
        failed=1,
    )

    assert to_upload_items(result) == [
        {
            "sourcePath": "readme.md",
            "finalPath": "docs/readme.md",
            "status": "created",
            "size": 5,
            "type": "file",
            "error": None,
        },
        {
            "sourcePath": "bad.md",
            "finalPath": None,
            "status": "failed",
            "size": 0,
            "type": "file",
            "error": "FILE_TOO_LARGE",
        },
    ]

    assert to_upload_batch_result(result) == {
        "items": to_upload_items(result),
        "total": 2,
        "succeeded": 1,
        "skipped": 0,
        "failed": 1,
    }


def test_file_conflict_preflight_mapper_uses_shared_wire_fields() -> None:
    result = FileConflictPreflight(
        conflicts=(
            FileConflictItem(
                source_path="docs/readme.md",
                target_path="target/docs/readme.md",
                source_type="file",
                target_type="file",
                can_replace=True,
            ),
        ),
        total=1,
    )

    assert to_file_conflict_preflight(result) == {
        "conflicts": [
            {
                "sourcePath": "docs/readme.md",
                "targetPath": "target/docs/readme.md",
                "sourceType": "file",
                "targetType": "file",
                "canReplace": True,
            }
        ],
        "total": 1,
    }
