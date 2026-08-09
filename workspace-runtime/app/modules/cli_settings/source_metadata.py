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
    marketplace: str | None = None
    path: str | None = None
    readonly: bool = False
    requires_new_thread: bool = False


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


def managed_source_metadata(path: Path | str | None = None) -> SettingsSourceMetadata:
    """Create read-only managed source metadata."""

    return SettingsSourceMetadata(
        type=SettingsSourceType.MANAGED,
        path=str(path) if path is not None else None,
        readonly=True,
    )
