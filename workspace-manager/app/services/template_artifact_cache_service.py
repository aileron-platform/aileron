"""Canonical template hash/cache/manifest service."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.template_canonical import InstallPlan
from app.services.template_base_service import TemplateBaseService


class TemplateArtifactCacheService(TemplateBaseService):
    """Manage canonical source hash, compile cache, and install manifests."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.cache_root = self.storage_path / ".canonical-cache"
        self.manifest_root = self.storage_path / ".install-manifests"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.manifest_root.mkdir(parents=True, exist_ok=True)

    def compute_source_hash(self, template_root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(template_root.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(template_root).as_posix()
            digest.update(rel_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def build_cache_key(self, template_id: str, target: str, source_hash: str) -> str:
        return f"{template_id}:{target}:{source_hash}"

    def load_compile_cache(self, template_id: str, target: str, source_hash: str) -> Optional[InstallPlan]:
        cache_path = self._cache_path(template_id, target, source_hash)
        if not cache_path.exists():
            return None
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return InstallPlan(**payload)

    def save_compile_cache(self, template_id: str, target: str, source_hash: str, plan: InstallPlan) -> InstallPlan:
        cache_path = self._cache_path(template_id, target, source_hash)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        enriched_plan = plan.model_copy(
            update={
                "source_hash": source_hash,
                "cache_key": self.build_cache_key(template_id, target, source_hash),
            }
        )
        cache_path.write_text(
            json.dumps(enriched_plan.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return enriched_plan

    def record_install_manifest(
        self,
        *,
        workspace_id: str,
        template_id: str,
        target: str,
        plan: InstallPlan,
    ) -> Path:
        manifest_dir = self.manifest_root / workspace_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"{template_id}.json"
        payload: dict[str, Any] = {
            "workspaceId": workspace_id,
            "templateId": template_id,
            "target": target,
            "recordedAt": datetime.utcnow().isoformat(),
            "sourceHash": plan.source_hash,
            "cacheKey": plan.cache_key,
            "files": [item.model_dump(mode="json") for item in plan.files],
            "warnings": [item.model_dump(mode="json") for item in plan.warnings],
            "unsupported": [item.model_dump(mode="json") for item in plan.unsupported],
            "degradationNotes": [item.model_dump(mode="json") for item in plan.degradation_notes],
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest_path

    def load_install_manifest(self, workspace_id: str, template_id: str) -> Optional[dict[str, Any]]:
        manifest_path = self.manifest_root / workspace_id / f"{template_id}.json"
        if not manifest_path.exists():
            return None
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _cache_path(self, template_id: str, target: str, source_hash: str) -> Path:
        return self.cache_root / template_id / target / f"{source_hash}.json"
