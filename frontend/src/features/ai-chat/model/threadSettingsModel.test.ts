import { describe, expect, it } from 'vitest';
import type { WorkspaceCapabilities } from './threadCapabilitiesModel';
import { defaultSettings, normalizeThreadSettings, selectTool } from './threadSettingsModel';

const caps: WorkspaceCapabilities = {
  defaultTool: 'claude',
  tools: [
    {
      id: 'claude',
      models: ['opus-4.8', 'sonnet-5'],
      defaultModel: 'opus-4.8',
      modes: ['execute', 'plan'],
      defaultMode: 'execute',
      contextWindow: 200000,
    },
    {
      id: 'codex',
      models: ['gpt-5.6-sol'],
      defaultModel: 'gpt-5.6-sol',
      modes: null,
      defaultMode: null,
      contextWindow: 128000,
    },
  ],
};

describe('threadSettingsModel', () => {
  it('switching tool falls back to that tool default model when current unsupported', () => {
    const next = selectTool(caps, { agenticTool: 'claude', model: 'sonnet-5', claudeMode: 'plan' }, 'codex');

    expect(next).toEqual({ agenticTool: 'codex', model: 'gpt-5.6-sol', claudeMode: null });
  });

  it('switching back to claude restores default mode', () => {
    const next = selectTool(caps, { agenticTool: 'codex', model: 'gpt-5.6-sol', claudeMode: null }, 'claude');

    expect(next.claudeMode).toBe('execute');
  });

  it('defaultSettings uses defaultTool + its defaults', () => {
    expect(defaultSettings(caps)).toEqual({ agenticTool: 'claude', model: 'opus-4.8', claudeMode: 'execute' });
  });

  it('normalizes a stale model to the selected tool default', () => {
    expect(normalizeThreadSettings(caps, {
      agenticTool: 'codex',
      model: 'removed-model',
      claudeMode: 'plan',
    })).toEqual({
      agenticTool: 'codex',
      model: 'gpt-5.6-sol',
      claudeMode: null,
    });
  });
});
