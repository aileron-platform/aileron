"""多語系測試輔助工具"""

from __future__ import annotations

from typing import Dict, Optional
from pathlib import Path
import json


class I18nTestHelper:
    """多語系測試輔助類別
    
    提供測試中需要的多語系功能：
    1. 載入翻譯檔案
    2. 根據語系取得翻譯
    3. 驗證 API 回應中的多語系訊息
    """
    
    def __init__(self, translations_dir: Optional[Path] = None):
        """初始化多語系測試輔助工具
        
        Args:
            translations_dir: 翻譯檔案目錄，預設為 app/translations
        """
        if translations_dir is None:
            # 預設使用 workspace-manager/app/translations
            base_path = Path(__file__).resolve().parent.parent.parent / "app" / "translations"
            translations_dir = base_path
        
        self.translations_dir = translations_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()
    
    def _load_translations(self) -> None:
        """載入所有翻譯檔案"""
        self.translations.clear()
        
        if not self.translations_dir.exists():
            return
        
        for path in sorted(self.translations_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                language = path.stem  # 例如: en, zh-TW
                self.translations[language] = data
            except json.JSONDecodeError:
                continue
    
    def get_translation(
        self,
        key: str,
        language: str = "en",
        **kwargs
    ) -> str:
        """取得翻譯字串
        
        Args:
            key: 翻譯鍵值，例如 "auth.user_conflict"
            language: 語系，預設為 "en"
            **kwargs: 格式化參數
        
        Returns:
            翻譯後的字串
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
        """驗證 API 回應中包含預期的翻譯訊息
        
        Args:
            response_data: API 回應的 JSON 資料
            key: 翻譯鍵值
            language: 語系
            field: 訊息欄位名稱，預設為 "detail"
            **kwargs: 格式化參數
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
        """驗證 API 回應中的訊息完全匹配預期的翻譯
        
        Args:
            response_data: API 回應的 JSON 資料
            key: 翻譯鍵值
            language: 語系
            field: 訊息欄位名稱，預設為 "detail"
            **kwargs: 格式化參數
        """
        expected_message = self.get_translation(key, language, **kwargs)
        actual_message = response_data.get(field, "")
        
        assert expected_message == actual_message, (
            f"Expected '{expected_message}' but got '{actual_message}'"
        )
    
    def get_supported_languages(self) -> list[str]:
        """取得支援的語系列表"""
        return list(self.translations.keys())
    
    def create_headers(self, language: str = "en") -> dict:
        """建立包含語系的 HTTP headers

        Args:
            language: 語系代碼

        Returns:
            包含 Accept-Language 或 X-Language 的 headers
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
        """驗證 API 回應包含任一語系的翻譯訊息

        這個方法會檢查所有支援的語系，只要有一個匹配就通過。
        適用於不確定 API 會返回哪種語系的情況。

        Args:
            response_data: API 回應的 JSON 資料
            key: 翻譯鍵值
            field: 訊息欄位名稱，預設為 "detail"
            **kwargs: 格式化參數
        """
        actual_message = response_data.get(field, "")

        # 檢查所有支援的語系
        for language in self.get_supported_languages():
            expected_message = self.get_translation(key, language, **kwargs)
            if expected_message.lower() in actual_message.lower():
                return  # 找到匹配，測試通過

        # 如果沒有任何語系匹配，顯示所有可能的翻譯
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
        """驗證 API 回應包含特定關鍵字（不區分大小寫）

        Args:
            response_data: API 回應的 JSON 資料
            keyword: 要搜尋的關鍵字
            field: 訊息欄位名稱，預設為 "detail"
        """
        actual_message = response_data.get(field, "")
        assert keyword.lower() in actual_message.lower(), (
            f"Keyword '{keyword}' not found in '{actual_message}'"
        )


def get_i18n_test_helper() -> I18nTestHelper:
    """取得多語系測試輔助工具的單例實例"""
    if not hasattr(get_i18n_test_helper, "_instance"):
        get_i18n_test_helper._instance = I18nTestHelper()
    return get_i18n_test_helper._instance


__all__ = ["I18nTestHelper", "get_i18n_test_helper"]

