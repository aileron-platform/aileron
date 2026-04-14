"""CLI Slash Commands 格式策略

根據不同 CLI 工具的檔案格式（Markdown / TOML），提供統一的讀寫介面。
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """解析後的文件資料"""

    content: str  # 原始檔案完整文字
    description: str | None
    namespace: str | None


class DocumentFormatStrategy(ABC):
    """文件格式策略基類"""

    @abstractmethod
    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        """解析檔案

        Args:
            file_path: 檔案路徑
            root_dir: scope 根目錄（用於推導 namespace）
        """

    @abstractmethod
    def write(self, file_path: Path, content: str, description: str | None = None) -> None:
        """寫入檔案

        Args:
            file_path: 檔案路徑
            content: 完整原始內容（前端負責組裝格式）
            description: 描述（部分格式可能忽略）
        """


def _infer_namespace(file_path: Path, root_dir: Path) -> str | None:
    """從檔案路徑推導命名空間"""
    try:
        relative = file_path.parent.relative_to(root_dir)
    except ValueError:
        return None
    if str(relative) == ".":
        return None
    return str(relative).replace("\\", "/")


class MarkdownFormatStrategy(DocumentFormatStrategy):
    """Markdown 格式策略（Codex / OpenCode）

    支援 YAML frontmatter 解析 description。
    """

    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        raw = file_path.read_text(encoding="utf-8")
        description = self._extract_description(raw)
        namespace = _infer_namespace(file_path, root_dir)
        return ParsedDocument(content=raw, description=description, namespace=namespace)

    def write(self, file_path: Path, content: str, description: str | None = None) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    @staticmethod
    def _extract_description(content: str) -> str | None:
        """從 YAML frontmatter 解析 description"""
        if not content.startswith("---"):
            return None
        parts = content.split("\n---", 1)
        if len(parts) != 2:
            return None
        header = parts[0].replace("---", "", 1).strip()
        try:
            metadata = yaml.safe_load(header) or {}
        except yaml.YAMLError:
            return None
        return metadata.get("description")


class TomlFormatStrategy(DocumentFormatStrategy):
    """TOML 格式策略（Gemini）

    Gemini slash commands 使用 TOML 格式，包含 prompt 和 description 欄位。
    """

    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        raw = file_path.read_text(encoding="utf-8")
        description = None
        try:
            data = tomllib.loads(raw)
            description = data.get("description")
        except Exception:
            logger.warning("Failed to parse TOML file: %s", file_path)
        namespace = _infer_namespace(file_path, root_dir)
        return ParsedDocument(content=raw, description=description, namespace=namespace)

    def write(self, file_path: Path, content: str, description: str | None = None) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
