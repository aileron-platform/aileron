from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.internal.models import ClaudeCodeRequest, FirewallConfigRequest, GitSettingsRequest, SSHKeysRequest
from app.modules.internal.router import (
    get_workspace_setup_status,
    install_claude_md,
    install_hooks,
    install_mcp_servers,
    install_output_styles,
    install_scripts,
    install_slash_commands,
    install_subagents,
    install_template,
    internal_health_check,
    sync_claude_code,
    sync_firewall_settings,
    sync_git_settings,
    sync_ssh_keys,
)
from app.modules.internal.template_install_models import (
    CompiledTemplateFileInstallItem,
    ClaudeMdInstallRequest,
    HooksInstallRequest,
    InstallPlanRequest,
    InstallResults,
    McpInstallRequest,
    OutputStyleInstallRequest,
    ScriptFileItem,
    ScriptsInstallRequest,
    SlashCommandInstallItem,
    SlashCommandInstallRequest,
    SubagentInstallItem,
    SubagentInstallRequest,
    TemplateInstallRequest,
)


@pytest.mark.asyncio
async def test_internal_basic_routes_success() -> None:
    service = AsyncMock()
    service.setup_ssh_keys.return_value = {"ok": True}
    service.setup_claude_code.return_value = {"ok": True}
    service.setup_git_settings.return_value = {"ok": True}
    service.apply_firewall_settings.return_value = {"status": "success"}
    service.get_setup_status.return_value = {"ssh": {"status": "success", "message": "ok"}}

    assert (await sync_ssh_keys(SSHKeysRequest(private_key="k", public_key="p"), service)).success is True
    assert (await sync_claude_code(ClaudeCodeRequest(auth_method="api_key"), service)).success is True
    assert (await sync_git_settings(GitSettingsRequest(user_name="u", user_email="e@example.com"), service)).success is True
    assert (
        await sync_firewall_settings(
            FirewallConfigRequest(network_access_enabled=False, domain_access_mode="all", allowed_domains=[]),
            service,
        )
    ).success is True
    assert (await internal_health_check()).success is True
    assert (await get_workspace_setup_status(service)).checks["ssh"].status == "success"


@pytest.mark.asyncio
async def test_internal_basic_routes_error_mapping() -> None:
    service = AsyncMock()
    service.setup_ssh_keys.side_effect = RuntimeError("ssh failed")
    with pytest.raises(HTTPException):
        await sync_ssh_keys(SSHKeysRequest(private_key="k", public_key="p"), service)

    service.setup_claude_code.side_effect = RuntimeError("cc failed")
    with pytest.raises(HTTPException):
        await sync_claude_code(ClaudeCodeRequest(auth_method="api_key"), service)

    service.setup_git_settings.side_effect = RuntimeError("git failed")
    with pytest.raises(HTTPException):
        await sync_git_settings(GitSettingsRequest(user_name="u", user_email="e@example.com"), service)

    service.apply_firewall_settings.side_effect = RuntimeError("fw failed")
    with pytest.raises(HTTPException):
        await sync_firewall_settings(
            FirewallConfigRequest(network_access_enabled=False, domain_access_mode="all", allowed_domains=[]),
            service,
        )

    service.get_setup_status.side_effect = RuntimeError("status failed")
    with pytest.raises(HTTPException):
        await get_workspace_setup_status(service)


@pytest.mark.asyncio
async def test_sync_firewall_settings_handles_error_status_payload() -> None:
    service = AsyncMock()
    service.apply_firewall_settings.return_value = {"status": "error", "message": "blocked"}

    with pytest.raises(HTTPException) as exc_info:
        await sync_firewall_settings(
            FirewallConfigRequest(
                network_access_enabled=True,
                domain_access_mode="specific",
                allowed_domains=["example.com"],
            ),
            service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "blocked"


@pytest.mark.asyncio
async def test_internal_install_routes_success_and_partial_failure() -> None:
    service = AsyncMock()
    ok_results = InstallResults(created=["a"], updated=[], failed=[])
    failed_results = InstallResults(created=[], updated=[], failed=["x"])

    service.install_slash_commands.return_value = (True, ok_results)
    service.install_subagents.return_value = (False, failed_results)
    service.install_output_styles.return_value = (True, ok_results)
    service.install_claude_md.return_value = True
    service.install_mcp_servers.return_value = (True, ok_results)
    service.install_hooks.return_value = (True, InstallResults(created=["hooks.json"], updated=[], failed=[]))
    service.install_scripts.return_value = (True, ok_results, "/workspace/scripts/demo", 123)
    service.execute_init_commands.return_value = (False, "", "bad init")

    slash_req = SlashCommandInstallRequest(commands=[SlashCommandInstallItem(fileName="a.md", content="# a")])
    sub_req = SubagentInstallRequest(subagents=[SubagentInstallItem(fileName="a.md", content="# a")])
    style_req = OutputStyleInstallRequest(outputStyles=[{"fileName": "a.md", "content": "# a"}])
    mcp_req = McpInstallRequest(mcpServers={"s1": {"command": "node"}})
    hooks_req = HooksInstallRequest(hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]})
    scripts_req = ScriptsInstallRequest(templateName="demo", scripts=[ScriptFileItem(path="a.sh", content="echo hi", executable=True)])

    assert (await install_slash_commands("ws", slash_req, service)).success is True
    assert (await install_subagents("ws", sub_req, service)).success is False
    assert (await install_output_styles("ws", style_req, service)).success is True
    assert (await install_claude_md("ws", ClaudeMdInstallRequest(content="# Claude"), service)).success is True
    assert (await install_mcp_servers("ws", mcp_req, service)).success is True
    assert (await install_hooks("ws", hooks_req, service)).success is True
    assert (await install_scripts("ws", scripts_req, service)).totalFiles == 1

    template_req = TemplateInstallRequest(
        templateId="tpl-1",
        templateName="demo",
        initCommands="echo hi",
        claudeMd={"content": "# Claude"},
        slashCommands=[{"fileName": "a.md", "content": "# a"}],
        subagents=[{"fileName": "b.md", "content": "# b"}],
        outputStyles=[{"fileName": "c.md", "content": "# c"}],
        mcpServers={"s1": {"command": "node"}},
        hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]},
        scripts=[{"path": "a.sh", "content": "echo hi", "executable": True}],
    )
    template_result = await install_template("ws", template_req, service)
    assert template_result.success is False
    assert "some failures" in template_result.message


