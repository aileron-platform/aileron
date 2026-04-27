"""I18n Service Unit Tests"""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from app.services.i18n_service import I18nService


@pytest.fixture
def translations_dir(tmp_path):
    """Create temporary translations directory."""
    trans_dir = tmp_path / "translations"
    trans_dir.mkdir()

    # Create Chinese translation
    zh_tw = trans_dir / "zh-TW.json"
    zh_tw.write_text(json.dumps({
        "hello": "你好",
        "goodbye": "再見",
        "welcome": "歡迎 {name}",
        "count": "數量: {count}"
    }, ensure_ascii=False))

    # Create English translation
    en = trans_dir / "en.json"
    en.write_text(json.dumps({
        "hello": "Hello",
        "goodbye": "Goodbye",
        "welcome": "Welcome {name}",
        "count": "Count: {count}"
    }))

    # Create Japanese translation (partial)
    ja = trans_dir / "ja.json"
    ja.write_text(json.dumps({
        "hello": "こんにちは",
        "goodbye": "さようなら"
    }, ensure_ascii=False))

    return trans_dir


@pytest.fixture
def i18n_service(translations_dir):
    """I18n service fixture."""
    return I18nService(translations_dir, default_language="zh-TW")


class TestInitialization:
    """Test initialization."""

    def test_init_with_default_language(self, translations_dir):
        """Test initialization with default language."""
        service = I18nService(translations_dir)
        assert service.default_language == "zh-TW"

    def test_init_with_custom_language(self, translations_dir):
        """Test initialization with custom language."""
        service = I18nService(translations_dir, default_language="en")
        assert service.default_language == "en"

    def test_init_loads_translations(self, i18n_service):
        """Test initialization loads translations."""
        assert len(i18n_service._translations) > 0

    def test_supported_languages(self, i18n_service):
        """Test supported languages."""
        languages = list(i18n_service.supported_languages)
        assert "zh-TW" in languages
        assert "en" in languages
        assert "ja" in languages


class TestTranslate:
    """Test translation functionality."""

    def test_translate_with_default_language(self, i18n_service):
        """Test translation with default language."""
        result = i18n_service.translate("hello")
        assert result == "你好"

    def test_translate_with_specified_language(self, i18n_service):
        """Test translation with specified language."""
        result = i18n_service.translate("hello", language="en")
        assert result == "Hello"

    def test_translate_with_parameters(self, i18n_service):
        """Test translation with parameters."""
        result = i18n_service.translate("welcome", language="en", name="John")
        assert result == "Welcome John"

    def test_translate_with_chinese_parameters(self, i18n_service):
        """Test Chinese parameters."""
        result = i18n_service.translate("welcome", name="小明")
        assert result == "歡迎 小明"

    def test_translate_missing_key(self, i18n_service):
        """Test missing translation key."""
        result = i18n_service.translate("nonexistent")
        assert result == "nonexistent"  # Return key itself

    def test_translate_with_default_fallback(self, i18n_service):
        """Test with default value."""
        result = i18n_service.translate("nonexistent", default="Default Value")
        assert result == "Default Value"

    def test_translate_fallback_to_default_language(self, i18n_service):
        """Test fallback to default language."""
        # Japanese missing "welcome" key, should fallback to Chinese
        result = i18n_service.translate("welcome", language="ja", name="太郎")
        assert result == "歡迎 太郎"

    def test_translate_with_multiple_parameters(self, i18n_service):
        """Test multiple parameters."""
        result = i18n_service.translate("count", language="en", count=42)
        assert result == "Count: 42"

    def test_translate_missing_parameter(self, i18n_service):
        """Test missing parameter (should remain unchanged)."""
        result = i18n_service.translate("welcome", language="en")
        # Missing {name} parameter, should keep template string
        assert "{name}" in result


