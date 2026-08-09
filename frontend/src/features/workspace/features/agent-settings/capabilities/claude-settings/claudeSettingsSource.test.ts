import { beforeEach, describe, expect, it, vi } from 'vitest';
import { claudeSettingsApi } from './claudeSettingsApi';
import { createClaudeSettingsSource } from './claudeSettingsSource';

vi.mock('./claudeSettingsApi', () => ({
  claudeSettingsApi: {
    getRawSettings: vi.fn(),
    updateRawSettings: vi.fn(),
  },
}));

describe('createClaudeSettingsSource', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads formatted JSON and saves parsed settings by scope', async () => {
    vi.mocked(claudeSettingsApi.getRawSettings).mockResolvedValue({
      scope: 'project',
      path: '/workspace/.claude/settings.json',
      content: { model: 'opus' },
    });
    vi.mocked(claudeSettingsApi.updateRawSettings).mockResolvedValue({
      scope: 'project',
      path: '/workspace/.claude/settings.json',
      content: { model: 'sonnet' },
    });

    const source = createClaudeSettingsSource('http://runtime.test', 'ws-1');

    expect(source.format).toBe('json');
    expect(source.scopes.map((scope) => scope.id)).toEqual(['local', 'project', 'user']);
    await expect(source.load('project')).resolves.toEqual({ content: '{\n  "model": "opus"\n}' });
    await source.save('project', '{"model":"sonnet"}');

    expect(claudeSettingsApi.getRawSettings).toHaveBeenCalledWith('http://runtime.test', 'ws-1', 'project');
    expect(claudeSettingsApi.updateRawSettings).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      { model: 'sonnet' },
    );
  });
});
