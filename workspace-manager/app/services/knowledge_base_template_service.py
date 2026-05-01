"""Knowledge base template service — load and render KB init templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


_TEMPLATES_DIR = Path(__file__).parent.parent / "resources" / "kb_templates"

_REQUIRED_MANIFEST_FIELDS = ("id", "name_key", "description_key", "icon")
_REQUIRED_TEMPLATE_FILES = ("AGENTS.md", "schema.md")


@dataclass(frozen=True)
class KnowledgeBaseTemplateMetadata:
    id: str
    name_key: str
    description_key: str
    icon: str
    extra_dirs: list[str] = field(default_factory=list)


class KnowledgeBaseTemplateService:
    """Load KB templates from resources/kb_templates/ and render them into a KB root."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or _TEMPLATES_DIR
        self._cache: dict[str, KnowledgeBaseTemplateMetadata] | None = None

    # ── public API ──────────────────────────────────────────────────────────

    def list_templates(self) -> list[KnowledgeBaseTemplateMetadata]:
        return list(self._load_all().values())

    def get_template(self, template_id: str) -> KnowledgeBaseTemplateMetadata:
        templates = self._load_all()
        if template_id not in templates:
            raise ValueError(f"KB_TEMPLATE_NOT_FOUND:{template_id}")
        return templates[template_id]

    def render(self, template_id: str, target_root: Path, locale: str = "zh-TW") -> None:
        """Copy template files into target_root; locale-specific files take priority."""
        tmpl = self.get_template(template_id)
        src = self._dir / template_id

        for file_name in ("AGENTS.md", "schema.md"):
            self._write_file(src / file_name, target_root / file_name)

        purpose_src = self._resolve_locale_file(src, "purpose", locale)
        if purpose_src:
            self._write_file(purpose_src, target_root / "purpose.md")

        for extra in tmpl.extra_dirs:
            (target_root / extra).mkdir(parents=True, exist_ok=True)

    def validate_all(self) -> list[str]:
        """Return a list of validation error strings; empty list means all OK."""
        errors: list[str] = []
        for tid, tmpl in self._load_all().items():
            src = self._dir / tid
            for fname in _REQUIRED_TEMPLATE_FILES:
                if not (src / fname).is_file():
                    errors.append(f"{tid}: missing required file {fname}")
            if not self._resolve_locale_file(src, "purpose", "en"):
                errors.append(f"{tid}: missing purpose.en.md or purpose.md")
            for extra in tmpl.extra_dirs:
                if extra.startswith("wiki/"):
                    type_name = extra.removeprefix("wiki/").rstrip("/")
                    schema_text = (src / "schema.md").read_text(encoding="utf-8") if (src / "schema.md").is_file() else ""
                    if type_name not in schema_text:
                        errors.append(f"{tid}: extra_dir '{extra}' not documented in schema.md")
        return errors

    # ── private helpers ─────────────────────────────────────────────────────

    def _load_all(self) -> dict[str, KnowledgeBaseTemplateMetadata]:
        if self._cache is not None:
            return self._cache
        result: dict[str, KnowledgeBaseTemplateMetadata] = {}
        if not self._dir.is_dir():
            self._cache = result
            return result
        for manifest_path in sorted(self._dir.glob("*/manifest.yaml")):
            try:
                raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw, dict):
                    continue
                missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in raw]
                if missing:
                    continue
                tid = str(raw["id"])
                result[tid] = KnowledgeBaseTemplateMetadata(
                    id=tid,
                    name_key=str(raw["name_key"]),
                    description_key=str(raw["description_key"]),
                    icon=str(raw["icon"]),
                    extra_dirs=[str(d) for d in (raw.get("extra_dirs") or [])],
                )
            except Exception:
                continue
        self._cache = result
        return result

    @staticmethod
    def _resolve_locale_file(src: Path, stem: str, locale: str) -> Path | None:
        for suffix in (f".{locale}.md", ".en.md", ".md"):
            candidate = src / f"{stem}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _write_file(src: Path, dst: Path) -> None:
        if not src.is_file():
            return
        if dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
