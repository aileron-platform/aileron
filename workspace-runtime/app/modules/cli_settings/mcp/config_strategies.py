"""CLI MCP configuration file read/write strategies

Provides read/write support for JSON and TOML configuration files.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from app.modules.cli_settings.user_scope.codecs import (
    JsonDocumentCodec,
    TomlDocumentCodec,
)


class ConfigFileStrategy(ABC):
    """Abstract base class for configuration file read/write strategies"""

    @abstractmethod
    def read(self, path: Path) -> Dict[str, Any]:
        """Read configuration file, return empty dict if file doesn't exist or format error"""

    @abstractmethod
    def write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write configuration file and ensure directory exists"""


class JsonConfigStrategy(ConfigFileStrategy):
    """JSON configuration file strategy (supports JSONC comment removal)"""

    _codec = JsonDocumentCodec(allow_comments=True)

    def read(self, path: Path) -> Dict[str, Any]:
        return self._codec.read(path)

    def write(self, path: Path, data: Dict[str, Any]) -> None:
        self._codec.write(path, data)


class TomlConfigStrategy(ConfigFileStrategy):
    """TOML configuration file strategy (for Codex)"""

    _codec = TomlDocumentCodec()

    def read(self, path: Path) -> Dict[str, Any]:
        return self._codec.read(path)

    def write(self, path: Path, data: Dict[str, Any]) -> None:
        self._codec.write(path, data)
