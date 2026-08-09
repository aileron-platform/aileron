import { describe, expect, it } from 'vitest';
import { Bot, Brain, Network, Settings } from 'lucide-react';
import {
  AGENT_TOOL_ICONS,
  getAgentToolSubViewNavigationMeta,
} from './agentToolNavigationModel';

describe('agentToolNavigationModel', () => {
  it('resolves workspace navigation metadata for known agent subviews', () => {
    expect(getAgentToolSubViewNavigationMeta('agents-md').labelKey).toBe('workspace.agentSettings.common.subViews.agentsMd');
    expect(getAgentToolSubViewNavigationMeta('mcp').labelKey).toBe('workspace.navigation.sub.claudeCodeSettings.mcp');
    expect(getAgentToolSubViewNavigationMeta('subagents').labelKey).toBe('workspace.agentSettings.common.subViews.subagents');
    expect(getAgentToolSubViewNavigationMeta('settings').labelKey).toBe('workspace.agentSettings.common.subViews.settings');
    expect(getAgentToolSubViewNavigationMeta('memory').labelKey).toBe('workspace.agentSettings.common.subViews.memory');
    expect(AGENT_TOOL_ICONS.mcp).toBe(Network);
    expect(AGENT_TOOL_ICONS.subagents).toBe(Bot);
    expect(AGENT_TOOL_ICONS.memory).toBe(Brain);
  });

  it('falls back to the common subview namespace and settings icon for unknown subviews', () => {
    const meta = getAgentToolSubViewNavigationMeta('custom-view');

    expect(meta.labelKey).toBe('workspace.agentSettings.common.subViews.unknown');
    expect(meta.icon).toBe(Settings);
  });

  it('does not expose Gemini-specific navigation metadata', () => {
    expect(getAgentToolSubViewNavigationMeta('gemini-md').labelKey).toBe('workspace.agentSettings.common.subViews.unknown');
  });
});
