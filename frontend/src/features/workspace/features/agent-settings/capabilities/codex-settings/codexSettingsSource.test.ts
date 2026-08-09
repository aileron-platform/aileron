import { beforeEach, describe, expect, it, vi } from 'vitest';
import { codexSettingsApi } from './codexSettingsApi';
import { createCodexSettingsSource } from './codexSettingsSource';

vi.mock('./codexSettingsApi', () => ({
  codexSettingsApi: {
    getRawConfig: vi.fn(),
    updateRawConfig: vi.fn(),
  },
}));

describe('createCodexSettingsSource', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and saves TOML config by scope', async () => {
    vi.mocked(codexSettingsApi.getRawConfig).mockResolvedValue({
      workspaceId: 'ws-1',
      scope: 'project',
      content: 'model = "gpt-5.6-sol"',
    });
    vi.mocked(codexSettingsApi.updateRawConfig).mockResolvedValue({
      workspaceId: 'ws-1',
      scope: 'project',
      content: 'model = "gpt-5.6-sol"',
    });

    const source = createCodexSettingsSource('http://runtime.test', 'ws-1');

    expect(source.format).toBe('toml');
    expect(source.scopes.map((scope) => scope.id)).toEqual(['user', 'project']);
    await expect(source.load('project')).resolves.toEqual({ content: 'model = "gpt-5.6-sol"' });
    await source.save('project', 'model = "gpt-5.6-sol"');

    expect(codexSettingsApi.getRawConfig).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      { signal: undefined },
    );
    expect(codexSettingsApi.updateRawConfig).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      'model = "gpt-5.6-sol"',
    );
  });
});
