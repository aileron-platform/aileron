import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
}));

vi.mock('./apiClient', () => ({ apiClient: apiClientMock }));

import { getRecentWorkspace, updateRecentWorkspace } from './recentWorkspaceApi';

describe('recent workspace API', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
    apiClientMock.put.mockReset();
  });

  it('gets and normalizes the recent workspace id', async () => {
    apiClientMock.get.mockResolvedValue({ workspace_id: 'workspace-1' });

    await expect(getRecentWorkspace()).resolves.toBe('workspace-1');
    expect(apiClientMock.get).toHaveBeenCalledWith('/users/me/recent-workspace');
  });

  it('preserves a null recent workspace', async () => {
    apiClientMock.get.mockResolvedValue({ workspace_id: null });

    await expect(getRecentWorkspace()).resolves.toBeNull();
  });

  it('updates the recent workspace with the manager contract', async () => {
    apiClientMock.put.mockResolvedValue({ workspace_id: 'workspace-2' });

    await expect(updateRecentWorkspace('workspace-2')).resolves.toBeUndefined();
    expect(apiClientMock.put).toHaveBeenCalledWith('/users/me/recent-workspace', {
      workspace_id: 'workspace-2',
    });
  });
});
