"""Workspace Runtime 多語系服務。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path as PathType
from typing import Dict, Iterable, Optional


class I18nService:
    """管理運行時翻譯字串的服務。"""

    def __init__(
        self,
        translations_dir: PathType,
        default_language: str = "zh-TW",
    ) -> None:
        self._translations_dir = translations_dir
        self._default_language = default_language
        self._translations: Dict[str, Dict[str, str]] = {}
        self._canonical_map: Dict[str, str] = {}
        self._load_translations()

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
                pass

        return value

    def resolve_language(self, language: Optional[str]) -> str:
        if not language:
            return self._canonical_map.get(self._normalize(self._default_language), self._default_language)

        for candidate in self._iter_candidates(language):
            normalized = self._normalize(candidate)
            if normalized in self._canonical_map:
                return self._canonical_map[normalized]

        return self._canonical_map.get(self._normalize(self._default_language), self._default_language)

    def refresh(self) -> None:
        self._load_translations()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_value(self, language: str, key: str) -> Optional[str]:
        return self._translations.get(language, {}).get(key)

    def _iter_candidates(self, language: str):
        if "," not in language and ";" not in language:
            yield language
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


@lru_cache()
def get_i18n_service() -> I18nService:
    """取得 I18n 服務實例（用於 FastAPI 依賴注入）"""
    base_path = PathType(__file__).resolve().parent.parent / "translations"
    return I18nService(base_path)


__all__ = ["I18nService", "get_i18n_service"]
