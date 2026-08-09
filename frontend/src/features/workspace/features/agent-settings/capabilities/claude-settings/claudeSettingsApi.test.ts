import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { registerExecutionGrantProvider } from '@/shared/api/apiClient';
import { claudeSettingsApi } from './claudeSettingsApi';

describe('claudeSettingsApi raw settings', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    registerExecutionGrantProvider(async () => 'signed-execution-grant');
  });

  afterEach(() => registerExecutionGrantProvider(null));

  it('maps unified error envelopes through the shared parser', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            errorCode: 'REVISION_CONFLICT',
            message: 'Settings were modified',
            validationResults: [{ path: 'settings.json' }],
          },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    await expect(
      claudeSettingsApi.updateRawSettings('http://runtime.test', 'ws-1', 'project', { model: 'sonnet' }),
    ).rejects.toMatchObject({
      message: 'Settings were modified',
      errorCode: 'REVISION_CONFLICT',
      validationResults: [{ path: 'settings.json' }],
    });
  });
});
