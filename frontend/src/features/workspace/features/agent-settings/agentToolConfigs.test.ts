import { describe, expect, it } from 'vitest';
import { AGENT_TOOL_CONFIGS } from './agentToolConfigs';
import type { AgentToolConfig } from './types';

const actionableSubViews = (config: AgentToolConfig) => config.availableSubViews;

describe('AGENT_TOOL_CONFIGS', () => {
  it('exposes Codex hooks in navigation with the official lifecycle events', () => {
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.supported).toBe(true);
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.scopes).toContain('plugin');
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.codex)).toContain('hooks');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.events.map((event) => event.value)).toEqual([
      'SessionStart',
      'PreToolUse',
      'PostToolUse',
      'PermissionRequest',
      'UserPromptSubmit',
      'Stop',
    ]);
  });

  it('hides unsupported hooks for OpenCode', () => {
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.hooks?.supported).toBe(false);
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.opencode)).not.toContain('hooks');
  });

  it('exposes the supported Codex settings navigation surface', () => {
    expect(AGENT_TOOL_CONFIGS.codex.availableScopes).toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.mcp?.scopes).toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.skills?.scopes).toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.skills?.readOnlyScopes).toContain('plugin');
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.codex)).toEqual([
      'agents-md',
      'mcp',
      'skills',
      'prompts',
      'subagents',
      'hooks',
      'rules',
      'plugins',
    ]);
  });

  it('keeps scripts unsupported for every agent settings surface', () => {
    for (const tool of ['claude', 'gemini', 'codex', 'opencode'] as const) {
      expect(AGENT_TOOL_CONFIGS[tool].capabilities.scripts?.supported).toBe(false);
      expect(actionableSubViews(AGENT_TOOL_CONFIGS[tool])).not.toContain('scripts');
    }
  });

  it('configures slash command formats per tool', () => {
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.slashCommands?.format).toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.slashCommands?.scopes).toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.slashCommands?.format).toBe('toml');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.slashCommands?.format).toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.slashCommands?.format).toBe('markdown');
  });

  it('opens Gemini subagents and extensions navigation without memory', () => {
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.agentDefinitions?.supported).toBe(true);
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.agentDefinitions?.format).toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.mcp?.scopes).toContain('extension');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.hooks?.scopes).toContain('extension');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.slashCommands?.scopes).toContain('extension');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.skills?.readOnlyScopes).toContain('extension');
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.gemini)).toEqual([
      'gemini-md',
      'mcp',
      'skills',
      'slash-commands',
      'subagents',
      'hooks',
      'extensions',
    ]);
  });
});
