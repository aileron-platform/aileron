import { describe, expect, it } from 'vitest';
import { getAgentSubViewLabelKey } from './agentSubViewLabelModel';

describe('agentSubViewLabelModel', () => {
  it('resolves shared agent settings subview label keys', () => {
    expect(getAgentSubViewLabelKey('claude-md')).toBe('workspace.agentSettings.common.subViews.claudeMd');
    expect(getAgentSubViewLabelKey('agents-md')).toBe('workspace.agentSettings.common.subViews.agentsMd');
    expect(getAgentSubViewLabelKey('slash-commands')).toBe('workspace.agentSettings.common.subViews.slashCommands');
    expect(getAgentSubViewLabelKey('output-styles')).toBe('workspace.agentSettings.common.subViews.outputStyles');
  });

  it('falls back to the unknown subview label key', () => {
    expect(getAgentSubViewLabelKey('not-registered')).toBe('workspace.agentSettings.common.subViews.unknown');
    expect(getAgentSubViewLabelKey('gemini-md')).toBe('workspace.agentSettings.common.subViews.unknown');
  });
});
