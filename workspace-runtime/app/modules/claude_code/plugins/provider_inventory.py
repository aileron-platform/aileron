"""Internal Claude provider inventory and execution-only CLI coordination."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from aileron_marketplace_core import (
    ClaudePluginResources,
    resolve_claude_plugin_resources,
)
from app.modules.cli_settings.cache import ProcessTTLCache


@dataclass(frozen=True)
class ClaudeProviderInstallation:
    """One provider installation row with a validated internal root."""

    plugin_id: str
    scope: str
    enabled: bool
    install_root: Path | None
    has_errors: bool


@dataclass(frozen=True)
class ClaudeProviderResourceProjection:
    """Resolved resources for the installation selected by provider precedence."""

    plugin_id: str
    install_root: Path
    manifest: dict[str, Any]
    resources: ClaudePluginResources


@dataclass(frozen=True)
class ClaudeProviderInventorySnapshot:
    """Provider rows plus internal roots that never enter public response models."""

    rows: tuple[dict[str, Any], ...]
    installations: tuple[ClaudeProviderInstallation, ...]
    resource_projections: tuple[ClaudeProviderResourceProjection, ...]

    def resource_projection(
        self,
        plugin_id: str,
    ) -> ClaudeProviderResourceProjection | None:
        """Return the request-local resource projection for one plugin."""

        return next(
            (
                projection
                for projection in self.resource_projections
                if projection.plugin_id == plugin_id
            ),
            None,
        )

    def enabled_roots(self) -> tuple[Path, ...]:
        """Return every valid root for effectively enabled provider plugins."""

        grouped: dict[str, list[ClaudeProviderInstallation]] = {}
        for installation in self.installations:
            grouped.setdefault(installation.plugin_id, []).append(installation)

        projected_plugin_ids = {
            projection.plugin_id for projection in self.resource_projections
        }
        if projected_plugin_ids != set(grouped):
            raise ValueError("Claude plugin inventory is incomplete")
        if any(
            projection.resources.diagnostics for projection in self.resource_projections
        ):
            raise ValueError("Claude plugin inventory is incomplete")

        roots: set[Path] = set()
        for plugin_id in sorted(grouped):
            installations = grouped[plugin_id]
            if any(item.has_errors for item in installations):
                raise ValueError("Claude plugin inventory is incomplete")

            effective_enabled = False
            for installation in sorted(
                installations,
                key=lambda item: _scope_rank(item.scope),
            ):
                effective_enabled = installation.enabled
            if not effective_enabled:
                continue

            enabled_roots = {
                item.install_root
                for item in installations
                if item.enabled and item.install_root is not None
            }
            if not enabled_roots:
                raise ValueError("Enabled Claude plugin root is missing")
            roots.update(enabled_roots)
        return tuple(sorted(roots, key=str))


_provider_cli_cache: ProcessTTLCache[
    tuple[tuple[str, ...], str, float],
    subprocess.CompletedProcess[str],
] = ProcessTTLCache()


def run_claude_plugin_cli(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Cache one completed Claude CLI discovery result for five minutes."""

    key = (tuple(args), str(cwd), timeout)
    return _provider_cli_cache.get_or_load(
        key,
        lambda: subprocess.run(
            ["claude", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        ),
        cache_if=lambda completed: completed.returncode == 0,
    )


def clear_claude_provider_inventory_cache(cwd: Path | None = None) -> None:
    """Clear completed Claude provider discovery results."""

    if cwd is None:
        _provider_cli_cache.clear()
        return
    identity = str(cwd)
    _provider_cli_cache.clear(lambda key: key[1] == identity)


def build_claude_provider_inventory_snapshot(
    rows: Sequence[dict[str, Any]],
) -> ClaudeProviderInventorySnapshot:
    """Retain validated installed roots beside the provider's original rows."""

    copied_rows = tuple(dict(row) for row in rows)
    installations: list[ClaudeProviderInstallation] = []
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    for row in copied_rows:
        plugin_id = row.get("id") or row.get("pluginId") or row.get("name")
        if not isinstance(plugin_id, str) or not plugin_id:
            continue
        grouped_rows.setdefault(plugin_id, []).append(row)
        scope = str(row.get("scope") or "user")
        if scope not in {"user", "project", "local"}:
            scope = "user"
        raw_path = row.get("installPath")
        install_root: Path | None = None
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path)
            if candidate.is_dir():
                install_root = candidate
        raw_errors = row.get("errors")
        installations.append(
            ClaudeProviderInstallation(
                plugin_id=plugin_id,
                scope=scope,
                enabled=bool(row.get("enabled")),
                install_root=install_root,
                has_errors=isinstance(raw_errors, list) and bool(raw_errors),
            )
        )

    resource_projections: list[ClaudeProviderResourceProjection] = []
    for plugin_id, group in sorted(grouped_rows.items()):
        selected = sorted(
            group,
            key=lambda row: _scope_rank(str(row.get("scope") or "user")),
            reverse=True,
        )[0]
        raw_path = selected.get("installPath")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        install_root = Path(raw_path)
        resource_projections.append(
            ClaudeProviderResourceProjection(
                plugin_id=plugin_id,
                install_root=install_root,
                manifest=read_claude_installed_manifest(install_root),
                resources=resolve_claude_plugin_resources(install_root),
            )
        )

    return ClaudeProviderInventorySnapshot(
        rows=copied_rows,
        installations=tuple(installations),
        resource_projections=tuple(resource_projections),
    )


def read_claude_installed_manifest(install_root: Path) -> dict[str, Any]:
    """Read an installed manifest with the existing tolerant service semantics."""

    path = install_root / ".claude-plugin" / "plugin.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _scope_rank(scope: str) -> int:
    return {"user": 0, "project": 1, "local": 2}.get(scope, 0)


__all__ = [
    "ClaudeProviderInstallation",
    "ClaudeProviderInventorySnapshot",
    "ClaudeProviderResourceProjection",
    "build_claude_provider_inventory_snapshot",
    "clear_claude_provider_inventory_cache",
    "read_claude_installed_manifest",
    "run_claude_plugin_cli",
]
