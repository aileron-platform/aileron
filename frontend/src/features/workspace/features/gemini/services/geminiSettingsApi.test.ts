import { beforeEach, describe, expect, it, vi } from 'vitest';
import { geminiSettingsApi } from './geminiSettingsApi';

const apiClientMocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => apiClientMocks),
}));

describe('geminiSettingsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reads and writes raw Gemini settings for the selected scope', async () => {
    apiClientMocks.get.mockResolvedValueOnce({ content: { model: 'gemini-2.5-pro' } });
    apiClientMocks.put.mockResolvedValueOnce({ content: { model: 'gemini-2.5-flash' } });

    await expect(geminiSettingsApi.getRawSettings('http://runtime.test', 'ws-1', 'user')).resolves.toEqual({
      content: { model: 'gemini-2.5-pro' },
    });
    await expect(
      geminiSettingsApi.updateRawSettings('http://runtime.test', 'ws-1', 'project', {
        model: 'gemini-2.5-flash',
      }),
    ).resolves.toEqual({ content: { model: 'gemini-2.5-flash' } });

    expect(apiClientMocks.get).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/gemini/settings/raw?scope=user',
      undefined,
    );
    expect(apiClientMocks.put).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/gemini/settings/raw?scope=project',
      { content: { model: 'gemini-2.5-flash' } },
      undefined,
    );
  });
});
