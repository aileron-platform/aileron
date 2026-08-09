"""Shared knowledge base storage path handling."""

from pathlib import Path


def ensure_knowledge_base_storage_root(storage_root: Path, kb_id: str) -> Path:
    """Return the knowledge base root, creating it when necessary."""

    knowledge_base_root = storage_root / kb_id
    knowledge_base_root.mkdir(parents=True, exist_ok=True)
    return knowledge_base_root


__all__ = ["ensure_knowledge_base_storage_root"]
