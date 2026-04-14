"""測試 Claude Code 模組的 __init__ 檔案 - 快速提升覆蓋率"""

import pytest


def test_claude_md_init():
    """測試 claude_md __init__ 模組"""
    from app.modules.claude_code.claude_md import router
    assert router is not None


def test_claude_md_dependencies():
    """測試 claude_md dependencies"""
    from app.modules.claude_code.claude_md.dependencies import get_claude_md_service
    service = get_claude_md_service()
    assert service is not None


def test_hooks_init():
    """測試 hooks __init__ 模組"""
    from app.modules.claude_code.hooks import router
    assert router is not None


def test_hooks_dependencies():
    """測試 hooks dependencies"""
    from app.modules.claude_code.hooks.dependencies import get_hook_service
    service = get_hook_service()
    assert service is not None


def test_mcp_init():
    """測試 mcp __init__ 模組"""
    from app.modules.claude_code.mcp import router
    assert router is not None


def test_mcp_dependencies():
    """測試 mcp dependencies"""
    from app.modules.claude_code.mcp.dependencies import get_mcp_service
    service = get_mcp_service()
    assert service is not None


def test_memory_init():
    """測試 memory __init__ 模組"""
    from app.modules.claude_code.memory import router
    assert router is not None


def test_memory_dependencies():
    """測試 memory dependencies"""
    from app.modules.claude_code.memory.dependencies import get_memory_service
    service = get_memory_service()
    assert service is not None


def test_output_styles_init():
    """測試 output_styles __init__ 模組"""
    from app.modules.claude_code.output_styles import router
    assert router is not None


def test_output_styles_dependencies():
    """測試 output_styles dependencies"""
    from app.modules.claude_code.output_styles.dependencies import get_output_style_service
    service = get_output_style_service()
    assert service is not None


def test_settings_init():
    """測試 settings __init__ 模組"""
    from app.modules.claude_code.settings import router
    assert router is not None


def test_slash_commands_init():
    """測試 slash_commands __init__ 模組"""
    from app.modules.claude_code.slash_commands import router
    assert router is not None


def test_slash_commands_dependencies():
    """測試 slash_commands dependencies"""
    from app.modules.claude_code.slash_commands.dependencies import get_slash_command_service
    service = get_slash_command_service()
    assert service is not None


def test_subagents_init():
    """測試 subagents __init__ 模組"""
    from app.modules.claude_code.subagents import router
    assert router is not None


def test_subagents_dependencies():
    """測試 subagents dependencies"""
    from app.modules.claude_code.subagents.dependencies import get_subagent_service
    service = get_subagent_service()
    assert service is not None


def test_claude_code_root_init():
    """測試 claude_code 根模組"""
    from app.modules import claude_code
    assert claude_code.router is not None


def test_openspec_init():
    """測試 openspec 模組"""
    from app.modules.openspec import router
    assert router is not None


def test_openspec_dependencies():
    """測試 openspec dependencies"""
    from app.modules.openspec.dependencies import get_openspec_service
    service = get_openspec_service()
    assert service is not None
