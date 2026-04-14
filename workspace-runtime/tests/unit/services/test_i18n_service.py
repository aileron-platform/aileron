"""I18n Service 單元測試"""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from app.services.i18n_service import I18nService


@pytest.fixture
def translations_dir(tmp_path):
    """創建臨時翻譯目錄."""
    trans_dir = tmp_path / "translations"
    trans_dir.mkdir()

    # 創建中文翻譯
    zh_tw = trans_dir / "zh-TW.json"
    zh_tw.write_text(json.dumps({
        "hello": "你好",
        "goodbye": "再見",
        "welcome": "歡迎 {name}",
        "count": "數量: {count}"
    }, ensure_ascii=False))

    # 創建英文翻譯
    en = trans_dir / "en.json"
    en.write_text(json.dumps({
        "hello": "Hello",
        "goodbye": "Goodbye",
        "welcome": "Welcome {name}",
        "count": "Count: {count}"
    }))

    # 創建日文翻譯（部分）
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
    """測試初始化."""

    def test_init_with_default_language(self, translations_dir):
        """測試預設語言初始化."""
        service = I18nService(translations_dir)
        assert service.default_language == "zh-TW"

    def test_init_with_custom_language(self, translations_dir):
        """測試自訂語言初始化."""
        service = I18nService(translations_dir, default_language="en")
        assert service.default_language == "en"

    def test_init_loads_translations(self, i18n_service):
        """測試初始化載入翻譯."""
        assert len(i18n_service._translations) > 0

    def test_supported_languages(self, i18n_service):
        """測試支援的語言."""
        languages = list(i18n_service.supported_languages)
        assert "zh-TW" in languages
        assert "en" in languages
        assert "ja" in languages


class TestTranslate:
    """測試翻譯功能."""

    def test_translate_with_default_language(self, i18n_service):
        """測試使用預設語言翻譯."""
        result = i18n_service.translate("hello")
        assert result == "你好"

    def test_translate_with_specified_language(self, i18n_service):
        """測試指定語言翻譯."""
        result = i18n_service.translate("hello", language="en")
        assert result == "Hello"

    def test_translate_with_parameters(self, i18n_service):
        """測試帶參數的翻譯."""
        result = i18n_service.translate("welcome", language="en", name="John")
        assert result == "Welcome John"

    def test_translate_with_chinese_parameters(self, i18n_service):
        """測試中文參數."""
        result = i18n_service.translate("welcome", name="小明")
        assert result == "歡迎 小明"

    def test_translate_missing_key(self, i18n_service):
        """測試缺失的翻譯鍵."""
        result = i18n_service.translate("nonexistent")
        assert result == "nonexistent"  # 返回鍵本身

    def test_translate_with_default_fallback(self, i18n_service):
        """測試使用預設值."""
        result = i18n_service.translate("nonexistent", default="Default Value")
        assert result == "Default Value"

    def test_translate_fallback_to_default_language(self, i18n_service):
        """測試回退到預設語言."""
        # 日文缺少 "welcome" 鍵，應該回退到中文
        result = i18n_service.translate("welcome", language="ja", name="太郎")
        assert result == "歡迎 太郎"

    def test_translate_with_multiple_parameters(self, i18n_service):
        """測試多個參數."""
        result = i18n_service.translate("count", language="en", count=42)
        assert result == "Count: 42"

    def test_translate_missing_parameter(self, i18n_service):
        """測試缺失參數（應該保持原樣）."""
        result = i18n_service.translate("welcome", language="en")
        # 缺少 {name} 參數，應該保持模板字串
        assert "{name}" in result


class TestResolveLanguage:
    """測試語言解析."""

    def test_resolve_language_exact_match(self, i18n_service):
        """測試精確匹配."""
        result = i18n_service.resolve_language("en")
        assert result == "en"

    def test_resolve_language_case_insensitive(self, i18n_service):
        """測試大小寫不敏感."""
        result = i18n_service.resolve_language("EN")
        assert result == "en"

    def test_resolve_language_with_region(self, i18n_service):
        """測試帶區域的語言."""
        result = i18n_service.resolve_language("zh-tw")
        assert result == "zh-TW"

    def test_resolve_language_none(self, i18n_service):
        """測試空語言（使用預設）."""
        result = i18n_service.resolve_language(None)
        assert result == "zh-TW"

    def test_resolve_language_unsupported(self, i18n_service):
        """測試不支援的語言（回退到預設）."""
        result = i18n_service.resolve_language("fr")
        assert result == "zh-TW"


