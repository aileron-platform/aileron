import { describe, expect, it } from 'vitest';
import { AGENT_TOOL_CONFIGS } from './agentToolConfigs';
import type { AgentToolConfig } from './types';

const actionableSubViews = (config: AgentToolConfig) => config.availableSubViews;

describe('AGENT_TOOL_CONFIGS', () => {
  it('hides unsupported hooks for Codex and OpenCode', () => {
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.hooks?.supported).toBe(false);
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.hooks?.supported).toBe(false);
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.codex)).not.toContain('hooks');
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.opencode)).not.toContain('hooks');
  });

  it('keeps scripts as an agent-settings capability but only exposes Claude initially', () => {
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.scripts?.supported).toBe(true);
    expect(actionableSubViews(AGENT_TOOL_CONFIGS.claude)).toContain('scripts');

    for (const tool of ['gemini', 'codex', 'opencode'] as const) {
      expect(AGENT_TOOL_CONFIGS[tool].capabilities.scripts?.supported).toBe(false);
      expect(actionableSubViews(AGENT_TOOL_CONFIGS[tool])).not.toContain('scripts');
    }
  });

  it('configures slash command formats per tool', () => {
    expect(AGENT_TOOL_CONFIGS.claude.capabilities.slashCommands?.format).toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.gemini.capabilities.slashCommands?.format).toBe('toml');
    expect(AGENT_TOOL_CONFIGS.codex.capabilities.slashCommands?.format).toBe('markdown');
    expect(AGENT_TOOL_CONFIGS.opencode.capabilities.slashCommands?.format).toBe('markdown');
  });
});