@pytest.mark.asyncio
async def test_internal_install_route_failures_raise_http_exception() -> None:
    service = AsyncMock()
    service.install_claude_md.return_value = False
    with pytest.raises(HTTPException):
        await install_claude_md("ws", ClaudeMdInstallRequest(content="# Claude"), service)

    service.install_hooks.side_effect = RuntimeError("hooks failed")
    with pytest.raises(HTTPException):
        await install_hooks(
            "ws",
            HooksInstallRequest(hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]}),
            service,
        )


@pytest.mark.asyncio
async def test_install_routes_map_service_exceptions_to_http() -> None:
    service = AsyncMock()
    service.install_slash_commands.side_effect = RuntimeError("slash failed")
    service.install_subagents.side_effect = RuntimeError("sub failed")
    service.install_output_styles.side_effect = RuntimeError("style failed")
    service.install_mcp_servers.side_effect = RuntimeError("mcp failed")
    service.install_scripts.side_effect = RuntimeError("script failed")

    with pytest.raises(HTTPException):
        await install_slash_commands(
            "ws",
            SlashCommandInstallRequest(commands=[SlashCommandInstallItem(fileName="a.md", content="# a")]),
            service,
        )

    with pytest.raises(HTTPException):
        await install_subagents(
            "ws",
            SubagentInstallRequest(subagents=[SubagentInstallItem(fileName="a.md", content="# a")]),
            service,
        )

    with pytest.raises(HTTPException):
        await install_output_styles(
            "ws",
            OutputStyleInstallRequest(outputStyles=[{"fileName": "a.md", "content": "# a"}]),
            service,
        )

    with pytest.raises(HTTPException):
        await install_mcp_servers(
            "ws",
            McpInstallRequest(mcpServers={"svc": {"command": "node"}}),
            service,
        )

    with pytest.raises(HTTPException):
        await install_scripts(
            "ws",
            ScriptsInstallRequest(templateName="demo", scripts=[ScriptFileItem(path="a.sh", content="echo hi", executable=True)]),
            service,
        )


@pytest.mark.asyncio
async def test_install_template_success_with_init_commands() -> None:
    service = AsyncMock()
    service.install_claude_md.return_value = True
    service.install_slash_commands.return_value = (True, InstallResults(created=["a"], updated=[], failed=[]))
    service.install_subagents.return_value = (True, InstallResults(created=[], updated=["b"], failed=[]))
    service.install_output_styles.return_value = (True, InstallResults(created=[], updated=[], failed=[]))
    service.install_mcp_servers.return_value = (True, InstallResults(created=["svc"], updated=[], failed=[]))
    service.install_hooks.return_value = (True, InstallResults(created=["hooks.json"], updated=[], failed=[]))
    service.install_scripts.return_value = (
        True,
        InstallResults(created=["a.sh"], updated=[], failed=[]),
        "/workspace/scripts/demo",
        8,
    )
    service.install_skills.return_value = (
        True,
        InstallResults(created=["skills/a.md"], updated=[], failed=[]),
        "/workspace/.claude/skills",
        5,
    )
    service.execute_init_commands.return_value = (True, "done", "")

    template_req = TemplateInstallRequest(
        templateId="tpl-2",
        templateName="demo",
        cliType="claude-code",
        initCommands="echo hi",
        claudeMd={"content": "# Claude"},
        slashCommands=[{"fileName": "a.md", "content": "# a"}],
        subagents=[{"fileName": "b.md", "content": "# b"}],
        outputStyles=[{"fileName": "c.md", "content": "# c"}],
        mcpServers={"svc": {"command": "node"}},
        hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]},
        scripts=[{"path": "a.sh", "content": "echo hi", "executable": True}],
        skills=[{"path": "skills/a.md", "content": "# a"}],
    )

    result = await install_template("ws", template_req, service)

    assert result.success is True
    assert result.message == "Template installation completed"
    assert result.results.hooks is not None
    assert result.results.hooks.success is True
    assert result.results.skills is not None
    assert result.results.skills.success is True
    assert service.execute_init_commands.await_count == 1


