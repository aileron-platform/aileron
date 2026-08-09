import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  registerExecutionGrantProvider,
  registerExecutionGrantRejectionHandler,
} from '@/shared/api/apiClient';
import { codexSettingsApi } from './codexSettingsApi';

describe('codexSettingsApi raw config', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    registerExecutionGrantProvider(vi.fn().mockResolvedValue('signed-grant'));
    registerExecutionGrantRejectionHandler(null);
  });

  afterEach(() => {
    registerExecutionGrantProvider(null);
  });

  it('reads and writes raw TOML config for the selected scope', async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ workspaceId: 'ws-1', scope: 'user', content: 'model = "gpt-5.6-sol"\n' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ workspaceId: 'ws-1', scope: 'project', content: 'sandbox_mode = "workspace-write"\n' }),
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
      'http://runtime.test/api/v1/workspaces/ws-1/codex/config?scope=user',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://runtime.test/api/v1/workspaces/ws-1/codex/config?scope=project',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ content: 'sandbox_mode = "workspace-write"\n' }),
      }),
    );
    expect(raw.content).toBe('model = "gpt-5.6-sol"\n');
    expect(updated.content).toBe('sandbox_mode = "workspace-write"\n');
  });

  it('forwards an AbortSignal to fetch when loading raw config', async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ workspaceId: 'ws-1', scope: 'user', content: '' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    await codexSettingsApi.getRawConfig('http://runtime.test', 'ws-1', 'user', {
      signal: controller.signal,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://runtime.test/api/v1/workspaces/ws-1/codex/config?scope=user',
      expect.objectContaining({ method: 'GET', signal: controller.signal }),
    );
  });

  it('maps unified error envelopes through the shared parser', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            errorCode: 'REVISION_CONFLICT',
            message: 'Config was modified',
            validationResults: [{ path: 'config.toml' }],
          },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    await expect(
      codexSettingsApi.updateRawConfig('http://runtime.test', 'ws-1', 'project', 'model = "gpt-5.6-sol"\n'),
    ).rejects.toMatchObject({
      message: 'Config was modified',
      errorCode: 'REVISION_CONFLICT',
      validationResults: [{ path: 'config.toml' }],
    });
  });
});
