"""Test Claude Code module __init__ files - Quick coverage boost"""

import pytest


def test_claude_md_init():
    """Test claude_md __init__ module"""
    from app.modules.claude_code.claude_md import router
    assert router is not None


def test_claude_md_dependencies():
    """Test claude_md dependencies"""
    from app.modules.claude_code.claude_md.dependencies import get_claude_md_service
    service = get_claude_md_service()
    assert service is not None


def test_hooks_init():
    """Test hooks __init__ module"""
    from app.modules.claude_code.hooks import router
    assert router is not None


def test_hooks_dependencies():
    """Test hooks dependencies"""
    from app.modules.claude_code.hooks.dependencies import get_hook_service
    service = get_hook_service()
    assert service is not None


def test_mcp_init():
    """Test mcp __init__ module"""
    from app.modules.claude_code.mcp import router
    assert router is not None


def test_mcp_dependencies():
    """Test mcp dependencies"""
    from app.modules.claude_code.mcp.dependencies import get_mcp_service
    service = get_mcp_service()
    assert service is not None


def test_memory_init():
    """Test memory __init__ module"""
    from app.modules.claude_code.memory import router
    assert router is not None


def test_memory_dependencies():
    """Test memory dependencies"""
    from app.modules.claude_code.memory.dependencies import get_memory_service
    service = get_memory_service()
    assert service is not None


def test_output_styles_init():
    """Test output_styles __init__ module"""
    from app.modules.claude_code.output_styles import router
    assert router is not None


def test_output_styles_dependencies():
    """Test output_styles dependencies"""
    from app.modules.claude_code.output_styles.dependencies import get_output_style_service
    service = get_output_style_service()
    assert service is not None


def test_settings_init():
    """Test settings __init__ module"""
    from app.modules.claude_code.settings import router
    assert router is not None


def test_slash_commands_init():
    """Test slash_commands __init__ module"""
    from app.modules.claude_code.slash_commands import router
    assert router is not None


def test_slash_commands_dependencies():
    """Test slash_commands dependencies"""
    from app.modules.claude_code.slash_commands.dependencies import get_slash_command_service
    service = get_slash_command_service()
    assert service is not None


def test_subagents_init():
    """Test subagents __init__ module"""
    from app.modules.claude_code.subagents import router
    assert router is not None


def test_subagents_dependencies():
    """Test subagents dependencies"""
    from app.modules.claude_code.subagents.dependencies import get_subagent_service
    service = get_subagent_service()
    assert service is not None


def test_claude_code_root_init():
    """Test claude_code root module"""
    from app.modules import claude_code
    assert claude_code.router is not None


def test_openspec_init():
    """Test openspec module"""
    from app.modules.openspec import router
    assert router is not None


def test_openspec_dependencies():
    """Test openspec dependencies"""
    from app.modules.openspec.dependencies import get_openspec_service
    service = get_openspec_service()
    assert service is not None
