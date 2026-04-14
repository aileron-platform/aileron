"""多語系服務，負責載入翻譯檔與提供翻譯查詢。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional


class I18nService:
    """簡易的 JSON 翻譯管理服務。"""

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
    # 公開 API
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
        """取得指定語系的翻譯字串，若不存在則回退到預設語系。"""

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
                # 若格式化參數缺失則保留原始字串
                pass

        return value

    def resolve_language(self, language: Optional[str]) -> str:
        """解析語系字串並回傳系統支援的語系。"""

        if not language:
            return self._canonical_map.get(self._normalize(self._default_language), self._default_language)

        # 解析 Accept-Language 風格的輸入，例如 "en-US,en;q=0.9"
        for candidate in self._iter_candidates(language):
            normalized = self._normalize(candidate)
            if normalized in self._canonical_map:
                return self._canonical_map[normalized]

        return self._canonical_map.get(self._normalize(self._default_language), self._default_language)

    def refresh(self) -> None:
        """重新載入翻譯檔。"""

        self._load_translations()

    # ------------------------------------------------------------------
    # 內部工具
    # ------------------------------------------------------------------
    def _get_value(self, language: str, key: str) -> Optional[str]:
        return self._translations.get(language, {}).get(key)

    def _iter_candidates(self, language: str) -> Iterable[str]:
        if "," not in language and ";" not in language:
            yield language
            # 若含有區域碼，將基底語系一併檢查
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
    # 工廠方法
    # ------------------------------------------------------------------


@lru_cache()
def get_i18n_service(translations_path: Optional[Path] = None) -> I18nService:
    """提供快取化的 I18nService 實例。"""

    base_path = translations_path or Path(__file__).resolve().parent.parent / "translations"
    return I18nService(base_path)


__all__ = ["I18nService", "get_i18n_service"]
