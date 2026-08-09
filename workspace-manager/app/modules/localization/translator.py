"""Multilingual service, responsible for loading translation files and providing translation lookup."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional


class I18nService:
    """Simple JSON translation management service."""

    def __init__(
        self,
        translations_dir: Path,
        default_language: str = "en",
    ) -> None:
        self._translations_dir = translations_dir
        self._default_language = default_language
        self._translations: Dict[str, Dict[str, str]] = {}
        self._canonical_map: Dict[str, str] = {}
        self._load_translations()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def default_language(self) -> str:
        return self._default_language

    @property
    def supported_languages(self) -> Iterable[str]:
        return self._translations.keys()

    def translate(
        self,
        key: str,
        *,
        language: Optional[str] = None,
        default: Optional[str] = None,
        **kwargs: object,
    ) -> str:
        """Get translation string for specified language, fallback to default language if not exists."""

        target_language = self.resolve_language(language)
        fallback_language = self.resolve_language(self._default_language)

        value = self._get_value(target_language, key)
        if value is None and target_language != fallback_language:
            value = self._get_value(fallback_language, key)

        if value is None:
            value = default if default is not None else key

        if kwargs and isinstance(value, str):
            try:
                value = value.format(**kwargs)
            except (KeyError, IndexError):
                # If formatting parameters missing, preserve original string
                pass

        return value

    def resolve_language(self, language: Optional[str]) -> str:
        """Parse language string and return system supported language."""

        if not language:
            return self._canonical_map.get(
                self._normalize(self._default_language), self._default_language
            )

        # Parse Accept-Language format input, e.g. "en-US,en;q=0.9""
        for candidate in self._iter_candidates(language):
            normalized = self._normalize(candidate)
            if normalized in self._canonical_map:
                return self._canonical_map[normalized]

        return self._canonical_map.get(
            self._normalize(self._default_language), self._default_language
        )

    def refresh(self) -> None:
        """Reload translation files."""

        self._load_translations()

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _get_value(self, language: str, key: str) -> Optional[str]:
        return self._translations.get(language, {}).get(key)

    def _iter_candidates(self, language: str) -> Iterable[str]:
        if "," not in language and ";" not in language:
            yield language
            # If contains region code, also check base language
            if "-" in language:
                yield language.split("-", 1)[0]
            return

        for part in language.split(","):
            code, *_quality = part.split(";", 1)
            code = code.strip()
            if not code:
                continue
            yield code
            if "-" in code:
                yield code.split("-", 1)[0]

    def _normalize(self, language: str) -> str:
        return language.replace("_", "-").lower()

    def _load_translations(self) -> None:
        self._translations.clear()
        self._canonical_map.clear()

        if not self._translations_dir.exists():
            return

        for path in sorted(self._translations_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue

            canonical = path.stem
            normalized = self._normalize(canonical)
            self._translations[canonical] = data
            self._canonical_map[normalized] = canonical

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------


@lru_cache()
def get_i18n_service(translations_path: Optional[Path] = None) -> I18nService:
    """Provide cached I18nService instance."""

    base_path = translations_path or Path(__file__).resolve().parent / "translations"
    return I18nService(base_path)


__all__ = ["I18nService", "get_i18n_service"]
