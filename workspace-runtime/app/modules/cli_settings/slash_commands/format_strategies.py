"""CLI Slash Commands format strategies

Provides unified read/write interface based on different CLI tool file formats (Markdown / TOML).
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
    """Parsed document data"""

    content: str  # Raw file full text
    description: str | None
    namespace: str | None


class DocumentFormatStrategy(ABC):
    """Document format strategy base class"""

    @abstractmethod
    def parse(self, file_path: Path, root_dir: Path) -> ParsedDocument:
        """Parse file

        Args:
            file_path: File path
            root_dir: Scope root directory (used to infer namespace)
        """

    @abstractmethod
    def write(self, file_path: Path, content: str, description: str | None = None) -> None:
        """Write file

        Args:
            file_path: File path
            content: Complete raw content (frontend responsible for assembling format)
            description: Description (some formats may ignore)
        """


def _infer_namespace(file_path: Path, root_dir: Path) -> str | None:
    """Infer namespace from file path"""
    try:
        relative = file_path.parent.relative_to(root_dir)
    except ValueError:
        return None
    if str(relative) == ".":
        return None
    return str(relative).replace("\\", "/")


class MarkdownFormatStrategy(DocumentFormatStrategy):
    """Markdown format strategy (Codex / OpenCode)

    Supports YAML frontmatter parsing for description.
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
        """Parse description from YAML frontmatter"""
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
    """TOML format strategy (Gemini)

    Gemini slash commands use TOML format, containing prompt and description fields.
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
