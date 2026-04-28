"""Multilingual Testing Helper Functions"""

from __future__ import annotations

from typing import Dict, Optional
from pathlib import Path
import json


class I18nTestHelper:
    """Multilingual testing helper class

    Provides multilingual features needed for testing:
    1. Load translation files
    2. Get translations by language
    3. Verify multilingual messages in API responses
    """
    
    def __init__(self, translations_dir: Optional[Path] = None):
        """Initialize multilingual testing helper

        Args:
            translations_dir: Translation files directory, defaults to app/translations
        """
        if translations_dir is None:
            # Default to workspace-manager/app/translations
            base_path = Path(__file__).resolve().parent.parent.parent / "app" / "translations"
            translations_dir = base_path
        
        self.translations_dir = translations_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()
    
    def _load_translations(self) -> None:
        """Load all translation files"""
        self.translations.clear()
        
        if not self.translations_dir.exists():
            return
        
        for path in sorted(self.translations_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                language = path.stem  # e.g.: en, zh-TW
                self.translations[language] = data
            except json.JSONDecodeError:
                continue
    
    def get_translation(
        self,
        key: str,
        language: str = "en",
        **kwargs
    ) -> str:
        """Get translation string

        Args:
            key: Translation key, e.g. "auth.user_conflict"
            language: Language code, defaults to "en"
            **kwargs: Format parameters

        Returns:
            Translated string
        """
        translations = self.translations.get(language, {})
        value = translations.get(key, key)
        
        if kwargs and isinstance(value, str):
            try:
                value = value.format(**kwargs)
            except (KeyError, IndexError):
                pass
        
        return value
    
    def assert_message_in_response(
        self,
        response_data: dict,
        key: str,
        language: str = "en",
        field: str = "detail",
        **kwargs
    ) -> None:
        """Verify API response contains expected translated message

        Args:
            response_data: API response JSON data
            key: Translation key
            language: Language code
            field: Message field name, defaults to "detail"
            **kwargs: Format parameters
        """
        expected_message = self.get_translation(key, language, **kwargs)
        actual_message = response_data.get(field, "")
        
        assert expected_message.lower() in actual_message.lower(), (
            f"Expected message '{expected_message}' not found in '{actual_message}'"
        )
    
    def assert_message_equals(
        self,
        response_data: dict,
        key: str,
        language: str = "en",
        field: str = "detail",
        **kwargs
    ) -> None:
        """Verify API response message exactly matches expected translation

        Args:
            response_data: API response JSON data
            key: Translation key
            language: Language code
            field: Message field name, defaults to "detail"
            **kwargs: Format parameters
        """
        expected_message = self.get_translation(key, language, **kwargs)
        actual_message = response_data.get(field, "")
        
        assert expected_message == actual_message, (
            f"Expected '{expected_message}' but got '{actual_message}'"
        )
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages"""
        return list(self.translations.keys())
    
    def create_headers(self, language: str = "en") -> dict:
        """Create HTTP headers with language

        Args:
            language: Language code

        Returns:
            Headers containing Accept-Language or X-Language
        """
        return {
            "Accept-Language": language,
            "X-Language": language,
        }

    def assert_contains_any_translation(
        self,
        response_data: dict,
        key: str,
        field: str = "detail",
        **kwargs
    ) -> None:
        """Verify API response contains translation in any language

        This method checks all supported languages, passes if any match.
        Suitable when unsure which language API will return.

        Args:
            response_data: API response JSON data
            key: Translation key
            field: Message field name, defaults to "detail"
            **kwargs: Format parameters
        """
        actual_message = response_data.get(field, "")

        # Check all supported languages
        for language in self.get_supported_languages():
            expected_message = self.get_translation(key, language, **kwargs)
            if expected_message.lower() in actual_message.lower():
                return  # Found match, test passes

        # If no language matches, show all possible translations
        all_translations = [
            f"{lang}: {self.get_translation(key, lang, **kwargs)}"
            for lang in self.get_supported_languages()
        ]
        raise AssertionError(
            f"Response message '{actual_message}' does not match any translation for key '{key}'.\n"
            f"Expected one of:\n" + "\n".join(all_translations)
        )

    def assert_message_contains_keyword(
        self,
        response_data: dict,
        keyword: str,
        field: str = "detail",
    ) -> None:
        """Verify API response contains specific keyword (case insensitive)

        Args:
            response_data: API response JSON data
            keyword: Keyword to search for
            field: Message field name, defaults to "detail"
        """
        actual_message = response_data.get(field, "")
        assert keyword.lower() in actual_message.lower(), (
            f"Keyword '{keyword}' not found in '{actual_message}'"
        )


def get_i18n_test_helper() -> I18nTestHelper:
    """Get singleton instance of multilingual testing helper"""
    if not hasattr(get_i18n_test_helper, "_instance"):
        get_i18n_test_helper._instance = I18nTestHelper()
    return get_i18n_test_helper._instance


__all__ = ["I18nTestHelper", "get_i18n_test_helper"]

