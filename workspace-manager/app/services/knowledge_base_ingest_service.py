"""Knowledge base ingest and wiki index workflow service."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from git import Actor, GitCommandError, InvalidGitRepositoryError, Repo
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import FileManagementException, InvalidPathException
from app.db import models as db_models
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_browse_service import WikiIndexBuilder
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

KB_INGEST_INVALID_OUTPUT_MESSAGE = "Invalid wiki generation output"
KB_INGEST_PATH_TRAVERSAL_REASON = "Invalid ingest path detected"
KB_INGEST_QUOTA_EXCEEDED_MESSAGE = "Knowledge base storage quota exceeded"
KB_INGEST_OWNER_QUOTA_EXCEEDED_MESSAGE = "User knowledge base total storage quota exceeded"
KB_REVIEW_MAX_ITEMS = 100
KB_WIKI_INDEX_AUTHOR_NAME = "KB Wiki Index"
KB_WIKI_INDEX_AUTHOR_EMAIL = "wiki-index@aileron.local"

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_REVIEW_OPENER_RE = re.compile(
    r"^---\s*REVIEW:\s*([a-z_]+)\s*,\s*([^\n,]+?)\s*,\s*(.+?)\s*---\s*$", re.IGNORECASE
)
_REVIEW_CLOSER_RE = re.compile(r"^---\s*END\s+REVIEW\s*---\s*$", re.IGNORECASE)
_REVIEW_VALID_TYPES = frozenset(
    ["contradiction", "duplicate", "missing_page", "suggestion", "confirm", "unreadable_source"]
)


@dataclass
class ParsedReviewBlock:
    type: str
    page_path: str
    detail: str
    context: str = ""


@dataclass(frozen=True)
class KnowledgeBaseIngestCandidate:
    source_path: str
    source_hash: str
    normalized_path: str | None = None
    normalized_hash: str | None = None
    skipped: bool = False


@dataclass(frozen=True)
class KnowledgeBaseIngestJob:
    id: str
    kb_id: str
    status: str
    source_paths: list[str]
    skipped_sources: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    version_control_enabled: bool = False
    commit_id: str | None = None
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""


class KnowledgeBaseIngestService:
    """Prepare and apply Team Wiki ingest operations."""

    MAX_PROMPT_FILE_CHARS = 24_000
    WRITABLE_PREFIXES = ("wiki/", "reports/ingest/")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)
        self.git_service: Any | None = None
        self.wiki_index_builder = WikiIndexBuilder()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        *,
        user_id: str,
        kb_id: str,
        source_paths: list[str] | None = None,
        force: bool = False,
    ) -> KnowledgeBaseIngestJob:
        """Create an ingest job record and skip unchanged sources by cache."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        candidates = self.discover_candidates(kb_id=kb.id, source_paths=source_paths, force=force)
        active_sources = [candidate.source_path for candidate in candidates if not candidate.skipped]
        skipped_sources = [candidate.source_path for candidate in candidates if candidate.skipped]
        now = self._now()
        job = KnowledgeBaseIngestJob(
            id=str(uuid4()),
            kb_id=kb.id,
            status="queued" if active_sources else "skipped",
            source_paths=active_sources,
            skipped_sources=skipped_sources,
            version_control_enabled=bool(kb.version_control_enabled),
            created_at=now,
            updated_at=now,
        )
        self._append_job(kb.id, job)
        return job

    def list_jobs(self, *, user_id: str, kb_id: str) -> list[KnowledgeBaseIngestJob]:
        """List ingest jobs for a knowledge base."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_wiki(kb)
        return [self._job_from_dict(payload) for payload in self._read_jobs(kb.id)]

    def get_job(self, *, user_id: str, kb_id: str, job_id: str) -> KnowledgeBaseIngestJob:
        """Get a single ingest job."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_wiki(kb)
        return self._get_job(kb.id, job_id)

    def retry_job(self, *, user_id: str, kb_id: str, job_id: str) -> KnowledgeBaseIngestJob:
        """Create a replacement ingest job for a previous ingest attempt."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        previous = self._get_job(kb.id, job_id)
        source_paths = list(dict.fromkeys([*previous.source_paths, *previous.skipped_sources]))
        return self.create_job(user_id=user_id, kb_id=kb.id, source_paths=source_paths or None, force=True)

    def cancel_job(self, *, user_id: str, kb_id: str, job_id: str) -> KnowledgeBaseIngestJob:
        """Cancel an ingest job when it has not reached a terminal state."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        job = self._get_job(kb.id, job_id)
        if job.status not in {"queued", "running"}:
            return job
        return self._update_job(
            kb.id,
            job_id=job_id,
            status="canceled",
            changed_files=job.changed_files,
            version_control_enabled=bool(kb.version_control_enabled),
            commit_id=job.commit_id,
            error=job.error,
        )

    def discover_candidates(
        self,
        *,
        kb_id: str,
        source_paths: list[str] | None = None,
        force: bool = False,
    ) -> list[KnowledgeBaseIngestCandidate]:
        """Find source files that need ingest based on source hash cache."""
        cache = self._read_cache(kb_id)
        raw_paths = source_paths or self._discover_raw_sources(kb_id)
        candidates: list[KnowledgeBaseIngestCandidate] = []
        for source_path in raw_paths:
            normalized_source_path = self._validate_raw_source_path(source_path)
            source = self._resolve_path(kb_id, normalized_source_path)
            if not source.is_file():
                raise FileManagementException(
                    code="FILE_NOT_FOUND",
                    message="Source file does not exist",
                    details={"path": "/" + normalized_source_path},
                    status_code=404,
                )
            source_hash = self._hash_file(source)
            cache_entry = cache.get(normalized_source_path, {})
            normalized_path = cache_entry.get("normalizedTextPath")
            normalized_hash = cache_entry.get("normalizedHash")
            generated_files = cache_entry.get("generatedFiles")
            generated_files_exist = isinstance(generated_files, list) and all(
                isinstance(generated_file, str)
                and self._resolve_path(kb_id, self._validate_path(generated_file)).is_file()
                for generated_file in generated_files
            )
            skipped = (
                not force
                and cache_entry.get("sourceHash") == source_hash
                and generated_files_exist
            )
            candidates.append(
                KnowledgeBaseIngestCandidate(
                    source_path="/" + normalized_source_path,
                    source_hash=source_hash,
                    normalized_path=normalized_path,
                    normalized_hash=normalized_hash,
                    skipped=skipped,
                )
            )
        return candidates

    def build_skill_invocation_prompt(self, *, mount_alias: str) -> str:
        """Build the prompt that invokes the kb-wiki-index skill in workspace-runtime."""
        return f"Run the kb-wiki-index skill. Working directory: /knowledge/{mount_alias}."

    def parse_review_blocks(self, output: str) -> list[ParsedReviewBlock]:
        """Parse ---REVIEW--- blocks from skill output; cap at KB_REVIEW_MAX_ITEMS."""
        results: list[ParsedReviewBlock] = []
        lines = output.splitlines()
        i = 0
        while i < len(lines) and len(results) < KB_REVIEW_MAX_ITEMS:
            m = _REVIEW_OPENER_RE.match(lines[i])
            if m:
                review_type = m.group(1).lower()
                page_path = m.group(2).strip()
                detail = m.group(3).strip()
                if review_type not in _REVIEW_VALID_TYPES:
                    i += 1
                    continue
                context_lines: list[str] = []
                i += 1
                while i < len(lines):
                    if _REVIEW_CLOSER_RE.match(lines[i]):
                        i += 1
                        break
                    context_lines.append(lines[i])
                    i += 1
                results.append(
                    ParsedReviewBlock(
                        type=review_type,
                        page_path=page_path,
                        detail=detail,
                        context="\n".join(context_lines).strip(),
                    )
                )
            else:
                i += 1
        return results

    def parse_generation_output(self, output: str) -> dict[str, str]:
        """Parse structured file updates from generation output."""
        payload_text = output.strip()
        fenced = _JSON_FENCE_RE.search(payload_text)
        if fenced:
            payload_text = fenced.group(1)
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError(KB_INGEST_INVALID_OUTPUT_MESSAGE) from exc

        files = payload.get("files")
        if not isinstance(files, list):
            raise ValueError(KB_INGEST_INVALID_OUTPUT_MESSAGE)

        updates: dict[str, str] = {}
        for item in files:
            if not isinstance(item, dict):
                raise ValueError(KB_INGEST_INVALID_OUTPUT_MESSAGE)
            path = item.get("path")
            content = item.get("content")
            if not isinstance(path, str) or not isinstance(content, str):
                raise ValueError(KB_INGEST_INVALID_OUTPUT_MESSAGE)
            updates[self._validate_writable_path(path)] = content
        return updates

    def apply_generation_output(
        self,
        *,
        user_id: str,
        kb_id: str,
        job_id: str,
        output: str,
        source_paths: list[str],
    ) -> KnowledgeBaseIngestJob:
        """Apply generation output to the KB wiki."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        updates = self.parse_generation_output(output)
        for source_path in source_paths:
            source_summary_path = self._source_summary_path(source_path)
            if source_summary_path not in updates and not self._resolve_path(kb.id, source_summary_path).exists():
                updates[source_summary_path] = self._default_source_summary(source_path)
        snapshots = self._snapshot_paths(
            kb.id,
            [*updates.keys(), ".aileron-kb/ingest-cache.json", ".aileron-kb/wiki-index.json"],
        )
        try:
            generated_files = self._write_updates(kb, updates)
            changed_files = list(generated_files)
            changed_files = self._mark_sources_ingested(
                kb.id,
                source_paths=source_paths,
                generated_files=generated_files,
                changed_files=changed_files,
            )
            changed_files = self._rebuild_wiki_index(kb, changed_files)
            commit_id = self._commit_ingest_results(kb, sources=source_paths, changed_files=changed_files)
            self._update_kb_index_status(kb, status="success", error=None)
            job = self._update_job(
                kb.id,
                job_id=job_id,
                status="success",
                changed_files=changed_files,
                version_control_enabled=bool(kb.version_control_enabled),
                commit_id=commit_id,
                error=None,
            )
            return job
        except Exception as exc:
            self._rollback_partial_writes(kb, snapshots)
            self._update_kb_index_status(kb, status="failed", error=str(exc))
            self._update_job(
                kb.id,
                job_id=job_id,
                status="failed",
                changed_files=[],
                version_control_enabled=bool(kb.version_control_enabled),
                commit_id=None,
                error=str(exc),
            )
            raise

    def fail_job(self, *, kb_id: str, job_id: str, error: str) -> KnowledgeBaseIngestJob:
        """Mark an ingest job failed and persist the KB index status."""
        kb = self.db.get(db_models.KnowledgeBase, kb_id)
        version_control_enabled = False
        if kb is not None:
            version_control_enabled = bool(kb.version_control_enabled)
            self._update_kb_index_status(kb, status="failed", error=error)
        return self._update_job(
            kb_id,
            job_id=job_id,
            status="failed",
            changed_files=[],
            version_control_enabled=version_control_enabled,
            commit_id=None,
            error=error,
        )

    def _write_updates(self, kb: db_models.KnowledgeBase, updates: dict[str, str]) -> list[str]:
        before_size = 0
        after_size = 0
        targets: list[tuple[str, Path, str]] = []
        for relative_path, content in updates.items():
            target = self._resolve_path(kb.id, relative_path)
            before_size += self._path_size(target)
            after_size += len(content.encode("utf-8"))
            targets.append((relative_path, target, content))
        delta = after_size - before_size
        self._check_quota(kb, delta)

        changed_files: list[str] = []
        for relative_path, target, content in targets:
            current_content = target.read_text(encoding="utf-8") if target.exists() else None
            if current_content == content:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            changed_files.append("/" + relative_path)
        if delta:
            self._update_kb_size(kb, delta)
        return changed_files

    def _rebuild_wiki_index(self, kb: db_models.KnowledgeBase, changed_files: list[str]) -> list[str]:
        index_path = self._resolve_path(kb.id, ".aileron-kb/wiki-index.json")
        before_size = self._path_size(index_path)
        before_content = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        self.wiki_index_builder.write(self._kb_root(kb.id))
        after_content = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        if after_content == before_content:
            return changed_files
        delta = self._path_size(index_path) - before_size
        if delta:
            self._update_kb_size(kb, delta)
        normalized_path = "/.aileron-kb/wiki-index.json"
        if normalized_path not in changed_files:
            return [*changed_files, normalized_path]
        return changed_files

    def _mark_sources_ingested(
        self,
        kb_id: str,
        *,
        source_paths: list[str],
        generated_files: list[str],
        changed_files: list[str],
    ) -> list[str]:
        cache = self._read_cache(kb_id)
        now = self._now()
        normalized_generated_files = [self._validate_path(path) for path in generated_files]
        for source_path in source_paths:
            normalized = self._validate_raw_source_path(source_path)
            source = self._resolve_path(kb_id, normalized)
            cache[normalized] = {
                "sourceHash": self._hash_file(source),
                "ingestedAt": now,
                "generatedFiles": normalized_generated_files,
            }
        if self._write_json(kb_id, ".aileron-kb/ingest-cache.json", cache):
            cache_path = "/.aileron-kb/ingest-cache.json"
            if cache_path not in changed_files:
                return [*changed_files, cache_path]
        return changed_files

    def _commit_ingest_results(
        self,
        kb: db_models.KnowledgeBase,
        *,
        sources: list[str],
        changed_files: list[str],
    ) -> str | None:
        if not kb.version_control_enabled or not changed_files:
            return None
        root = self._kb_root(kb.id)
        try:
            repo = Repo(root)
        except (InvalidGitRepositoryError, ValueError) as exc:
            raise ValueError("GIT_REPO_NOT_FOUND") from exc
        repo.git.add("--all")
        if not repo.is_dirty(untracked_files=True):
            return None
        author = Actor(
            os.environ.get("KB_WIKI_INDEX_GIT_AUTHOR_NAME", KB_WIKI_INDEX_AUTHOR_NAME),
            os.environ.get("KB_WIKI_INDEX_GIT_AUTHOR_EMAIL", KB_WIKI_INDEX_AUTHOR_EMAIL),
        )
        commit = repo.index.commit(self._build_ingest_commit_message(sources), author=author, committer=author)
        kb.git_last_commit_sha = commit.hexsha
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
        if repo.is_dirty(untracked_files=True):
            raise ValueError("KB_INGEST_WORKTREE_NOT_CLEAN")
        return commit.hexsha

    def _build_ingest_commit_message(self, sources: list[str]) -> str:
        normalized_sources = ["/" + self._validate_raw_source_path(source) for source in sources]
        subject = f"ingest: {len(normalized_sources)} source" + ("" if len(normalized_sources) == 1 else "s")
        body_paths = normalized_sources[:10]
        body = "\n".join(f"- {path}" for path in body_paths)
        remaining = len(normalized_sources) - len(body_paths)
        if remaining > 0:
            body = f"{body}\n- ... and {remaining} more"
        return f"{subject}\n\n{body}\n" if body else subject

    def _git_service(self) -> Any:
        if self.git_service is not None:
            return self.git_service
        from app.services.knowledge_base_git_service import KnowledgeBaseGitService

        service = KnowledgeBaseGitService(self.db)
        service.storage_root = self.storage_root
        service.wiki_service.storage_root = self.storage_root
        self.git_service = service
        return service

    def _append_job(self, kb_id: str, job: KnowledgeBaseIngestJob) -> None:
        jobs = self._read_jobs(kb_id)
        jobs.append(self._job_to_dict(job))
        self._write_json(kb_id, ".aileron-kb/ingest-queue.json", jobs)

    def _get_job(self, kb_id: str, job_id: str) -> KnowledgeBaseIngestJob:
        for job in self._read_jobs(kb_id):
            if job.get("id") == job_id:
                return self._job_from_dict(job)
        raise LookupError("Knowledge base ingest job does not exist")

    def _update_job(
        self,
        kb_id: str,
        *,
        job_id: str,
        status: str,
        changed_files: list[str],
        error: str | None,
        version_control_enabled: bool,
        commit_id: str | None,
    ) -> KnowledgeBaseIngestJob:
        jobs = self._read_jobs(kb_id)
        for job in jobs:
            if job.get("id") == job_id:
                job["status"] = status
                job["changedFiles"] = changed_files
                job["versionControlEnabled"] = version_control_enabled
                job["commitId"] = commit_id
                job["error"] = error
                job["updatedAt"] = self._now()
                self._write_json(kb_id, ".aileron-kb/ingest-queue.json", jobs)
                return self._job_from_dict(job)
        raise LookupError("Knowledge base ingest job does not exist")

    def _read_jobs(self, kb_id: str) -> list[dict[str, Any]]:
        path = self._resolve_path(kb_id, ".aileron-kb/ingest-queue.json")
        if not path.exists():
            return []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, list) else []
        except json.JSONDecodeError:
            return []

    def _read_cache(self, kb_id: str) -> dict[str, Any]:
        path = self._resolve_path(kb_id, ".aileron-kb/ingest-cache.json")
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _write_json(self, kb_id: str, relative_path: str, payload: Any) -> bool:
        target = self._resolve_path(kb_id, relative_path)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        current_content = target.read_text(encoding="utf-8") if target.exists() else None
        if current_content == content:
            return False
        before_size = self._path_size(target)
        delta = len(content.encode("utf-8")) - before_size
        kb = self.db.get(db_models.KnowledgeBase, kb_id)
        if kb is not None:
            self._check_quota(kb, delta)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if kb is not None:
            self._update_kb_size(kb, delta)
        return True

    def _discover_raw_sources(self, kb_id: str) -> list[str]:
        root = self._kb_root(kb_id)
        raw_root = root / "raw"
        if not raw_root.exists():
            return []
        paths = [
            "/" + str(path.relative_to(root)).replace("\\", "/")
            for path in raw_root.rglob("*")
            if path.is_file()
        ]
        return sorted(paths)

    def _preferred_source_context_path(self, kb_id: str, raw_relative_path: str) -> str:
        cache_entry = self._read_cache(kb_id).get(raw_relative_path, {})
        normalized = cache_entry.get("normalizedTextPath")
        if isinstance(normalized, str):
            normalized_path = self._validate_path(normalized)
            if self._resolve_path(kb_id, normalized_path).exists():
                return normalized_path
        return raw_relative_path

    def _prompt_file_section(self, kb_id: str, relative_path: str, *, label: str | None = None) -> str:
        normalized = self._validate_path(relative_path)
        target = self._resolve_path(kb_id, normalized)
        content = ""
        if target.exists() and target.is_file():
            try:
                content = target.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = target.read_text(encoding="latin-1")
        if len(content) > self.MAX_PROMPT_FILE_CHARS:
            content = content[: self.MAX_PROMPT_FILE_CHARS] + "\n[TRUNCATED]\n"
        display_path = label or "/" + normalized
        return f"## File: {display_path}\n\n```text\n{content}\n```\n"

    def _source_summary_path(self, source_path: str) -> str:
        normalized = self._validate_raw_source_path(source_path)
        source = Path(normalized)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        return f"wiki/sources/{source.stem}-{digest}.md"

    def _default_source_summary(self, source_path: str) -> str:
        normalized = self._validate_raw_source_path(source_path)
        title = Path(normalized).stem.replace("-", " ").replace("_", " ").title()
        return (
            "---\n"
            f"title: {json.dumps(title, ensure_ascii=False)}\n"
            "type: source\n"
            "sources:\n"
            f"  - {json.dumps('/' + normalized, ensure_ascii=False)}\n"
            "---\n\n"
            f"# {title}\n\n"
            f"Source: `/{normalized}`\n"
        )

    def _update_kb_index_status(self, kb: db_models.KnowledgeBase, *, status: str, error: str | None) -> None:
        kb.last_indexed_at = datetime.utcnow()
        kb.last_index_status = status
        kb.last_index_error = error
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)

    def _validate_writable_path(self, path: str) -> str:
        normalized = self._validate_path(path)
        if not normalized.endswith(".md") and not normalized.startswith("reports/ingest/"):
            raise InvalidPathException(path, KB_INGEST_PATH_TRAVERSAL_REASON)
        if not normalized.startswith(self.WRITABLE_PREFIXES):
            raise InvalidPathException(path, KB_INGEST_PATH_TRAVERSAL_REASON)
        return normalized

    def _validate_raw_source_path(self, source_path: str) -> str:
        normalized = self._validate_path(source_path)
        parts = Path(normalized).parts
        if len(parts) < 3 or parts[0] != "raw" or parts[1] not in {"sources", "uploads", "clipped", "assets"}:
            raise InvalidPathException(source_path, KB_INGEST_PATH_TRAVERSAL_REASON)
        return normalized

    def _validate_path(self, path: str) -> str:
        normalized = (path or "").strip().lstrip("/")
        if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
            raise InvalidPathException(path, KB_INGEST_PATH_TRAVERSAL_REASON)
        return normalized

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        target = root / self._validate_path(relative_path)
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise InvalidPathException(relative_path, KB_INGEST_PATH_TRAVERSAL_REASON)
        return resolved

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ensure_wiki(self, kb: db_models.KnowledgeBase) -> None:
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

    def _hash_file(self, path: Path) -> str:
        return git_blob_sha(path)

    def _snapshot_paths(self, kb_id: str, relative_paths: list[str]) -> dict[str, bytes | None]:
        snapshots: dict[str, bytes | None] = {}
        for relative_path in relative_paths:
            normalized = self._validate_path(relative_path)
            if normalized in snapshots:
                continue
            target = self._resolve_path(kb_id, normalized)
            snapshots[normalized] = target.read_bytes() if target.exists() and target.is_file() else None
        return snapshots

    def _rollback_partial_writes(self, kb: db_models.KnowledgeBase, snapshots: dict[str, bytes | None]) -> None:
        root = self._kb_root(kb.id)
        for relative_path, content in snapshots.items():
            target = self._resolve_path(kb.id, relative_path)
            before_size = self._path_size(target)
            if content is None:
                if target.exists() and target.is_file():
                    target.unlink()
                    self._update_kb_size(kb, -before_size)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            self._update_kb_size(kb, len(content) - before_size)
        if kb.version_control_enabled:
            try:
                Repo(root).git.reset("--mixed")
            except (GitCommandError, InvalidGitRepositoryError, ValueError):
                pass

    def _path_size(self, path: Path) -> int:
        return path.stat().st_size if path.exists() and path.is_file() else 0

    def _check_quota(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        if delta_bytes <= 0:
            return
        per_kb_quota = kb.quota_bytes or self.settings.DEFAULT_KB_QUOTA_BYTES
        if kb.current_size_bytes + delta_bytes > per_kb_quota:
            raise FileManagementException(
                code="KB_QUOTA_EXCEEDED",
                message=KB_INGEST_QUOTA_EXCEEDED_MESSAGE,
                details={
                    "kbId": kb.id,
                    "currentSizeBytes": kb.current_size_bytes,
                    "deltaBytes": delta_bytes,
                    "quotaBytes": per_kb_quota,
                },
                status_code=409,
            )

        owner_total = (
            self.db.scalar(
                select(func.coalesce(func.sum(db_models.KnowledgeBase.current_size_bytes), 0)).where(
                    db_models.KnowledgeBase.owner_id == kb.owner_id,
                    db_models.KnowledgeBase.tombstoned_at.is_(None),
                )
            )
            or 0
        )
        if owner_total + delta_bytes > self.settings.DEFAULT_USER_KB_QUOTA_BYTES:
            raise FileManagementException(
                code="USER_KB_QUOTA_EXCEEDED",
                message=KB_INGEST_OWNER_QUOTA_EXCEEDED_MESSAGE,
                details={
                    "ownerId": kb.owner_id,
                    "currentTotalBytes": owner_total,
                    "deltaBytes": delta_bytes,
                    "quotaBytes": self.settings.DEFAULT_USER_KB_QUOTA_BYTES,
                },
                status_code=409,
            )

    def _update_kb_size(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        if delta_bytes == 0:
            return
        kb.current_size_bytes = max(0, (kb.current_size_bytes or 0) + delta_bytes)
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)

    def _job_to_dict(self, job: KnowledgeBaseIngestJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "kbId": job.kb_id,
            "status": job.status,
            "sourcePaths": job.source_paths,
            "skippedSources": job.skipped_sources,
            "changedFiles": job.changed_files,
            "versionControlEnabled": job.version_control_enabled,
            "commitId": job.commit_id,
            "error": job.error,
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
        }

    def _job_from_dict(self, payload: dict[str, Any]) -> KnowledgeBaseIngestJob:
        return KnowledgeBaseIngestJob(
            id=payload["id"],
            kb_id=payload["kbId"],
            status=payload["status"],
            source_paths=list(payload.get("sourcePaths", [])),
            skipped_sources=list(payload.get("skippedSources", [])),
            changed_files=list(payload.get("changedFiles", [])),
            version_control_enabled=bool(payload.get("versionControlEnabled", False)),
            commit_id=payload.get("commitId"),
            error=payload.get("error"),
            created_at=payload.get("createdAt", ""),
            updated_at=payload.get("updatedAt", ""),
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


def git_blob_sha(path: Path) -> str:
    """Return the Git blob object id for a file's current bytes."""
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode("utf-8")
    return hashlib.sha1(header + content).hexdigest()
