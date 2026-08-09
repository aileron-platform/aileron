import { beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    post: postMock,
  },
}));

import { syncSettingsToWorkspaces } from './settingsSyncApi';

describe('syncSettingsToWorkspaces', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  it('preserves the user settings sync endpoint and payload', async () => {
    const response = {
      success: true,
      message: 'ok',
      workspaces: [],
    };
    postMock.mockResolvedValue(response);

    await expect(syncSettingsToWorkspaces('user-1')).resolves.toBe(response);
    expect(postMock).toHaveBeenCalledWith('/users/user-1/settings/sync', {});
  });
});
