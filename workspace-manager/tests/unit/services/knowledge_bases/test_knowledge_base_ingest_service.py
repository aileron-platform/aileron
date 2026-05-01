"""Knowledge base ingest service unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from git import Repo

from app.core.file_management import InvalidPathException
from app.db import models as db_models
from app.services.knowledge_base_ingest_service import KnowledgeBaseIngestService, git_blob_sha


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
def test_build_skill_invocation_prompt(ingest_service):
    prompt = ingest_service.build_skill_invocation_prompt(mount_alias="my-kb")
    assert "kb-wiki-index" in prompt
    assert "my-kb" in prompt


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
    assert cache["raw/uploads/research.md"]["ingestedAt"]
    assert set(cache["raw/uploads/research.md"]) == {"sourceHash", "ingestedAt", "generatedFiles"}
    assert kb.last_index_status == "success"
    assert kb.last_index_error is None


@pytest.mark.unit
def test_git_blob_sha_matches_git_hash_object(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    root = ingest_service.storage_root / kb.id
    repo = Repo.init(root, initial_branch="main")

    assert git_blob_sha(root / "raw/uploads/research.md") == repo.git.hash_object("raw/uploads/research.md")


@pytest.mark.unit
def test_discover_candidates_uses_three_cache_rules(ingest_service, kb):
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    generated = ingest_service.storage_root / kb.id / "wiki/generated.md"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text("# Generated\n", encoding="utf-8")
    cache_path = ingest_service.storage_root / kb.id / ".aileron-kb/ingest-cache.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "raw/uploads/research.md": {
                    "sourceHash": ingest_service._hash_file(ingest_service.storage_root / kb.id / "raw/uploads/research.md"),
                    "ingestedAt": "2026-05-01T00:00:00+00:00",
                    "generatedFiles": ["wiki/generated.md"],
                }
            }
        ),
        encoding="utf-8",
    )

    candidates = ingest_service.discover_candidates(kb_id=kb.id, source_paths=["/raw/uploads/research.md"])
    assert candidates[0].skipped is True

    generated.unlink()
    candidates = ingest_service.discover_candidates(kb_id=kb.id, source_paths=["/raw/uploads/research.md"])
    assert candidates[0].skipped is False

    generated.write_text("# Generated\n", encoding="utf-8")
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source changed\n")
    candidates = ingest_service.discover_candidates(kb_id=kb.id, source_paths=["/raw/uploads/research.md"])
    assert candidates[0].skipped is False


@pytest.mark.unit
def test_apply_generation_output_commits_changed_files_when_git_enabled(ingest_service, kb):
    kb.version_control_enabled = True
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    root = ingest_service.storage_root / kb.id
    repo = Repo.init(root, initial_branch="main")
    (root / ".gitignore").write_text(".aileron-kb/\n", encoding="utf-8")
    repo.git.add("--all")
    repo.index.commit("Initialize knowledge base")
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

    repo = Repo(root)
    assert completed.commit_id == repo.head.commit.hexsha
    assert repo.git.status("--porcelain") == ""
    assert repo.head.commit.message.startswith("ingest: 1 source")
    assert repo.head.commit.author.name == "KB Wiki Index"
    assert repo.head.commit.author.email == "wiki-index@aileron.local"
    assert completed.version_control_enabled is True
    queue = json.loads((ingest_service.storage_root / kb.id / ".aileron-kb/ingest-queue.json").read_text(encoding="utf-8"))
    assert queue[0]["versionControlEnabled"] is True
    assert queue[0]["commitId"] == completed.commit_id


@pytest.mark.unit
def test_apply_generation_output_rolls_back_writes_on_commit_failure(ingest_service, kb):
    kb.version_control_enabled = True
    _write_source(ingest_service, kb.id, "/raw/uploads/research.md", "# Source\n")
    job = ingest_service.create_job(
        user_id="owner-1",
        kb_id=kb.id,
        source_paths=["/raw/uploads/research.md"],
    )
    original_index = (ingest_service.storage_root / kb.id / "wiki/index.md").read_text(encoding="utf-8")
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

    with pytest.raises(ValueError, match="GIT_REPO_NOT_FOUND"):
        ingest_service.apply_generation_output(
            user_id="owner-1",
            kb_id=kb.id,
            job_id=job.id,
            output=output,
            source_paths=job.source_paths,
        )

    assert (ingest_service.storage_root / kb.id / "wiki/index.md").read_text(encoding="utf-8") == original_index
    cache = json.loads((ingest_service.storage_root / kb.id / ".aileron-kb/ingest-cache.json").read_text(encoding="utf-8"))
    assert cache == {}
    failed = ingest_service.get_job(user_id="owner-1", kb_id=kb.id, job_id=job.id)
    assert failed.status == "failed"


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
