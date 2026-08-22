from __future__ import annotations

import json
from typing import Mapping, Sequence

import pytest

from app.modules.marketplace_operations.plugin_cli_install import (
    CliCommandResult,
    TargetClientPluginCliInstaller,
    marketplace_add_argv,
    plugin_enable_argv,
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


def _success_results(target_client: str) -> list[CliCommandResult]:
    if target_client == "claude-code":
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
        *([_ok("plugin enabled")] if target_client == "claude-code" else []),
        _ok(json.dumps(marketplaces)),
        _ok(json.dumps(plugins)),
    ]


def test_claude_and_codex_argv_are_target_client_native_and_keep_scp_remote() -> None:
    remote = "git@gitlab.example:team/private-marketplace.git"

    assert marketplace_add_argv(
        target_client="claude-code",
        remote_url=remote,
        registry_ref="main",
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
        target_client="codex",
        remote_url=remote,
        registry_ref="release",
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
        target_client="claude-code",
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
        target_client="codex",
        plugin_identity="demo@private-market",
    ) == ["codex", "plugin", "add", "demo@private-market"]
    assert plugin_enable_argv("demo@private-market") == [
        "claude", "plugin", "enable", "demo@private-market", "--scope", "user"
    ]


@pytest.mark.parametrize("target_client", ["claude-code", "codex"])
def test_install_runs_required_mutations_and_reads_back_once(target_client: str) -> None:
    runner = _Runner(_success_results(target_client))
    installer = TargetClientPluginCliInstaller(runner=runner)

    result = installer.install(
        target_client=target_client,  # type: ignore[arg-type]
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
    )

    assert result.status == "installed"
    assert result.stage == "completed"
    assert result.exit_code == 0
    assert len(runner.calls) == (5 if target_client == "claude-code" else 4)
    assert runner.calls[-2][-2:] == ["list", "--json"]
    assert runner.calls[-1][-2:] == ["list", "--json"]
    assert result.stdout is not None
    assert ("plugin enabled" if target_client == "claude-code" else "plugin installed") in result.stdout
    assert [command.sequence for command in result.commands] == list(
        range(len(runner.calls))
    )


@pytest.mark.parametrize(
    ("failed_index", "expected_stage"),
    [
        (0, "marketplace-add"),
        (1, "plugin-install"),
    ],
)
def test_nonzero_exit_returns_typed_stage_and_cli_output(
    failed_index: int,
    expected_stage: str,
) -> None:
    results = _success_results("codex")
    results[failed_index] = CliCommandResult(
        returncode=17,
        stdout="target_client stdout",
        stderr="target_client stderr",
    )
    runner = _Runner(results)

    result = TargetClientPluginCliInstaller(runner=runner).install(
        target_client="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == expected_stage
    assert result.exit_code == 17
    assert result.cli_message == "target_client stderr"
    assert result.stdout is not None and "target_client stdout" in result.stdout
    assert result.stderr is not None and "target_client stderr" in result.stderr
    assert len(runner.calls) == failed_index + 1


def test_claude_enable_failure_is_terminal_and_preserves_install_receipt() -> None:
    results = _success_results("claude-code")
    results[2] = CliCommandResult(9, "", "enable denied")
    result = TargetClientPluginCliInstaller(runner=_Runner(results)).install(
        target_client="claude-code",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
    )

    assert result.status == "failed"
    assert result.stage == "plugin-enable"
    assert [command.stage for command in result.commands] == [
        "marketplace-add", "plugin-install", "plugin-enable"
    ]


def test_launch_failure_returns_failed_without_exit_code() -> None:
    runner = _Runner([FileNotFoundError("claude executable not found")])

    result = TargetClientPluginCliInstaller(runner=runner).install(
        target_client="claude-code",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
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

    result = TargetClientPluginCliInstaller(runner=runner).install(
        target_client="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
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

    result = TargetClientPluginCliInstaller(runner=runner).install(
        target_client="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
    )

    assert result.status == "installed"
    assert result.stage == "completed"
    assert result.exit_code == 0
    assert result.warnings == ("marketplace.install.state-unconfirmed",)
    assert any(
        marketplace_output in (command.stdout or "")
        or plugin_output in (command.stdout or "")
        for command in result.commands
        if command.stage == expected_stage
    )


def test_output_is_bounded_without_changing_cli_text() -> None:
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
        f"{private_key}\n" + ("x" * 300000)
    )
    runner = _Runner([CliCommandResult(returncode=1, stdout="", stderr=diagnostic)])

    result = TargetClientPluginCliInstaller(runner=runner).install(
        target_client="codex",
        package_id="demo",
        marketplace_id="private-market",
        remote_url="git@gitlab.example:team/marketplace.git",
        registry_ref="main",
    )

    assert result.status == "failed"
    assert result.truncated is True
    assert result.stderr is not None
    assert "top-secret" in result.stderr
    assert "bearer-secret" in result.stderr
    assert "user:password" in result.stderr
    assert "deploy:private" in result.stderr
    assert "git@gitlab.example:team/repo.git" in result.stderr
    assert "private-material" in result.stderr
    assert "/home/developer" in result.stderr
