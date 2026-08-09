from __future__ import annotations

from typing import Iterable

from .models import (
    FileConflictPreflight,
    FileMutationResult,
    FileTreeNode,
    UploadBatchResult,
    UploadItemResult,
)


def to_file_operation_data(result: FileMutationResult) -> dict:
    payload = {
        **result.metadata,
        "path": result.path,
        "operation": result.operation,
        "type": result.entry_type,
        "size": result.size,
    }
    if result.version_id is not None:
        payload["versionId"] = result.version_id
    if result.updated_at is not None:
        payload["updatedAt"] = result.updated_at
    return payload


def to_tree_nodes(nodes: Iterable[FileTreeNode]) -> list[dict]:
    return [_to_tree_node(node) for node in nodes]


def to_upload_items(result: UploadBatchResult | Iterable[UploadItemResult]) -> list[dict]:
    items = result.items if isinstance(result, UploadBatchResult) else result
    return [_to_upload_item(item) for item in items]


def to_upload_batch_result(result: UploadBatchResult) -> dict:
    return {
        "items": to_upload_items(result),
        "total": result.total,
        "succeeded": result.succeeded,
        "skipped": result.skipped,
        "failed": result.failed,
    }


def to_file_conflict_preflight(result: FileConflictPreflight) -> dict:
    return {
        "conflicts": [
            {
                "sourcePath": item.source_path,
                "targetPath": item.target_path,
                "sourceType": item.source_type,
                "targetType": item.target_type,
                "canReplace": item.can_replace,
            }
            for item in result.conflicts
        ],
        "total": result.total,
    }


def _to_tree_node(node: FileTreeNode) -> dict:
    return {
        "name": node.name,
        "path": node.path,
        "type": node.type,
        "size": node.size,
        "updatedAt": node.updated_at,
        "depth": node.depth,
        "children": to_tree_nodes(node.children),
        "hasChildren": node.has_children,
        "extension": node.extension,
        "metadata": dict(node.metadata),
    }


def _to_upload_item(item: UploadItemResult) -> dict:
    payload = {
        "sourcePath": item.source_path,
        "finalPath": item.final_path,
        "status": item.status,
        "size": item.size,
        "type": item.entry_type,
        "error": item.error,
    }
    return payload
