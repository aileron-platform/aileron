"""Shared primitives for CLI settings services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SettingsSourceType(str, Enum):
    """Where a settings item came from."""

    USER = "user"
    PROJECT = "project"
    PLUGIN = "plugin"
    EXTENSION = "extension"
    BUILT_IN = "built_in"
    MANAGED = "managed"
    INLINE_CONFIG = "inline_config"


class SettingsLayer(str, Enum):
    """Editable settings layer identifiers."""

    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True)
class SettingsSourceMetadata:
    """Source metadata attached to settings rows."""

    type: SettingsSourceType
    layer: SettingsLayer | None = None
    label: str | None = None
    plugin_id: str | None = None
    extension_name: str | None = None
    extension_version: str | None = None
    marketplace: str | None = None
    path: str | None = None
    readonly: bool = False
    requires_new_thread: bool = False


@dataclass(frozen=True)
class LayerFile:
    """A resolved settings file for one editable layer."""

    layer: SettingsLayer
    path: Path

    def exists(self) -> bool:
        return self.path.is_file()

    def read_text(self, default: str = "") -> str:
        if not self.exists():
            return default
        return self.path.read_text(encoding="utf-8")

    def write_text(self, content: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")

    def source_metadata(self) -> SettingsSourceMetadata:
        return SettingsSourceMetadata(
            type=SettingsSourceType(self.layer.value),
            layer=self.layer,
            path=str(self.path),
        )


class LayeredFileResolver:
    """Resolve and operate on user/project settings files."""

    def __init__(self, files: dict[SettingsLayer, Path]) -> None:
        self._files = dict(files)

    def layers(self) -> list[SettingsLayer]:
        return list(self._files.keys())

    def resolve(self, layer: SettingsLayer | str) -> LayerFile:
        settings_layer = SettingsLayer(layer)
        if settings_layer not in self._files:
            raise ValueError(f"Unsupported settings layer: {layer}")
        return LayerFile(layer=settings_layer, path=self._files[settings_layer])


def plugin_source_metadata(
    *,
    plugin_id: str,
    marketplace: str,
    path: Path | str | None = None,
    requires_new_thread: bool = False,
) -> SettingsSourceMetadata:
    """Create read-only plugin source metadata."""

    return SettingsSourceMetadata(
        type=SettingsSourceType.PLUGIN,
        label=f"{plugin_id}@{marketplace}",
        plugin_id=plugin_id,
        marketplace=marketplace,
        path=str(path) if path is not None else None,
        readonly=True,
        requires_new_thread=requires_new_thread,
    )


def extension_source_metadata(
    *,
    extension_name: str,
    extension_version: str | None = None,
    path: Path | str | None = None,
) -> SettingsSourceMetadata:
    """Create read-only Gemini extension source metadata."""

    return SettingsSourceMetadata(
        type=SettingsSourceType.EXTENSION,
        label=extension_name,
        extension_name=extension_name,
        extension_version=extension_version,
        path=str(path) if path is not None else None,
        readonly=True,
    )


def managed_source_metadata(path: Path | str | None = None) -> SettingsSourceMetadata:
    """Create read-only managed source metadata."""

    return SettingsSourceMetadata(
        type=SettingsSourceType.MANAGED,
        path=str(path) if path is not None else None,
        readonly=True,
    )
