"""Knowledge base ingest service unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.core.file_management import InvalidPathException
from app.db import models as db_models
from app.services.knowledge_base_ingest_service import KnowledgeBaseIngestService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.scalar = MagicMock(return_value=0)
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.get = MagicMock(return_value=None)
    return session


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
        version_control_enabled=False,
        git_lfs_enabled=False,
        git_default_branch="main",
    )


@pytest.fixture
def ingest_service(mock_db_session, kb, tmp_path):
    service = KnowledgeBaseIngestService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb = MagicMock(return_value=(kb, type("Access", (), {"access_role": "editor"})()))
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100_000
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100_000
    mock_db_session.get.return_value = kb
    return service


def _write_source(service: KnowledgeBaseIngestService, kb_id: str, path: str, content: str = "source") -> None:
    target = service.storage_root / kb_id / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_create_job_persists_queue_and_sources(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")

    job = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )

    queue_path = ingest_service.storage_root / kb.id / ".aileron-kb/ingest-queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert job.status == "queued"
    assert job.source_paths == ["/raw/uploads/research.md"]
    assert queue[0]["id"] == job.id
    assert queue[0]["status"] == "queued"
    assert queue[0]["versionControlEnabled"] is False
    assert queue[0]["commitId"] is None


@pytest.mark.unit
def test_create_job_skips_unchanged_source_after_successful_ingest(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    first = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )
    output = json.dumps(
        {
            "files": [
                {
                    "path": "wiki/index.md",
                    "content": "---\ntitle: Index\ntype: overview\nsources: []\n---\n\n# Index\n",
                }
            ]
        }
    )
    ingest_service.apply_generation_output(
        user_id="owner-1",
        kb_id=kb.id,
        job_id=first.id,
        output=output,
        source_paths=first.source_paths,
    )

    second = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )

    assert second.status == "skipped"
    assert second.source_paths == []
    assert second.skipped_sources == ["/raw/uploads/research.md"]


@pytest.mark.unit
def test_build_analysis_prompt_uses_normalized_source_when_available(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "raw text")
    normalized = ingest_service.storage_root / kb.id / "normalized/text/research.md"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_text("normalized text", encoding="utf-8")
    cache = {
        "raw/uploads/research.md": {
            "sourceHash": "hash",
            "normalizedTextPath": "/normalized/text/research.md",
        }
    }
    cache_path = ingest_service.storage_root / kb.id / ".aileron-kb/ingest-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    ingest_service.wiki_service.storage_root = ingest_service.storage_root
    ingest_service.wiki_service.initialize(kb)

    prompt = ingest_service.build_analysis_prompt(
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )

    assert "## File: /raw/uploads/research.md" in prompt
    assert "normalized text" in prompt
    assert "raw text" not in prompt
    assert "purpose.md" in prompt
    assert "schema.md" in prompt


@pytest.mark.unit
def test_generation_prompt_requests_structured_file_blocks(ingest_service):
    prompt = ingest_service.build_generation_prompt(
        analysis="Create source summary.",
        source_paths=["/raw/uploads/research.md"],
    )

    assert "\"files\"" in prompt
    assert "\"path\"" in prompt
    assert "Only write under wiki/ or reports/ingest/" in prompt
    assert "/raw/uploads/research.md" in prompt


@pytest.mark.unit
def test_parse_generation_output_accepts_json_fence(ingest_service):
    output = """```json
{"files":[{"path":"wiki/sources/research.md","content":"# Research"}]}
```"""

    updates = ingest_service.parse_generation_output(output)

    assert updates == {"wiki/sources/research.md": "# Research"}


@pytest.mark.unit
def test_parse_generation_output_rejects_paths_outside_kb(ingest_service):
    output = json.dumps({"files": [{"path": "../outside.md", "content": "x"}]})

    with pytest.raises(InvalidPathException):
        ingest_service.parse_generation_output(output)


@pytest.mark.unit
def test_apply_generation_output_writes_updates_source_summary_and_status(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    job = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )
    output = json.dumps(
        {
            "files": [
                {
                    "path": "wiki/index.md",
                    "content": "---\ntitle: Index\ntype: overview\nsources: []\n---\n\n# Index\n- [[sources/research]]\n",
                },
                {
                    "path": "wiki/log.md",
                    "content": "---\ntitle: Log\ntype: overview\nsources: []\n---\n\n# Log\n- Indexed research\n",
                },
                {
                    "path": "wiki/overview.md",
                    "content": "---\ntitle: Overview\ntype: overview\nsources: []\n---\n\n# Overview\nUpdated\n",
                },
            ]
        }
    )

    completed = ingest_service.apply_generation_output(
        user_id="owner-1",
        kb_id=kb.id,
        job_id=job.id,
        output=output,
        source_paths=job.source_paths,
    )

    assert completed.status == "success"
    assert "/wiki/index.md" in completed.changed_files
    assert completed.version_control_enabled is False
    assert completed.commit_id is None
    assert (ingest_service.storage_root / kb.id / "wiki/index.md").read_text(encoding="utf-8").endswith(
        "- [[sources/research]]\n"
    )
    source_summaries = list((ingest_service.storage_root / kb.id / "wiki/sources").glob("research-*.md"))
    assert len(source_summaries) == 1
    assert "/raw/uploads/research.md" in source_summaries[0].read_text(encoding="utf-8")
    cache = json.loads((ingest_service.storage_root / kb.id / ".aileron-kb/ingest-cache.json").read_text(encoding="utf-8"))
    assert cache["raw/uploads/research.md"]["lastIngestedAt"]
    assert kb.last_index_status == "success"
    assert kb.last_index_error is None


@pytest.mark.unit
def test_apply_generation_output_commits_changed_files_when_git_enabled(ingest_service, kb):
    kb.version_control_enabled = True
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    job = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )
    ingest_service.git_service = MagicMock()
    ingest_service.git_service.commit.return_value = type(
        "CommitResponse",
        (),
        {"commit": type("Commit", (), {"id": "abc1234"})()},
    )()
    output = json.dumps(
        {
            "files": [
                {
                    "path": "wiki/index.md",
                    "content": "---\ntitle: Index\ntype: overview\nsources: []\n---\n\n# Index\nUpdated\n",
                }
            ]
        }
    )

    completed = ingest_service.apply_generation_output(
        user_id="owner-1",
        kb_id=kb.id,
        job_id=job.id,
        output=output,
        source_paths=job.source_paths,
    )

    ingest_service.git_service.commit.assert_called_once()
    call_kwargs = ingest_service.git_service.commit.call_args.kwargs
    assert call_kwargs["user_id"] == "owner-1"
    assert call_kwargs["kb_id"] == kb.id
    assert call_kwargs["message"] == "Update knowledge base wiki index"
    assert "wiki/index.md" in call_kwargs["paths"]
    assert all(not path.startswith("/") for path in call_kwargs["paths"])
    assert completed.version_control_enabled is True
    assert completed.commit_id == "abc1234"
    queue = json.loads((ingest_service.storage_root / kb.id / ".aileron-kb/ingest-queue.json").read_text(encoding="utf-8"))
    assert queue[0]["versionControlEnabled"] is True
    assert queue[0]["commitId"] == "abc1234"


@pytest.mark.unit
def test_fail_job_updates_status_and_error(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    job = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )

    failed = ingest_service.fail_job(kb_id=kb.id, job_id=job.id, error="LLM_FAILED")

    assert failed.status == "failed"
    assert failed.error == "LLM_FAILED"
    assert kb.last_index_status == "failed"
    assert kb.last_index_error == "LLM_FAILED"
