"""Provider-native one-shot Marketplace plugin installation."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

MarketplaceProvider = Literal["claude-code", "codex"]
MarketplacePluginStage = Literal[
    "marketplace-add",
    "plugin-install",
    "marketplace-list",
    "plugin-list",
    "completed",
]

_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_OUTPUT_LINES = 400
_MAX_MESSAGE_BYTES = 4096
_MAX_MESSAGE_LINES = 20
_REDACTED = "[REDACTED]"
_RUNTIME_HOME_TOKEN = "${RUNTIME_HOME}"
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?" r"-----END [^-\r\n]*PRIVATE KEY-----",
    flags=re.DOTALL,
)
_URI_CREDENTIALS = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)" r"(?P<credentials>[^/\s@]+)@",
)
_BEARER_TOKEN = re.compile(
    r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]+",
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:authorization|cookie|credential|password|private[_-]?key|"
    r"secret|token)\b\s*[:=]\s*)([^\s&,;]+)"
)
_SENSITIVE_JSON_VALUE = re.compile(
    r'(?i)("(?:authorization|cookie|credential|password|private[_-]?key|'
    r'secret|token)"\s*:\s*")([^"]*)(")'
)


@dataclass(frozen=True)
class CliCommandResult:
    """Raw provider CLI process result."""

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
    """Run provider CLI commands without shell expansion."""

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


class ProviderPluginCliInstaller:
    """Install through the documented provider CLI and read back once."""

    def __init__(
        self,
        *,
        runner: CliCommandRunner | None = None,
        timeout_seconds: float = 60.0,
        runtime_home: Path | None = None,
    ) -> None:
        self._runner = runner or SubprocessCliCommandRunner()
        self._timeout_seconds = timeout_seconds
        self._runtime_roots = _runtime_roots(runtime_home)

    def install(
        self,
        *,
        provider: MarketplaceProvider,
        package_id: str,
        marketplace_id: str,
        remote_url: str,
        publish_ref: str,
    ) -> PluginCliInstallResult:
        """Execute add, install, and immediate list readback in order."""

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        plugin_identity = f"{package_id}@{marketplace_id}"
        install_message: str | None = None

        stages: tuple[tuple[MarketplacePluginStage, list[str]], ...] = (
            (
                "marketplace-add",
                marketplace_add_argv(
                    provider=provider,
                    remote_url=remote_url,
                    publish_ref=publish_ref,
                ),
            ),
            (
                "plugin-install",
                plugin_install_argv(
                    provider=provider,
                    plugin_identity=plugin_identity,
                ),
            ),
            (
                "marketplace-list",
                marketplace_list_argv(provider),
            ),
            (
                "plugin-list",
                plugin_list_argv(provider),
            ),
        )

        for stage, argv in stages:
            try:
                command = self._runner.run(
                    argv,
                    env=os.environ.copy(),
                    timeout_seconds=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                stdout_parts.append(_exception_output(exc.stdout))
                stderr_parts.append(_exception_output(exc.stderr))
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=None,
                    cli_message=_first_diagnostic(
                        stderr_parts[-1],
                        stdout_parts[-1],
                    ),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )
            except OSError as exc:
                stderr_parts.append(str(exc))
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=None,
                    cli_message=str(exc),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )
            except UnicodeError as exc:
                stderr_parts.append(str(exc))
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=None,
                    cli_message=str(exc),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )

            stdout_parts.append(command.stdout)
            stderr_parts.append(command.stderr)
            if command.returncode != 0:
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=command.returncode,
                    cli_message=_first_diagnostic(
                        command.stderr,
                        command.stdout,
                    ),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )

            if stage == "plugin-install":
                install_message = _first_diagnostic(
                    command.stderr,
                    command.stdout,
                )
                continue
            if stage not in {"marketplace-list", "plugin-list"}:
                continue

            try:
                payload = json.loads(command.stdout)
                if stage == "marketplace-list":
                    found = marketplace_visible(
                        provider,
                        payload,
                        marketplace_id,
                    )
                else:
                    found = plugin_visible(
                        provider,
                        payload,
                        plugin_identity,
                    )
            except (TypeError, ValueError, json.JSONDecodeError):
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=command.returncode,
                    cli_message=_first_diagnostic(
                        command.stderr,
                        command.stdout,
                    ),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )
            if not found:
                return self._result(
                    status="failed",
                    stage=stage,
                    exit_code=command.returncode,
                    cli_message=_first_diagnostic(
                        command.stderr,
                        command.stdout,
                    ),
                    stdout_parts=stdout_parts,
                    stderr_parts=stderr_parts,
                )

        return self._result(
            status="installed",
            stage="completed",
            exit_code=0,
            cli_message=install_message,
            stdout_parts=stdout_parts,
            stderr_parts=stderr_parts,
        )

    def _result(
        self,
        *,
        status: Literal["installed", "failed"],
        stage: MarketplacePluginStage,
        exit_code: int | None,
        cli_message: str | None,
        stdout_parts: Sequence[str],
        stderr_parts: Sequence[str],
    ) -> PluginCliInstallResult:
        stdout, stdout_truncated = _bounded_redacted(
            "\n".join(part for part in stdout_parts if part),
            runtime_roots=self._runtime_roots,
            max_bytes=_MAX_OUTPUT_BYTES,
            max_lines=_MAX_OUTPUT_LINES,
        )
        stderr, stderr_truncated = _bounded_redacted(
            "\n".join(part for part in stderr_parts if part),
            runtime_roots=self._runtime_roots,
            max_bytes=_MAX_OUTPUT_BYTES,
            max_lines=_MAX_OUTPUT_LINES,
        )
        message, message_truncated = _bounded_redacted(
            cli_message or "",
            runtime_roots=self._runtime_roots,
            max_bytes=_MAX_MESSAGE_BYTES,
            max_lines=_MAX_MESSAGE_LINES,
        )
        return PluginCliInstallResult(
            status=status,
            stage=stage,
            exit_code=exit_code,
            cli_message=message,
            stdout=stdout,
            stderr=stderr,
            truncated=(stdout_truncated or stderr_truncated or message_truncated),
        )


def marketplace_add_argv(
    *,
    provider: MarketplaceProvider,
    remote_url: str,
    publish_ref: str,
) -> list[str]:
    """Build the documented provider marketplace-add argv."""

    if provider == "claude-code":
        return [
            "claude",
            "plugin",
            "marketplace",
            "add",
            f"{remote_url}#{publish_ref}",
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
        publish_ref,
        "--sparse",
        ".agents/plugins",
        "--sparse",
        "codex",
    ]


def plugin_install_argv(
    *,
    provider: MarketplaceProvider,
    plugin_identity: str,
) -> list[str]:
    """Build the documented provider plugin-install argv."""

    if provider == "claude-code":
        return [
            "claude",
            "plugin",
            "install",
            plugin_identity,
            "--scope",
            "user",
        ]
    return ["codex", "plugin", "add", plugin_identity]


def marketplace_list_argv(provider: MarketplaceProvider) -> list[str]:
    executable = "claude" if provider == "claude-code" else "codex"
    return [executable, "plugin", "marketplace", "list", "--json"]


def plugin_list_argv(provider: MarketplaceProvider) -> list[str]:
    executable = "claude" if provider == "claude-code" else "codex"
    return [executable, "plugin", "list", "--json"]


def marketplace_visible(
    provider: MarketplaceProvider,
    payload: Any,
    marketplace_id: str,
) -> bool:
    """Validate official list shape and locate the requested marketplace."""

    if provider == "claude-code":
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
    provider: MarketplaceProvider,
    payload: Any,
    plugin_identity: str,
) -> bool:
    """Validate official list shape and locate the installed plugin."""

    if provider == "claude-code":
        rows = payload
    else:
        if not isinstance(payload, dict):
            raise ValueError("invalid Codex plugin list")
        rows = payload.get("installed")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid plugin list")
    identities: list[str] = []
    for row in rows:
        identity = row.get("id" if provider == "claude-code" else "pluginId")
        if not isinstance(identity, str) or not identity:
            raise ValueError("invalid plugin identity")
        identities.append(identity)
    return plugin_identity in identities


def _runtime_roots(runtime_home: Path | None) -> tuple[str, ...]:
    candidates = [
        runtime_home or Path.home(),
        *(
            Path(value)
            for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR")
            if (value := os.environ.get(name))
        ),
    ]
    roots: set[str] = set()
    for candidate in candidates:
        try:
            value = str(candidate.resolve(strict=False))
        except (OSError, RuntimeError):
            value = str(candidate)
        if value not in {"", "/"}:
            roots.add(value.rstrip("/"))
    return tuple(sorted(roots, key=len, reverse=True))


def _bounded_redacted(
    value: str,
    *,
    runtime_roots: Sequence[str],
    max_bytes: int,
    max_lines: int,
) -> tuple[str | None, bool]:
    if not value:
        return None, False
    sanitized = _PRIVATE_KEY_BLOCK.sub(_REDACTED, value)
    sanitized = _URI_CREDENTIALS.sub(
        lambda match: f"{match.group('scheme')}{_REDACTED}@",
        sanitized,
    )
    sanitized = _BEARER_TOKEN.sub(rf"\1{_REDACTED}", sanitized)
    sanitized = _SENSITIVE_ASSIGNMENT.sub(rf"\1{_REDACTED}", sanitized)
    sanitized = _SENSITIVE_JSON_VALUE.sub(
        rf"\1{_REDACTED}\3",
        sanitized,
    )
    for root in runtime_roots:
        sanitized = sanitized.replace(root, _RUNTIME_HOME_TOKEN)

    truncated = False
    lines = sanitized.splitlines(keepends=True)
    if len(lines) > max_lines:
        sanitized = "".join(lines[:max_lines])
        truncated = True
    encoded = sanitized.encode("utf-8")
    if len(encoded) > max_bytes:
        sanitized = encoded[:max_bytes].decode("utf-8", errors="ignore")
        truncated = True
    return sanitized.rstrip() or None, truncated


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
    "ProviderPluginCliInstaller",
    "SubprocessCliCommandRunner",
    "marketplace_add_argv",
    "marketplace_list_argv",
    "marketplace_visible",
    "plugin_install_argv",
    "plugin_list_argv",
    "plugin_visible",
]
