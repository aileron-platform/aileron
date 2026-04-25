import { beforeEach, describe, expect, it, vi } from 'vitest';

const { deleteMock, postMock } = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    delete: deleteMock,
    post: postMock,
  },
}));

import { workspaceLifecycleApi } from './workspaceLifecycleApi';

describe('workspaceLifecycleApi', () => {
  beforeEach(() => {
    deleteMock.mockReset();
    postMock.mockReset();
  });

  it('maps deleteWorkspace to the delete endpoint', async () => {
    deleteMock.mockResolvedValue({ status: 'deleting' });

    await workspaceLifecycleApi.deleteWorkspace('ws-123');

    expect(deleteMock).toHaveBeenCalledWith('/workspaces/ws-123');
  });

  it('maps rebuild and restart actions to the expected endpoints', async () => {
    postMock.mockResolvedValue({ status: 'restarting' });

    await workspaceLifecycleApi.rebuildWorkspace('ws-123');
    await workspaceLifecycleApi.restartRuntime('ws-123');
    await workspaceLifecycleApi.restartWorkspace('ws-123');
    await workspaceLifecycleApi.restartBrowserContainer('ws-123');
    await workspaceLifecycleApi.restartCanvasContainer('ws-123');

    expect(postMock).toHaveBeenNthCalledWith(1, '/workspaces/ws-123/rebuild');
    expect(postMock).toHaveBeenNthCalledWith(2, '/workspaces/ws-123/rebuild');
    expect(postMock).toHaveBeenNthCalledWith(3, '/workspaces/ws-123/rebuild');
    expect(postMock).toHaveBeenNthCalledWith(4, '/workspaces/ws-123/restart-browser');
    expect(postMock).toHaveBeenNthCalledWith(5, '/workspaces/ws-123/restart-canvas');
  });
});