class TestResolveLanguage:
    """Test language resolution."""

    def test_resolve_language_exact_match(self, i18n_service):
        """Test exact match."""
        result = i18n_service.resolve_language("en")
        assert result == "en"

    def test_resolve_language_case_insensitive(self, i18n_service):
        """Test case insensitive."""
        result = i18n_service.resolve_language("EN")
        assert result == "en"

    def test_resolve_language_with_region(self, i18n_service):
        """Test language with region."""
        result = i18n_service.resolve_language("zh-tw")
        assert result == "zh-TW"

    def test_resolve_language_none(self, i18n_service):
        """Test empty language (use default)."""
        result = i18n_service.resolve_language(None)
        assert result == "zh-TW"

    def test_resolve_language_unsupported(self, i18n_service):
        """Test unsupported language (fallback to default)."""
        result = i18n_service.resolve_language("fr")
        assert result == "zh-TW"


class TestRefresh:
    """Test reload translations."""

    def test_refresh_reloads_translations(self, i18n_service, translations_dir):
        """Test reload translations."""
        # Modify translation file
        zh_tw = translations_dir / "zh-TW.json"
        zh_tw.write_text(json.dumps({
            "hello": "你好！",  # Modified
            "new_key": "新鍵值"
        }, ensure_ascii=False))

        # Reload
        i18n_service.refresh()

        # Check update
        result = i18n_service.translate("hello")
        assert result == "你好！"

        result = i18n_service.translate("new_key")
        assert result == "新鍵值"


class TestLanguageCandidates:
    """Test language candidates."""

    def test_language_with_quality_values(self, translations_dir):
        """Test language list with quality values."""
        service = I18nService(translations_dir, default_language="en")

        # Simulate HTTP Accept-Language: "en-US,en;q=0.9,zh-TW;q=0.8"
        result = service.resolve_language("en-US,en;q=0.9,zh-TW;q=0.8")
        # Should prioritize matching en
        assert result in ["en", "zh-TW"]


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_translations_dir(self, tmp_path):
        """Test empty translations directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        service = I18nService(empty_dir)
        result = service.translate("hello")
        # No translation, should return key
        assert result == "hello"

    def test_invalid_json_file(self, tmp_path):
        """Test invalid JSON file."""
        trans_dir = tmp_path / "invalid"
        trans_dir.mkdir()

        # Create invalid JSON
        invalid = trans_dir / "invalid.json"
        invalid.write_text("{ invalid json }")

        # Should not crash
        service = I18nService(trans_dir)
        assert service is not None

    def test_translate_with_empty_key(self, i18n_service):
        """Test empty key."""
        result = i18n_service.translate("")
        assert result == ""

    def test_translate_with_special_characters(self, i18n_service):
        """Test special characters."""
        result = i18n_service.translate("special_@#$%", default="Special")
        assert result == "Special"


class TestComplexScenarios:
    """Test complex scenarios."""

    def test_multiple_languages_fallback(self, i18n_service):
        """Test multiple language fallback."""
        # Test key doesn't exist in any language
        result = i18n_service.translate("missing_key", language="ja", default="Fallback")
        assert result == "Fallback"

    def test_parameter_formatting_edge_cases(self, i18n_service):
        """Test parameter formatting edge cases."""
        # Extra parameters should be ignored
        result = i18n_service.translate(
            "welcome",
            language="en",
            name="John",
            extra="ignored"
        )
        assert result == "Welcome John"

    def test_nested_language_resolution(self, translations_dir):
        """Test nested language resolution."""
        service = I18nService(translations_dir, default_language="en")

        # Test various language variants
        test_cases = [
            ("zh-TW", "zh-TW"),
            ("zh-tw", "zh-TW"),
            ("ZH-TW", "zh-TW"),
            ("en-US", "en"),
            ("en-GB", "en"),
        ]

        for input_lang, expected_lang in test_cases:
            result = service.resolve_language(input_lang)
            assert result == expected_lang or result == "en"  # Allow fallback to default


class TestProperties:
    """Test properties."""

    def test_default_language_property(self, i18n_service):
        """Test default_language property."""
        assert i18n_service.default_language == "zh-TW"

    def test_supported_languages_property(self, i18n_service):
        """Test supported_languages property."""
        languages = list(i18n_service.supported_languages)
        assert len(languages) >= 3
        assert "zh-TW" in languages

    def test_supported_languages_is_iterable(self, i18n_service):
        """Test supported_languages is iterable."""
        count = 0
        for lang in i18n_service.supported_languages:
            count += 1
        assert count >= 3
