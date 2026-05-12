import { beforeEach, describe, expect, it, vi } from 'vitest';
import { codexSettingsApi } from './codexSettingsApi';

describe('codexSettingsApi raw config', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('reads and writes raw TOML config for the selected layer', async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ workspaceId: 'ws-1', layer: 'user', content: 'model = "gpt-5.3-codex"\n' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ workspaceId: 'ws-1', layer: 'project', content: 'sandbox_mode = "workspace-write"\n' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      );

    const raw = await codexSettingsApi.getRawConfig('http://runtime.test', 'ws-1', 'user');
    const updated = await codexSettingsApi.updateRawConfig(
      'http://runtime.test',
      'ws-1',
      'project',
      'sandbox_mode = "workspace-write"\n',
    );

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://runtime.test/api/v1/workspaces/ws-1/codex/config?layer=user',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://runtime.test/api/v1/workspaces/ws-1/codex/config?layer=project',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ content: 'sandbox_mode = "workspace-write"\n' }),
      }),
    );
    expect(raw.content).toBe('model = "gpt-5.3-codex"\n');
    expect(updated.content).toBe('sandbox_mode = "workspace-write"\n');
  });
});
