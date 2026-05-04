"""Resolve Gemini extension resources without mutating CLI-owned files."""

from __future__ import annotations

import fnmatch
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from app.config.settings import get_workspace_path

from .models import (
    GeminiExtensionCommandError,
    GeminiExtensionContextFile,
    GeminiExtensionHookDocument,
    GeminiExtensionInstallInfo,
    GeminiExtensionMcpServer,
    GeminiExtensionPackage,
    GeminiExtensionPolicy,
    GeminiExtensionSkill,
    GeminiExtensionSlashCommand,
    GeminiExtensionToggleScope,
)

GEMINI_COMMAND = "gemini"


def gemini_extensions_dir(home: Path | None = None) -> Path:
    """Return the Gemini extension root."""

    return (home or Path.home()) / ".gemini" / "extensions"


def enable(name: str, scope: GeminiExtensionToggleScope, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Enable a Gemini extension through the Gemini CLI."""

    return _run_toggle("enable", name, scope, cwd)


def disable(name: str, scope: GeminiExtensionToggleScope, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Disable a Gemini extension through the Gemini CLI."""

    return _run_toggle("disable", name, scope, cwd)


def resolve_toggle_cwd(scope: GeminiExtensionToggleScope, workspace_root: Path) -> Path:
    """Resolve the cwd required by Gemini extension toggles."""

    if scope == GeminiExtensionToggleScope.USER:
        return Path.home()
    return workspace_root.resolve(strict=True)


def resolve_workspace_root() -> Path:
    """Return the current workspace root as a real path."""

    return Path(get_workspace_path()).resolve(strict=True)


def _run_toggle(
    action: str,
    name: str,
    scope: GeminiExtensionToggleScope,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    command = [GEMINI_COMMAND, "extensions", action, name, f"--scope={scope.value}"]
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GeminiExtensionCommandError(command, result.stderr, result.returncode)
    return result


class GeminiExtensionResourceResolver:
    """Discover installed Gemini extensions and aggregate their contributions."""

    def __init__(self, extensions_dir: Path | None = None) -> None:
        self.extensions_dir = extensions_dir or gemini_extensions_dir()

    def list_extensions(self, workspace_root: Path | None = None, *, enabled_only: bool = False) -> list[GeminiExtensionPackage]:
        root = (workspace_root or resolve_workspace_root()).resolve(strict=True)
        enablement = self._read_enablement()
        packages = [self._load_package(path, root, enablement) for path in self._manifest_paths()]
        packages = [package for package in packages if package is not None]
        if enabled_only:
            packages = [package for package in packages if package.enabledHere]
        return sorted(packages, key=lambda item: item.name.lower())

    def get_extension(self, name: str, workspace_root: Path | None = None) -> GeminiExtensionPackage | None:
        for package in self.list_extensions(workspace_root, enabled_only=False):
            if package.name == name:
                return package
        return None

    def enabled_mcp_servers(self, workspace_root: Path | None = None) -> dict[str, dict[str, Any]]:
        servers: dict[str, dict[str, Any]] = {}
        for package in self.list_extensions(workspace_root, enabled_only=True):
            for server in package.mcpServers:
                servers[f"{package.name}:{server.name}"] = {
                    **server.config,
                    "enabled": True,
                    "source": {
                        "type": "extension",
                        "extensionName": package.name,
                        "extensionVersion": package.version,
                    },
                    "extensionName": package.name,
                    "extensionVersion": package.version,
                }
        return servers

    def enabled_hook_documents(self, workspace_root: Path | None = None) -> list[GeminiExtensionPackage]:
        return [
            package
            for package in self.list_extensions(workspace_root, enabled_only=True)
            if package.hooks
        ]

    def enabled_slash_commands(self, workspace_root: Path | None = None) -> list[tuple[GeminiExtensionPackage, GeminiExtensionSlashCommand]]:
        return [
            (package, command)
            for package in self.list_extensions(workspace_root, enabled_only=True)
            for command in package.slashCommands
        ]

    def enabled_skills(self, workspace_root: Path | None = None) -> list[tuple[GeminiExtensionPackage, GeminiExtensionSkill]]:
        return [
            (package, skill)
            for package in self.list_extensions(workspace_root, enabled_only=True)
            for skill in package.skills
        ]

    def is_enabled_for(self, extension_name: str, workspace_root: Path) -> bool:
        enablement = self._read_enablement()
        overrides = self._overrides_for(enablement, extension_name)
        return is_enabled_for(overrides, workspace_root.resolve(strict=True))

    def _manifest_paths(self) -> list[Path]:
        if not self.extensions_dir.is_dir():
            return []
        return sorted(self.extensions_dir.glob("*/gemini-extension.json"))

    def _load_package(
        self,
        manifest_path: Path,
        workspace_root: Path,
        enablement: dict[str, Any],
    ) -> GeminiExtensionPackage | None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(manifest, dict):
            return None

        extension_dir = manifest_path.parent
        name = str(manifest.get("name") or extension_dir.name)
        version = manifest.get("version")
        version = str(version) if version is not None else None
        overrides = self._overrides_for(enablement, name)

        return GeminiExtensionPackage(
            name=name,
            version=version,
            path=str(extension_dir),
            manifest=manifest,
            installInfo=self._read_install_info(extension_dir),
            overrides=overrides,
            enabledHere=is_enabled_for(overrides, workspace_root),
            mcpServers=self._read_mcp_servers(manifest),
            slashCommands=self._read_slash_commands(extension_dir),
            skills=self._read_skills(extension_dir),
            hooks=self._read_hooks(extension_dir),
            policies=self._read_policies(extension_dir),
            excludeTools=[str(item) for item in manifest.get("excludeTools", []) if isinstance(item, str)],
            contextFile=self._read_context_file(extension_dir, manifest),
        )

    def _read_enablement(self) -> dict[str, Any]:
        path = self.extensions_dir / "extension-enablement.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _overrides_for(enablement: dict[str, Any], extension_name: str) -> list[str]:
        config = enablement.get(extension_name)
        if not isinstance(config, dict):
            return []
        overrides = config.get("overrides")
        if not isinstance(overrides, list):
            return []
        return [item for item in overrides if isinstance(item, str)]

    @staticmethod
    def _read_install_info(extension_dir: Path) -> GeminiExtensionInstallInfo | None:
        path = extension_dir / ".gemini-extension-install.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return GeminiExtensionInstallInfo.model_validate(data) if isinstance(data, dict) else None

    @staticmethod
    def _read_mcp_servers(manifest: dict[str, Any]) -> list[GeminiExtensionMcpServer]:
        raw = manifest.get("mcpServers")
        if not isinstance(raw, dict):
            return []
        return [
            GeminiExtensionMcpServer(name=name, config=config)
            for name, config in raw.items()
            if isinstance(name, str) and isinstance(config, dict)
        ]

    @staticmethod
    def _read_slash_commands(extension_dir: Path) -> list[GeminiExtensionSlashCommand]:
        commands_dir = extension_dir / "commands"
        if not commands_dir.is_dir():
            return []
        commands: list[GeminiExtensionSlashCommand] = []
        for path in sorted(commands_dir.rglob("*.toml")):
            try:
                raw = tomllib.loads(path.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                raw = {}
            relative_parent = path.parent.relative_to(commands_dir)
            namespace = None if str(relative_parent) == "." else str(relative_parent)
            commands.append(
                GeminiExtensionSlashCommand(
                    fileName=path.name,
                    namespace=namespace,
                    description=raw.get("description") if isinstance(raw.get("description"), str) else None,
                    content=path.read_text(encoding="utf-8"),
                    path=str(path),
                )
            )
        return commands

    @staticmethod
    def _read_skills(extension_dir: Path) -> list[GeminiExtensionSkill]:
        skills_dir = extension_dir / "skills"
        if not skills_dir.is_dir():
            return []
        skills: list[GeminiExtensionSkill] = []
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            skills.append(
                GeminiExtensionSkill(
                    name=path.parent.name,
                    path=str(path),
                    content=path.read_text(encoding="utf-8"),
                )
            )
        return skills

    @staticmethod
    def _read_hooks(extension_dir: Path) -> list[GeminiExtensionHookDocument]:
        path = extension_dir / "hooks" / "hooks.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            hooks = data if isinstance(data, dict) else {}
        return [GeminiExtensionHookDocument(hooks=hooks, path=str(path))]

    @staticmethod
    def _read_policies(extension_dir: Path) -> list[GeminiExtensionPolicy]:
        policies_dir = extension_dir / "policies"
        if not policies_dir.is_dir():
            return []
        return [
            GeminiExtensionPolicy(path=str(path), content=path.read_text(encoding="utf-8"))
            for path in sorted(policies_dir.glob("*.toml"))
        ]

    @staticmethod
    def _read_context_file(extension_dir: Path, manifest: dict[str, Any]) -> GeminiExtensionContextFile | None:
        name = manifest.get("contextFileName")
        path = extension_dir / (name if isinstance(name, str) and name else "GEMINI.md")
        if not path.is_file():
            return None
        return GeminiExtensionContextFile(path=str(path), content=path.read_text(encoding="utf-8"))


def is_enabled_for(overrides: list[str], workspace_root: Path) -> bool:
    """Evaluate Gemini extension overrides for a workspace path."""

    enabled = True
    workspace = str(workspace_root.resolve(strict=True))
    for pattern in overrides:
        negated = pattern.startswith("!")
        raw_pattern = pattern[1:] if negated else pattern
        if _matches_workspace(raw_pattern, workspace):
            enabled = not negated
    return enabled


def _matches_workspace(pattern: str, workspace: str) -> bool:
    normalized = _normalize_enablement_pattern(pattern)
    current = _normalize_enablement_pattern(workspace)
    if normalized.endswith("/*") and current == normalized[:-2].rstrip("/"):
        return True
    if fnmatch.fnmatch(current, normalized):
        return True
    return fnmatch.fnmatch(f"{current}/", normalized)


def _normalize_enablement_pattern(pattern: str) -> str:
    normalized = str(Path(pattern).expanduser()).replace("\\", "/")
    return normalized.rstrip("/")
