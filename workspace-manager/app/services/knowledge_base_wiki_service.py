"""Team Wiki initialization service for knowledge bases."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models


class KnowledgeBaseWikiService:
    """Initialize the canonical Team Wiki file layout for a knowledge base."""

    DIRECTORIES = (
        "raw/sources",
        "raw/uploads",
        "raw/clipped",
        "raw/assets",
        "normalized/text",
        "normalized/metadata",
        "wiki/entities",
        "wiki/concepts",
        "wiki/sources",
        "wiki/queries",
        "wiki/synthesis",
        "wiki/comparisons",
        "wiki/decisions",
        "wiki/projects",
        "reports/ingest",
        "reports/lint",
        "reports/graph",
        ".aileron-kb/vector",
    )

    FILES = {
        "AGENTS.md": """# Team Wiki Agent Instructions

This knowledge base is a team wiki. Treat source material as evidence, keep wiki pages navigable, and preserve citations.

## Rules

- Write durable wiki pages under `wiki/`.
- Store original source material under `raw/`.
- Store normalized text and metadata under `normalized/`.
- Keep `wiki/index.md`, `wiki/overview.md`, and `wiki/log.md` current after indexing.
- Use wikilinks for relationships, such as `[[concepts/example]]`.
- Do not remove source files unless explicitly instructed.
""",
        "purpose.md": """# Purpose

This team wiki captures shared research, decisions, concepts, source summaries, and reusable answers for the attached workspaces.
""",
        "schema.md": """# Wiki Schema

## Required Frontmatter

```yaml
---
title: Page title
type: overview
sources: []
---
```

## Page Types

- overview
- entity
- concept
- source
- query
- synthesis
- comparison
- decision
- project
""",
        "wiki/index.md": """---
title: Index
type: overview
sources: []
---

# Index

- [[overview]]
- [[log]]
""",
        "wiki/log.md": """---
title: Index Log
type: overview
sources: []
---

# Index Log

No wiki index runs have been recorded yet.
""",
        "wiki/overview.md": """---
title: Overview
type: overview
sources: []
---

# Overview

This wiki is ready for source ingestion and indexing.
""",
        ".aileron-kb/ingest-queue.json": "[]\n",
        ".aileron-kb/ingest-cache.json": "{}\n",
        ".aileron-kb/reviews.json": "[]\n",
        ".aileron-kb/graph-cache.json": json.dumps({"nodes": [], "edges": []}, separators=(",", ":")) + "\n",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def initialize(self, kb: db_models.KnowledgeBase) -> db_models.KnowledgeBase:
        """Create missing Team Wiki directories and seed files."""
        root = self._kb_root(kb.id)
        before_size = self._calculate_size(root)
        changed = False

        for directory in self.DIRECTORIES:
            target = root / directory
            if not target.exists():
                changed = True
            target.mkdir(parents=True, exist_ok=True)

        for relative_path, content in self.FILES.items():
            target = root / relative_path
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            changed = True

        after_size = self._calculate_size(root)
        delta = after_size - before_size
        if delta:
            kb.current_size_bytes = max(0, (kb.current_size_bytes or 0) + delta)
        needs_initialized_at = kb.wiki_initialized_at is None
        if needs_initialized_at:
            kb.wiki_initialized_at = datetime.utcnow()
        if changed or delta or needs_initialized_at:
            kb.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(kb)
        return kb

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _calculate_size(self, path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        if not path.exists():
            return 0
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
        return total
