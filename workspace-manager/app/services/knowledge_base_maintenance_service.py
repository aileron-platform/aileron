"""Knowledge base 維護相關背景工作。"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models

logger = logging.getLogger(__name__)


class KnowledgeBaseMaintenanceService:
    """處理 KB 配額校正與 tombstone 清理。"""

    DRIFT_THRESHOLD_RATIO = 0.05

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def reconcile_kb_quota(self) -> dict[str, int]:
        """掃描所有非 tombstoned KB 目錄並校正 cached size。"""

        knowledge_bases = list(
            self.db.scalars(
                select(db_models.KnowledgeBase).where(
                    db_models.KnowledgeBase.tombstoned_at.is_(None)
                )
            ).all()
        )

        updated = 0
        drifted = 0
        for kb in knowledge_bases:
            actual_size = self._calculate_directory_size(self.storage_root / kb.id)
            previous_size = kb.current_size_bytes
            if previous_size != actual_size:
                kb.current_size_bytes = actual_size
                kb.updated_at = datetime.utcnow()
                updated += 1
                if self._has_significant_drift(previous_size, actual_size):
                    drifted += 1
                    logger.warning(
                        "knowledge_base.quota_drift kb_id=%s cached_bytes=%s actual_bytes=%s",
                        kb.id,
                        previous_size,
                        actual_size,
                    )

        if updated:
            self.db.commit()

        logger.info(
            "knowledge base quota reconcile complete processed=%s updated=%s drifted=%s",
            len(knowledge_bases),
            updated,
            drifted,
        )
        return {
            "processed": len(knowledge_bases),
            "updated": updated,
            "drifted": drifted,
        }

    def cleanup_tombstoned_knowledge_bases(self) -> dict[str, int]:
        """清理超過 retention 的 tombstoned KB 與目錄。"""

        cutoff = self._retention_cutoff()
        tombstoned_kbs = list(
            self.db.scalars(
                select(db_models.KnowledgeBase).where(
                    db_models.KnowledgeBase.tombstoned_at.is_not(None),
                    db_models.KnowledgeBase.tombstoned_at <= cutoff,
                )
            ).all()
        )

        deleted = 0
        attachments_deleted = 0
        bytes_freed = 0

        for kb in tombstoned_kbs:
            kb_dir = self.storage_root / kb.id
            size_bytes = self._calculate_directory_size(kb_dir)
            if kb_dir.exists():
                shutil.rmtree(kb_dir)
            bytes_freed += size_bytes

            for attachment in list(getattr(kb, "attachments", []) or []):
                self.db.delete(attachment)
                attachments_deleted += 1

            self.db.delete(kb)
            deleted += 1

        if deleted or attachments_deleted:
            self.db.commit()

        logger.info(
            "knowledge base tombstone cleanup complete deleted=%s attachments_deleted=%s bytes_freed=%s",
            deleted,
            attachments_deleted,
            bytes_freed,
        )
        return {
            "deleted": deleted,
            "attachmentsDeleted": attachments_deleted,
            "bytesFreed": bytes_freed,
        }

    def _retention_cutoff(self):
        return datetime.utcnow() - timedelta(hours=self.settings.KB_TOMBSTONE_RETENTION_HOURS)

    @classmethod
    def _has_significant_drift(cls, previous_size: int, actual_size: int) -> bool:
        baseline = max(previous_size, 1)
        return abs(actual_size - previous_size) / baseline > cls.DRIFT_THRESHOLD_RATIO

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
