"""CLI MCP 設定檔讀寫策略

提供 JSON 和 TOML 兩種設定檔的讀寫支援。
"""

from __future__ import annotations

import json
import logging
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w


class ConfigFileStrategy(ABC):
    """設定檔讀寫策略的抽象基類"""

    @abstractmethod
    def read(self, path: Path) -> Dict[str, Any]:
        """讀取設定檔，若檔案不存在或格式錯誤回傳空 dict"""

    @abstractmethod
    def write(self, path: Path, data: Dict[str, Any]) -> None:
        """寫入設定檔並確保目錄存在"""


class JsonConfigStrategy(ConfigFileStrategy):
    """JSON 設定檔策略（支援 JSONC 註解移除）"""

    def read(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            raw = path.read_text(encoding="utf-8")
            cleaned = _strip_json_comments(raw)
            result = json.loads(cleaned)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(
                "Failed to parse JSON config file %s: %s. Treating as empty config.",
                path, exc, exc_info=False,
            )
            return {}

    def write(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


class TomlConfigStrategy(ConfigFileStrategy):
    """TOML 設定檔策略（用於 Codex）"""

    def read(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            raw = path.read_bytes()
            return tomllib.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.warning(
                "Failed to parse TOML config file %s: %s. Treating as empty config.",
                path, exc, exc_info=False,
            )
            return {}

    def write(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tomli_w.dumps(data).encode("utf-8"))


def _strip_json_comments(text: str) -> str:
    """移除 JSONC 中的單行 (//) 和多行 (/* */) 註解，保留字串中的內容"""
    result: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        # 字串
        if ch in ('"', "'"):
            quote = ch
            result.append(ch)
            i += 1
            while i < length:
                c = text[i]
                result.append(c)
                i += 1
                if c == "\\":
                    if i < length:
                        result.append(text[i])
                        i += 1
                elif c == quote:
                    break
        # 單行註解
        elif ch == "/" and i + 1 < length and text[i + 1] == "/":
            i += 2
            while i < length and text[i] != "\n":
                i += 1
        # 多行註解
        elif ch == "/" and i + 1 < length and text[i + 1] == "*":
            i += 2
            while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2  # skip */
        else:
            result.append(ch)
            i += 1
    return "".join(result)
