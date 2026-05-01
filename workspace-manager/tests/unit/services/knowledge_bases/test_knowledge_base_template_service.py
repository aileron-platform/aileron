"""Knowledge base template service unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.services.knowledge_base_template_service import KnowledgeBaseTemplateService


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    for tid, extra in [
        ("general", []),
        ("research", ["wiki/methodology", "wiki/findings", "wiki/thesis"]),
        ("reading", ["wiki/characters", "wiki/themes"]),
    ]:
        tdir = tmp_path / tid
        tdir.mkdir()
        manifest = {
            "id": tid,
            "name_key": f"knowledgeBase.template.{tid}.name",
            "description_key": f"knowledgeBase.template.{tid}.description",
            "icon": "FileText",
            "extra_dirs": extra,
        }
        (tdir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
        (tdir / "AGENTS.md").write_text(f"# {tid} AGENTS\n", encoding="utf-8")
        (tdir / "schema.md").write_text(
            f"# {tid} Schema\n\n" + "\n".join(e.split("/")[1] for e in extra),
            encoding="utf-8",
        )
        (tdir / "purpose.en.md").write_text(f"# {tid} Purpose\n", encoding="utf-8")
        (tdir / "purpose.zh-TW.md").write_text(f"# {tid} 目的\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def service(templates_dir: Path) -> KnowledgeBaseTemplateService:
    return KnowledgeBaseTemplateService(templates_dir=templates_dir)


@pytest.mark.unit
def test_list_templates_returns_all(service: KnowledgeBaseTemplateService) -> None:
    templates = service.list_templates()
    ids = {t.id for t in templates}
    assert ids == {"general", "research", "reading"}


@pytest.mark.unit
def test_get_template_returns_metadata(service: KnowledgeBaseTemplateService) -> None:
    tmpl = service.get_template("research")
    assert tmpl.id == "research"
    assert tmpl.icon == "FileText"
    assert "wiki/methodology" in tmpl.extra_dirs


@pytest.mark.unit
def test_get_template_raises_for_unknown(service: KnowledgeBaseTemplateService) -> None:
    with pytest.raises(ValueError, match="KB_TEMPLATE_NOT_FOUND"):
        service.get_template("nonexistent")


@pytest.mark.unit
def test_render_copies_files_and_creates_extra_dirs(service: KnowledgeBaseTemplateService, tmp_path: Path) -> None:
    target = tmp_path / "kb"
    target.mkdir()
    service.render("research", target, locale="en")

    assert (target / "AGENTS.md").is_file()
    assert (target / "schema.md").is_file()
    assert (target / "purpose.md").is_file()
    assert "# research AGENTS" in (target / "AGENTS.md").read_text()
    assert (target / "wiki/methodology").is_dir()
    assert (target / "wiki/findings").is_dir()
    assert (target / "wiki/thesis").is_dir()


@pytest.mark.unit
def test_render_locale_fallback(service: KnowledgeBaseTemplateService, tmp_path: Path) -> None:
    target = tmp_path / "kb"
    target.mkdir()
    service.render("general", target, locale="zh-TW")
    assert "目的" in (target / "purpose.md").read_text(encoding="utf-8")

    target2 = tmp_path / "kb2"
    target2.mkdir()
    service.render("general", target2, locale="fr")
    assert "Purpose" in (target2 / "purpose.md").read_text(encoding="utf-8")


@pytest.mark.unit
def test_render_does_not_overwrite_existing(service: KnowledgeBaseTemplateService, tmp_path: Path) -> None:
    target = tmp_path / "kb"
    target.mkdir()
    (target / "AGENTS.md").write_text("# Custom\n", encoding="utf-8")
    service.render("general", target, locale="en")
    assert (target / "AGENTS.md").read_text() == "# Custom\n"


@pytest.mark.unit
def test_validate_all_passes_for_good_templates(service: KnowledgeBaseTemplateService) -> None:
    errors = service.validate_all()
    assert errors == []


@pytest.mark.unit
def test_wiki_service_uses_template_on_initialize(tmp_path: Path) -> None:
    from unittest.mock import MagicMock
    from app.db import models as db_models
    from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        template_id="research",
    )

    service = KnowledgeBaseWikiService(mock_db)
    service.storage_root = tmp_path

    service.initialize(kb)

    root = tmp_path / "kb-1"
    assert (root / "wiki/methodology").is_dir()
    assert (root / "wiki/findings").is_dir()
    assert (root / "wiki/thesis").is_dir()
    assert (root / "AGENTS.md").is_file()
    assert (root / "wiki/index.md").is_file()
