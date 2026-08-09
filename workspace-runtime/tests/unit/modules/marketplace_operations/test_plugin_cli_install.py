from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import pytest

from app.modules.marketplace_operations.plugin_cli_install import (
    CliCommandResult,
    ProviderPluginCliInstaller,
    marketplace_add_argv,
    plugin_install_argv,
)


class _Runner:
    def __init__(
        self,
        results: Sequence[CliCommandResult | Exception],
    ) -> None:
        self._results = list(results)
        self.calls: list[list[str]] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str],
        timeout_seconds: float,
    ) -> CliCommandResult:
        assert isinstance(env, dict)
        assert timeout_seconds == 60.0
        self.calls.append(list(argv))
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _ok(stdout: str = "", stderr: str = "") -> CliCommandResult:
    return CliCommandResult(returncode=0, stdout=stdout, stderr=stderr)


def _success_results(provider: str) -> list[CliCommandResult]:
    if provider == "claude-code":
        marketplaces = [{"name": "private-market"}]
        plugins = [{"id": "demo@private-market"}]
    else:
        marketplaces = {"marketplaces": [{"name": "private-market"}]}
        plugins = {
            "installed": [{"pluginId": "demo@private-market"}],
            "available": [],
        }
    return [
        _ok("marketplace added"),
        _ok("plugin installed"),
        _ok(json.dumps(marketplaces)),
        _ok(json.dumps(plugins)),
    ]


def test_claude_and_codex_argv_are_provider_native_and_keep_scp_remote() -> None:
    remote = "git@gitlab.example:team/private-marketplace.git"

    assert marketplace_add_argv(
        provider="claude-code",
        remote_url=remote,
        publish_ref="main",
    ) == [
        "claude",
        "plugin",
        "marketplace",
        "add",
        f"{remote}#main",
        "--sparse",
        ".claude-plugin",
        "claude-code",
        "--scope",
        "user",
    ]
    assert marketplace_add_argv(
        provider="codex",
        remote_url=remote,
        publish_ref="release",
    ) == [
        "codex",
        "plugin",
        "marketplace",
        "add",
        remote,
        "--ref",
        "release",
        "--sparse",
        ".agents/plugins",
        "--sparse",
        "codex",
    ]
    assert plugin_install_argv(
        provider="claude-code",
        plugin_identity="demo@private-market",
    ) == [
        "claude",
        "plugin",
        "install",
        "demo@private-market",
        "--scope",
        "user",
    ]
    assert plugin_install_argv(
        provider="codex",
        plugin_identity="demo@private-market",
    ) == ["codex", "plugin", "add", "demo@private-market"]


@pytest.mark.parametrize("provider", ["claude-code", "codex"])
def test_install_runs_four_commands_and_reads_back_once(provider: str) -> None:
    runner = _Runner(_success_results(provider))
    installer = ProviderPluginCliInstaller(runner=runner)

    result = installer.install(
        provider=provider,  # type: ignore[arg-type]
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "installed"
    assert result.stage == "completed"
    assert result.exit_code == 0
    assert len(runner.calls) == 4
    assert runner.calls[-2][-2:] == ["list", "--json"]
    assert runner.calls[-1][-2:] == ["list", "--json"]
    assert result.stdout is not None
    assert "plugin installed" in result.stdout


@pytest.mark.parametrize(
    ("failed_index", "expected_stage"),
    [
        (0, "marketplace-add"),
        (1, "plugin-install"),
        (2, "marketplace-list"),
        (3, "plugin-list"),
    ],
)
def test_nonzero_exit_returns_typed_stage_and_cli_output(
    failed_index: int,
    expected_stage: str,
) -> None:
    results = _success_results("codex")
    results[failed_index] = CliCommandResult(
        returncode=17,
        stdout="provider stdout",
        stderr="provider stderr",
    )
    runner = _Runner(results)

    result = ProviderPluginCliInstaller(runner=runner).install(
        provider="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == expected_stage
    assert result.exit_code == 17
    assert result.cli_message == "provider stderr"
    assert result.stdout is not None and "provider stdout" in result.stdout
    assert result.stderr is not None and "provider stderr" in result.stderr
    assert len(runner.calls) == failed_index + 1


def test_launch_failure_returns_failed_without_exit_code() -> None:
    runner = _Runner([FileNotFoundError("claude executable not found")])

    result = ProviderPluginCliInstaller(runner=runner).install(
        provider="claude-code",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == "marketplace-add"
    assert result.exit_code is None
    assert result.stderr == "claude executable not found"


def test_cli_output_decode_failure_returns_typed_failure() -> None:
    runner = _Runner(
        [
            UnicodeDecodeError(
                "utf-8",
                b"\xff",
                0,
                1,
                "invalid start byte",
            )
        ]
    )

    result = ProviderPluginCliInstaller(runner=runner).install(
        provider="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == "marketplace-add"
    assert result.exit_code is None
    assert result.cli_message is not None
    assert "invalid start byte" in result.cli_message


@pytest.mark.parametrize(
    ("marketplace_output", "plugin_output", "expected_stage"),
    [
        ("not-json", '{"installed":[]}', "marketplace-list"),
        (
            '{"marketplaces":[{"name":"private-market"}]}',
            '{"installed":[]}',
            "plugin-list",
        ),
    ],
)
def test_parser_and_readback_failures_keep_raw_cli_output(
    marketplace_output: str,
    plugin_output: str,
    expected_stage: str,
) -> None:
    runner = _Runner(
        [
            _ok(),
            _ok(),
            _ok(marketplace_output),
            _ok(plugin_output),
        ]
    )

    result = ProviderPluginCliInstaller(runner=runner).install(
        provider="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == expected_stage
    assert result.exit_code == 0
    assert result.stdout is not None
    assert marketplace_output in result.stdout or plugin_output in result.stdout


def test_output_is_bounded_and_redacts_secrets_credentials_and_home() -> None:
    private_key = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "private-material\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    diagnostic = (
        "token=top-secret\n"
        "Authorization: Bearer bearer-secret\n"
        "https://user:password@gitlab.example/team/repo.git\n"
        "ssh://deploy:private@gitlab.example/team/repo.git\n"
        "git@gitlab.example:team/repo.git\n"
        "/home/developer/.codex/plugins/demo\n"
        f"{private_key}\n" + ("x" * 70000)
    )
    runner = _Runner([CliCommandResult(returncode=1, stdout="", stderr=diagnostic)])

    result = ProviderPluginCliInstaller(
        runner=runner,
        runtime_home=Path("/home/developer"),
    ).install(
        provider="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        publish_ref="main",
    )

    assert result.status == "failed"
    assert result.truncated is True
    assert result.stderr is not None
    assert "top-secret" not in result.stderr
    assert "bearer-secret" not in result.stderr
    assert "user:password" not in result.stderr
    assert "deploy:private" not in result.stderr
    assert "git@gitlab.example:team/repo.git" in result.stderr
    assert "private-material" not in result.stderr
    assert "/home/developer" not in result.stderr
    assert "[REDACTED]" in result.stderr
    assert "${RUNTIME_HOME}" in result.stderr