@pytest.mark.asyncio
async def test_install_template_compiled_plan_success() -> None:
    service = AsyncMock()
    service.install_compiled_files.return_value = {
        "claudeMd": InstallResults(created=["AGENTS.md"], updated=[], failed=[]),
        "slashCommands": InstallResults(created=[".codex/prompts/review.md"], updated=[], failed=[]),
        "subagents": InstallResults(created=[".codex/agents/reviewer.md"], updated=[], failed=[]),
        "outputStyles": InstallResults(created=[], updated=[], failed=[]),
        "files": InstallResults(created=[], updated=[], failed=[]),
    }
    service.install_target_output_style.return_value = (
        True,
        InstallResults(created=[], updated=["AGENTS.md"], failed=[]),
    )
    service.install_target_mcp_servers.return_value = (
        True,
        InstallResults(created=["svc"], updated=[], failed=[]),
    )
    service.install_target_hooks.return_value = (
        True,
        InstallResults(created=[], updated=[], failed=[]),
    )
    service.install_skills.return_value = (
        True,
        InstallResults(created=["skills/demo/SKILL.md"], updated=[], failed=[]),
        "/workspace/.codex/skills",
        12,
    )
    service.execute_init_commands.return_value = (True, "done", "")

    template_req = TemplateInstallRequest(
        templateId="tpl-compiled",
        templateName="demo",
        cliType="codex",
        initCommands="echo hi",
        installPlan=InstallPlanRequest(
            target="codex",
            files=[
                CompiledTemplateFileInstallItem(path="AGENTS.md", source="agents.md", content="# Agents"),
                CompiledTemplateFileInstallItem(
                    path=".codex/prompts/review.md",
                    source="commands/review.md",
                    content="# Review",
                ),
            ],
            installHints={
                "outputStyles": [{"fileName": "output-style.yaml", "content": "Keep answers concise."}],
                "mcpServers": {"svc": {"command": "node"}},
                "skills": [{"path": "demo/SKILL.md", "content": "# Skill"}],
            },
        ),
    )

    result = await install_template("ws", template_req, service)

    assert result.success is True
    assert result.results.claudeMd is not None
    assert result.results.slashCommands is not None
    assert result.results.outputStyles is not None
    assert result.results.mcp is not None
    assert result.results.skills is not None
    service.install_compiled_files.assert_awaited_once()
    service.install_target_output_style.assert_awaited_once()
    service.install_target_mcp_servers.assert_awaited_once()


@pytest.mark.asyncio
async def test_install_template_handles_section_exceptions() -> None:
    service = AsyncMock()
    service.install_claude_md.side_effect = RuntimeError("claude broken")
    service.install_slash_commands.return_value = (True, InstallResults(created=[], updated=[], failed=[]))
    service.install_subagents.side_effect = RuntimeError("sub broken")
    service.install_output_styles.return_value = (True, InstallResults(created=[], updated=[], failed=[]))
    service.install_mcp_servers.side_effect = RuntimeError("mcp broken")
    service.install_hooks.side_effect = RuntimeError("hooks broken")
    service.install_scripts.side_effect = RuntimeError("scripts broken")
    service.install_skills.side_effect = RuntimeError("skills broken")
    service.execute_init_commands.side_effect = RuntimeError("init broken")

    template_req = TemplateInstallRequest(
        templateId="tpl-3",
        templateName="demo",
        cliType="claude-code",
        initCommands="echo hi",
        claudeMd={"content": "# Claude"},
        slashCommands=[{"fileName": "a.md", "content": "# a"}],
        subagents=[{"fileName": "b.md", "content": "# b"}],
        outputStyles=[{"fileName": "c.md", "content": "# c"}],
        mcpServers={"svc": {"command": "node"}},
        hooks={"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]},
        scripts=[{"path": "a.sh", "content": "echo hi", "executable": True}],
        skills=[{"path": "skills/a.md", "content": "# a"}],
    )

    result = await install_template("ws", template_req, service)

    assert result.success is False
    assert result.results.claudeMd is not None
    assert result.results.claudeMd.error == "claude broken"
    assert result.results.subagents is not None
    assert result.results.subagents.error == "sub broken"
    assert result.results.mcp is not None
    assert result.results.hooks is not None
    assert result.results.scripts is not None
    assert result.results.skills is not None
    assert result.results.skills.error == "skills broken"
    assert service.execute_init_commands.await_count == 1
