"""Knowledge base maintenance related background tasks."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models

logger = logging.getLogger(__name__)


class KnowledgeBaseMaintenanceService:
    """Handle knowledge base quota reconciliation."""

    DRIFT_THRESHOLD_RATIO = 0.05

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def reconcile_kb_quota(self) -> dict[str, int]:
        """Scan all knowledge base directories and reconcile cached size."""

        knowledge_bases = list(self.db.scalars(select(db_models.KnowledgeBase)).all())

        updated = 0
        drifted = 0
        for kb in knowledge_bases:
            actual_size = self._calculate_directory_size(
                self.storage_root / kb.id,
            )
            previous_size = kb.current_size_bytes
            if previous_size != actual_size:
                kb.current_size_bytes = actual_size
                kb.updated_at = datetime.utcnow()
                updated += 1
                if self._has_significant_drift(previous_size, actual_size):
                    drifted += 1
                    logger.warning(
                        "knowledge_base.quota_drift kb_id=%s "
                        "cached_bytes=%s actual_bytes=%s",
                        kb.id,
                        previous_size,
                        actual_size,
                    )

        if updated:
            self.db.commit()

        logger.info(
            "knowledge base quota reconcile complete processed=%s "
            "updated=%s drifted=%s",
            len(knowledge_bases),
            updated,
            drifted,
        )
        return {
            "processed": len(knowledge_bases),
            "updated": updated,
            "drifted": drifted,
        }

    @classmethod
    def _has_significant_drift(
        cls,
        previous_size: int,
        actual_size: int,
    ) -> bool:
        baseline = max(previous_size, 1)
        drift_ratio = abs(actual_size - previous_size) / baseline
        return drift_ratio > cls.DRIFT_THRESHOLD_RATIO

    @staticmethod
    def _calculate_directory_size(path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_file():
            return path.stat().st_size
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
        return total
