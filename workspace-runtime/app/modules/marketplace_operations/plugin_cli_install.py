"""Target client-native one-shot Marketplace plugin installation."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Protocol, Sequence

MarketplaceTargetClient = Literal["claude-code", "codex"]
MarketplacePluginStage = Literal[
    "marketplace-add",
    "plugin-install",
    "plugin-enable",
    "marketplace-list",
    "plugin-list",
    "completed",
]

_MAX_OUTPUT_BYTES = 256 * 1024
_MAX_OUTPUT_LINES = 400
_MAX_MESSAGE_BYTES = 4096
_MAX_MESSAGE_LINES = 20
_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


@dataclass(frozen=True)
class CliCommandResult:
    """Raw target_client CLI process result."""

    returncode: int
    stdout: str
    stderr: str


class CliCommandRunner(Protocol):
    """Fixed-argv subprocess seam."""

    def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        timeout_seconds: float,
    ) -> CliCommandResult: ...


class SubprocessCliCommandRunner:
    """Run target_client CLI commands without shell expansion."""

    def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        timeout_seconds: float,
    ) -> CliCommandResult:
        completed = subprocess.run(
            list(argv),
            env=dict(env),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        return CliCommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


@dataclass(frozen=True)
class PluginCliInstallResult:
    """Bounded terminal result for one CLI command sequence."""

    status: Literal["installed", "failed"]
    stage: MarketplacePluginStage
    exit_code: int | None
    cli_message: str | None
    stdout: str | None
    stderr: str | None
    truncated: bool
    commands: tuple["PluginCliCommandAudit", ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PluginCliCommandAudit:
    """One bounded, append-only CLI invocation receipt."""

    sequence: int
    stage: MarketplacePluginStage
    argv_display: str
    exit_code: int | None
    started_at: str
    ended_at: str
    stdout: str | None
    stderr: str | None
    stdout_original_byte_count: int
    stderr_original_byte_count: int
    truncated: bool


class TargetClientPluginCliInstaller:
    """Install through the documented target_client CLI and read back once."""

    def __init__(
        self,
        *,
        runner: CliCommandRunner | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._runner = runner or SubprocessCliCommandRunner()
        self._timeout_seconds = timeout_seconds

    def install(
        self,
        *,
        target_client: MarketplaceTargetClient,
        package_id: str,
        marketplace_id: str,
        remote_url: str,
        registry_ref: str,
    ) -> PluginCliInstallResult:
        """Execute add, install, and immediate list readback in order."""

        commands: list[PluginCliCommandAudit] = []
        warnings: list[str] = []
        plugin_identity = f"{package_id}@{marketplace_id}"
        install_message: str | None = None

        mutation_stages: list[tuple[MarketplacePluginStage, list[str]]] = [
            (
                "marketplace-add",
                marketplace_add_argv(
                    target_client=target_client,
                    remote_url=remote_url,
                    registry_ref=registry_ref,
                ),
            ),
            (
                "plugin-install",
                plugin_install_argv(
                    target_client=target_client,
                    plugin_identity=plugin_identity,
                ),
            ),
        ]
        if target_client == "claude-code":
            mutation_stages.append(
                ("plugin-enable", plugin_enable_argv(plugin_identity))
            )
        readback_stages: tuple[tuple[MarketplacePluginStage, list[str]], ...] = (
            ("marketplace-list", marketplace_list_argv(target_client)),
            ("plugin-list", plugin_list_argv(target_client)),
        )

        terminal_command: PluginCliCommandAudit | None = None
        for stage, argv in [*mutation_stages, *readback_stages]:
            started_at = datetime.now(timezone.utc)
            try:
                command = self._runner.run(
                    argv,
                    env=os.environ.copy(),
                    timeout_seconds=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                command = CliCommandResult(
                    returncode=-1,
                    stdout=_exception_output(exc.stdout),
                    stderr=_exception_output(exc.stderr),
                )
                command_audit = _command_audit(
                    len(commands), stage, argv, command, started_at, exit_code=None
                )
                commands.append(command_audit)
                if stage in {"marketplace-list", "plugin-list"}:
                    warnings.append("marketplace.install.state-unconfirmed")
                    continue
                return self._result(
                    status="failed",
                    stage=stage,
                    terminal_command=command_audit,
                    cli_message="marketplace.install.outcome-unconfirmed",
                    commands=commands,
                    warnings=("marketplace.install.command-timeout",),
                )
            except (OSError, UnicodeError) as exc:
                command = CliCommandResult(returncode=-1, stdout="", stderr=str(exc))
                command_audit = _command_audit(
                    len(commands), stage, argv, command, started_at, exit_code=None
                )
                commands.append(command_audit)
                return self._result(
                    status="failed",
                    stage=stage,
                    cli_message=str(exc),
                    terminal_command=command_audit,
                    commands=commands,
                    warnings=warnings,
                )

            command_audit = _command_audit(
                len(commands), stage, argv, command, started_at
            )
            commands.append(command_audit)
            if command.returncode != 0:
                if stage in {"marketplace-list", "plugin-list"}:
                    warnings.append("marketplace.install.state-unconfirmed")
                    continue
                return self._result(
                    status="failed",
                    stage=stage,
                    cli_message=_first_diagnostic(
                        command.stderr,
                        command.stdout,
                    ),
                    terminal_command=command_audit,
                    commands=commands,
                    warnings=warnings,
                )

            if stage in {"plugin-install", "plugin-enable"}:
                install_message = _first_diagnostic(
                    command.stderr,
                    command.stdout,
                )
                terminal_command = command_audit
                continue
            if stage not in {"marketplace-list", "plugin-list"}:
                continue

            try:
                payload = json.loads(command.stdout)
                if stage == "marketplace-list":
                    found = marketplace_visible(
                        target_client,
                        payload,
                        marketplace_id,
                    )
                else:
                    found = plugin_visible(
                        target_client,
                        payload,
                        plugin_identity,
                    )
            except (TypeError, ValueError, json.JSONDecodeError):
                warnings.append("marketplace.install.state-unconfirmed")
                continue
            if not found:
                warnings.append("marketplace.install.state-unconfirmed")

        assert terminal_command is not None
        return self._result(
            status="installed",
            stage="completed",
            cli_message=install_message,
            terminal_command=terminal_command,
            commands=commands,
            warnings=warnings,
        )

    def _result(
        self,
        *,
        status: Literal["installed", "failed"],
        stage: MarketplacePluginStage,
        cli_message: str | None,
        terminal_command: PluginCliCommandAudit,
        commands: Sequence[PluginCliCommandAudit],
        warnings: Sequence[str],
    ) -> PluginCliInstallResult:
        message, message_truncated = _bounded_output(
            cli_message or "",
            max_bytes=_MAX_MESSAGE_BYTES,
            max_lines=_MAX_MESSAGE_LINES,
        )
        return PluginCliInstallResult(
            status=status,
            stage=stage,
            exit_code=terminal_command.exit_code,
            cli_message=message,
            stdout=terminal_command.stdout,
            stderr=terminal_command.stderr,
            truncated=(terminal_command.truncated or message_truncated),
            commands=tuple(commands),
            warnings=tuple(dict.fromkeys(warnings)),
        )


def marketplace_add_argv(
    *,
    target_client: MarketplaceTargetClient,
    remote_url: str,
    registry_ref: str,
) -> list[str]:
    """Build the documented target_client marketplace-add argv."""

    if target_client == "claude-code":
        return [
            "claude",
            "plugin",
            "marketplace",
            "add",
            f"{remote_url}#{registry_ref}",
            "--sparse",
            ".claude-plugin",
            "claude-code",
            "--scope",
            "user",
        ]
    return [
        "codex",
        "plugin",
        "marketplace",
        "add",
        remote_url,
        "--ref",
        registry_ref,
        "--sparse",
        ".agents/plugins",
        "--sparse",
        "codex",
    ]


def plugin_install_argv(
    *,
    target_client: MarketplaceTargetClient,
    plugin_identity: str,
) -> list[str]:
    """Build the documented target_client plugin-install argv."""

    if target_client == "claude-code":
        return [
            "claude",
            "plugin",
            "install",
            plugin_identity,
            "--scope",
            "user",
        ]
    return ["codex", "plugin", "add", plugin_identity]


def plugin_enable_argv(plugin_identity: str) -> list[str]:
    """Build the required Claude post-install enable argv."""

    return ["claude", "plugin", "enable", plugin_identity, "--scope", "user"]


def marketplace_list_argv(target_client: MarketplaceTargetClient) -> list[str]:
    executable = "claude" if target_client == "claude-code" else "codex"
    return [executable, "plugin", "marketplace", "list", "--json"]


def plugin_list_argv(target_client: MarketplaceTargetClient) -> list[str]:
    executable = "claude" if target_client == "claude-code" else "codex"
    return [executable, "plugin", "list", "--json"]


def marketplace_visible(
    target_client: MarketplaceTargetClient,
    payload: Any,
    marketplace_id: str,
) -> bool:
    """Validate official list shape and locate the requested marketplace."""

    if target_client == "claude-code":
        rows = payload
    else:
        if not isinstance(payload, dict):
            raise ValueError("invalid Codex marketplace list")
        rows = payload.get("marketplaces")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid marketplace list")
    names = [row.get("name") for row in rows]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("invalid marketplace identity")
    return marketplace_id in names


def plugin_visible(
    target_client: MarketplaceTargetClient,
    payload: Any,
    plugin_identity: str,
) -> bool:
    """Validate official list shape and locate the installed plugin."""

    if target_client == "claude-code":
        rows = payload
    else:
        if not isinstance(payload, dict):
            raise ValueError("invalid Codex plugin list")
        rows = payload.get("installed")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid plugin list")
    identities: list[str] = []
    for row in rows:
        identity = row.get("id" if target_client == "claude-code" else "pluginId")
        if not isinstance(identity, str) or not identity:
            raise ValueError("invalid plugin identity")
        identities.append(identity)
    return plugin_identity in identities


def _command_audit(
    sequence: int,
    stage: MarketplacePluginStage,
    argv: Sequence[str],
    command: CliCommandResult,
    started_at: datetime,
    *,
    exit_code: int | None | object = ...,
) -> PluginCliCommandAudit:
    stdout_original = len(command.stdout.encode("utf-8"))
    stderr_original = len(command.stderr.encode("utf-8"))
    stdout, stdout_truncated = _bounded_output(
        _sanitize_output(command.stdout),
        max_bytes=_MAX_OUTPUT_BYTES,
        max_lines=_MAX_OUTPUT_LINES,
    )
    stderr, stderr_truncated = _bounded_output(
        _sanitize_output(command.stderr),
        max_bytes=_MAX_OUTPUT_BYTES,
        max_lines=_MAX_OUTPUT_LINES,
    )
    return PluginCliCommandAudit(
        sequence=sequence,
        stage=stage,
        argv_display=shlex.join(argv),
        exit_code=command.returncode if exit_code is ... else exit_code,
        started_at=started_at.isoformat(),
        ended_at=datetime.now(timezone.utc).isoformat(),
        stdout=stdout,
        stderr=stderr,
        stdout_original_byte_count=stdout_original,
        stderr_original_byte_count=stderr_original,
        truncated=stdout_truncated or stderr_truncated,
    )


def _sanitize_output(value: str) -> str:
    without_ansi = _ANSI_ESCAPE.sub("", value.replace("\x00", ""))
    return "".join(
        character
        for character in without_ansi
        if character in "\n\r\t" or ord(character) >= 32
    )


def _bounded_output(
    value: str,
    *,
    max_bytes: int,
    max_lines: int,
) -> tuple[str | None, bool]:
    if not value:
        return None, False
    truncated = False
    lines = value.splitlines(keepends=True)
    if len(lines) > max_lines:
        half = max_lines // 2
        value = "".join([*lines[:half], *lines[-half:]])
        truncated = True
    encoded = value.encode("utf-8")
    if len(encoded) > max_bytes:
        half = max_bytes // 2
        value = (
            encoded[:half].decode("utf-8", errors="ignore")
            + encoded[-half:].decode("utf-8", errors="ignore")
        )
        truncated = True
    return value.rstrip() or None, truncated


def _first_diagnostic(stderr: str, stdout: str) -> str | None:
    for candidate in (stderr, stdout):
        for line in candidate.splitlines():
            if line.strip():
                return line.strip()
    return None


def _exception_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


__all__ = [
    "CliCommandResult",
    "CliCommandRunner",
    "PluginCliInstallResult",
    "PluginCliCommandAudit",
    "TargetClientPluginCliInstaller",
    "SubprocessCliCommandRunner",
    "marketplace_add_argv",
    "marketplace_list_argv",
    "marketplace_visible",
    "plugin_install_argv",
    "plugin_enable_argv",
    "plugin_list_argv",
    "plugin_visible",
]