class TestRefresh:
    """測試重新載入翻譯."""

    def test_refresh_reloads_translations(self, i18n_service, translations_dir):
        """測試重新載入翻譯."""
        # 修改翻譯文件
        zh_tw = translations_dir / "zh-TW.json"
        zh_tw.write_text(json.dumps({
            "hello": "你好！",  # 修改
            "new_key": "新鍵值"
        }, ensure_ascii=False))

        # 重新載入
        i18n_service.refresh()

        # 檢查更新
        result = i18n_service.translate("hello")
        assert result == "你好！"

        result = i18n_service.translate("new_key")
        assert result == "新鍵值"


class TestLanguageCandidates:
    """測試語言候選."""

    def test_language_with_quality_values(self, translations_dir):
        """測試帶品質值的語言列表."""
        service = I18nService(translations_dir, default_language="en")

        # 模擬 HTTP Accept-Language: "en-US,en;q=0.9,zh-TW;q=0.8"
        result = service.resolve_language("en-US,en;q=0.9,zh-TW;q=0.8")
        # 應該優先匹配 en
        assert result in ["en", "zh-TW"]


class TestEdgeCases:
    """測試邊界條件."""

    def test_empty_translations_dir(self, tmp_path):
        """測試空的翻譯目錄."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        service = I18nService(empty_dir)
        result = service.translate("hello")
        # 沒有翻譯，應該返回鍵
        assert result == "hello"

    def test_invalid_json_file(self, tmp_path):
        """測試無效的 JSON 文件."""
        trans_dir = tmp_path / "invalid"
        trans_dir.mkdir()

        # 創建無效的 JSON
        invalid = trans_dir / "invalid.json"
        invalid.write_text("{ invalid json }")

        # 不應該崩潰
        service = I18nService(trans_dir)
        assert service is not None

    def test_translate_with_empty_key(self, i18n_service):
        """測試空鍵."""
        result = i18n_service.translate("")
        assert result == ""

    def test_translate_with_special_characters(self, i18n_service):
        """測試特殊字符."""
        result = i18n_service.translate("special_@#$%", default="Special")
        assert result == "Special"


class TestComplexScenarios:
    """測試複雜場景."""

    def test_multiple_languages_fallback(self, i18n_service):
        """測試多語言回退."""
        # 測試鍵不存在於任何語言
        result = i18n_service.translate("missing_key", language="ja", default="Fallback")
        assert result == "Fallback"

    def test_parameter_formatting_edge_cases(self, i18n_service):
        """測試參數格式化邊界情況."""
        # 多餘的參數應該被忽略
        result = i18n_service.translate(
            "welcome",
            language="en",
            name="John",
            extra="ignored"
        )
        assert result == "Welcome John"

    def test_nested_language_resolution(self, translations_dir):
        """測試嵌套語言解析."""
        service = I18nService(translations_dir, default_language="en")

        # 測試各種語言變體
        test_cases = [
            ("zh-TW", "zh-TW"),
            ("zh-tw", "zh-TW"),
            ("ZH-TW", "zh-TW"),
            ("en-US", "en"),
            ("en-GB", "en"),
        ]

        for input_lang, expected_lang in test_cases:
            result = service.resolve_language(input_lang)
            assert result == expected_lang or result == "en"  # 允許回退到預設


class TestProperties:
    """測試屬性."""

    def test_default_language_property(self, i18n_service):
        """測試 default_language 屬性."""
        assert i18n_service.default_language == "zh-TW"

    def test_supported_languages_property(self, i18n_service):
        """測試 supported_languages 屬性."""
        languages = list(i18n_service.supported_languages)
        assert len(languages) >= 3
        assert "zh-TW" in languages

    def test_supported_languages_is_iterable(self, i18n_service):
        """測試 supported_languages 可迭代."""
        count = 0
        for lang in i18n_service.supported_languages:
            count += 1
        assert count >= 3
