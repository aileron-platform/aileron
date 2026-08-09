import { describe, expect, it } from 'vitest';
import { AGENT_TOOL_CONFIGS } from './agentToolConfigs';
import { PAGE_REGISTRY } from './pageRegistryRuntime';
import { resolveAgentSettingsPageEntry } from './pageRegistryModel';

describe('pageRegistryModel', () => {
  it('resolves supported page entries from tool config and registry', () => {
    expect(resolveAgentSettingsPageEntry(PAGE_REGISTRY, AGENT_TOOL_CONFIGS.claude, 'mcp')).not.toBeNull();
    expect(resolveAgentSettingsPageEntry(PAGE_REGISTRY, AGENT_TOOL_CONFIGS.codex, 'rules')).not.toBeNull();
    expect(resolveAgentSettingsPageEntry(PAGE_REGISTRY, AGENT_TOOL_CONFIGS.opencode, 'subagents')).not.toBeNull();
  });

  it('returns null for unmapped or unsupported page entries', () => {
    expect(resolveAgentSettingsPageEntry(PAGE_REGISTRY, AGENT_TOOL_CONFIGS.opencode, 'hooks')).toBeNull();
    expect(resolveAgentSettingsPageEntry(PAGE_REGISTRY, AGENT_TOOL_CONFIGS.codex, 'apps')).toBeNull();
    expect(resolveAgentSettingsPageEntry({
      opencode: {
        hooks: {
          render: () => null,
          requiresCapability: 'hooks',
        },
      },
    }, AGENT_TOOL_CONFIGS.opencode, 'hooks')).toBeNull();
  });

  it('covers every shared agent settings subview that navigation exposes', () => {
    const getMissingEntries = (config: typeof AGENT_TOOL_CONFIGS.opencode) =>
      config.availableSubViews.filter((subView) => (
        !resolveAgentSettingsPageEntry(PAGE_REGISTRY, config, subView)
      ));

    expect(getMissingEntries(AGENT_TOOL_CONFIGS.opencode)).toEqual([]);
    expect(getMissingEntries(AGENT_TOOL_CONFIGS.claude)).toEqual([]);
    expect(getMissingEntries(AGENT_TOOL_CONFIGS.codex)).toEqual([]);
  });

  it('does not register Gemini pages', () => {
    expect(PAGE_REGISTRY).not.toHaveProperty('gemini');
  });
});
