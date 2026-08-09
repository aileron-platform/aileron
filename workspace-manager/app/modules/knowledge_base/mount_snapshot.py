"""Canonical Workspace knowledge mount snapshot validation."""

from __future__ import annotations

from typing import NotRequired, TypedDict
from uuid import UUID

from app.modules.knowledge_base.mount_contract import validate_mount_alias

_SNAPSHOT_KEYS = {
    "attachmentId",
    "knowledgeBaseId",
    "mountAlias",
    "attachedById",
}


class KnowledgeBaseMountSnapshotEntry(TypedDict):
    attachmentId: str
    knowledgeBaseId: str
    mountAlias: str
    attachedById: NotRequired[str | None]


def canonical_mount_snapshot(
    value: object,
) -> list[KnowledgeBaseMountSnapshotEntry]:
    """Validate and deterministically order a server-owned mount snapshot."""

    if not isinstance(value, list):
        raise ValueError("Knowledge mount snapshot must be a list")

    entries: list[KnowledgeBaseMountSnapshotEntry] = []
    attachment_ids: set[str] = set()
    knowledge_base_ids: set[str] = set()
    aliases: set[str] = set()
    for raw_entry in value:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _SNAPSHOT_KEYS:
            raise ValueError("Knowledge mount snapshot entry is invalid")
        attachment_id = _canonical_uuid(
            raw_entry.get("attachmentId"),
            label="Attachment identifier",
        )
        knowledge_base_id = _canonical_uuid(
            raw_entry.get("knowledgeBaseId"),
            label="Knowledge base identifier",
        )
        mount_alias = validate_mount_alias(raw_entry.get("mountAlias"))
        attached_by_id = raw_entry.get("attachedById")
        if attached_by_id is not None and (
            not isinstance(attached_by_id, str)
            or not attached_by_id
            or len(attached_by_id) > 128
        ):
            raise ValueError("Attachment actor identifier is invalid")
        if (
            attachment_id in attachment_ids
            or knowledge_base_id in knowledge_base_ids
            or mount_alias in aliases
        ):
            raise ValueError("Knowledge mount snapshot contains a collision")
        attachment_ids.add(attachment_id)
        knowledge_base_ids.add(knowledge_base_id)
        aliases.add(mount_alias)
        entries.append(
            {
                "attachmentId": attachment_id,
                "knowledgeBaseId": knowledge_base_id,
                "mountAlias": mount_alias,
                "attachedById": attached_by_id,
            }
        )
    return sorted(entries, key=lambda item: item["attachmentId"])


def _canonical_uuid(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is invalid")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"{label} is invalid") from exc
    if str(parsed) != value:
        raise ValueError(f"{label} is invalid")
    return value


__all__ = [
    "KnowledgeBaseMountSnapshotEntry",
    "canonical_mount_snapshot",
]
