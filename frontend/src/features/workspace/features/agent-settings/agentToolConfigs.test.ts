import { describe, expect, it } from 'vitest';
import { AGENT_TOOL_CONFIGS } from './agentToolConfigs';
import type { AgentToolConfig } from './model/capabilities';

const actionableSubViews = (config: AgentToolConfig) => config.availableSubViews;

describe('AGENT_TOOL_CONFIGS', () => {
  it('exposes Codex hooks in navigation with the official lifecycle events', () => {
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.supported).toBe(true);
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.scopes).toContain('plugin');
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.codex)).toContain('hooks');
    expect(
      AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.events.map(event => event.value),
    ).toEqual([
      'SessionStart',
      'SubagentStart',
      'PreToolUse',
      'PostToolUse',
      'PermissionRequest',
      'PreCompact',
      'PostCompact',
      'UserPromptSubmit',
      'SubagentStop',
      'Stop',
      'SessionEnd',
    ]);
  });

  it('hides unsupported hooks for OpenCode', () => {
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.hooks?.supported).toBe(false);
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.opencode)).not.toContain('hooks');
  });

  it('exposes OpenCode subagents as markdown project and user settings', () => {
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.agentDefinitions).toMatchObject({
      supported: true,
      endpoint: 'subagents',
      scopes: ['project', 'user'],
      format: 'markdown',
      displayLabelKey: 'workspace.agentSettings.common.subViews.subagents',
    });
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.opencode)).toEqual([
      'agents-md',
      'mcp',
      'skills',
      'slash-commands',
      'subagents',
    ]);
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
      'subagents',
      'hooks',
      'prompts',
      'rules',
      'plugins',
      'settings',
    ]);
  });

  it('drives plugin settings navigation from the provider capability matrix', () => {
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.claude)).toEqual([
      'claude-md',
      'mcp',
      'skills',
      'slash-commands',
      'subagents',
      'hooks',
      'output-styles',
      'memory',
      'plugins',
      'settings',
    ]);
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.outputStyles).toMatchObject({
      scopes: ['project', 'user', 'plugin'],
      readOnlyScopes: ['plugin'],
    });
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.agentDefinitions?.scopes)
      .not.toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.slashCommands?.supported)
      .toBe(false);
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.outputStyles?.supported)
      .toBe(false);
  });

  it('removes the legacy file collection from every agent settings surface', () => {
    const removedCollection = ['scr', 'ipts'].join('');
    for (const tool of ['claude', 'codex', 'opencode'] as const) {
      expect(Object.prototype.hasOwnProperty.call(
        AGENT_TOOL_CONFIGS[tool].capabilities,
        removedCollection,
      )).toBe(false);
      expect(actionableSubViews(AGENT_TOOL_CONFIGS[tool]))
        .not.toContain(removedCollection);
    }
  });

  it('configures slash command formats per tool', () => {
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.slashCommands?.format)
      .toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.slashCommands?.scopes)
      .toContain('plugin');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.slashCommands?.format)
      .toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.slashCommands?.format)
      .toBe('markdown');
  });

  it('exposes only Claude, Codex, and OpenCode agent settings tools', () => {
    expect(Object.keys(AGENT_TOOL_CONFIGS).sort())
      .toEqual(['claude', 'codex', 'opencode']);
    expect(Object.values(AGENT_TOOL_CONFIGS).map(config => config.navigationId))
      .not.toContain('gemini');
    expect(Object.values(AGENT_TOOL_CONFIGS).flatMap(actionableSubViews))
      .not.toContain('gemini-md');
  });
});
