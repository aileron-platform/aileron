import { describe, expect, it } from 'vitest';
import { normalizeAgentType } from './agentSettingsModel';

describe('agentSettingsModel', () => {
  it('normalizes raw agent type strings to stable tool ids', () => {
    expect(normalizeAgentType('Claude Code')).toBe('claude');
    expect(normalizeAgentType('open-code')).toBe('opencode');
    expect(normalizeAgentType('unknown')).toBe('claude');
  });
});
