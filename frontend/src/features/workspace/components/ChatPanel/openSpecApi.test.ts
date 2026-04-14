import { beforeEach, describe, expect, it, vi } from 'vitest';

const { clientGetMock } = vi.hoisted(() => ({
  clientGetMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class {
    get = clientGetMock;
  },
}));

import { openSpecApi } from './openSpecApi';

describe('openSpecApi.getWorkspaceState', () => {
  beforeEach(() => {
    clientGetMock.mockReset();
    clientGetMock.mockResolvedValue({
      workspaceId: 'ws-1',
      state: { cliInstalled: true, initialized: true, profile: 'core', activeChanges: [] },
      actions: [],
      changes: [],
    });
  });

  it('passes OpenSpec action context as query params', async () => {
    await openSpecApi.getWorkspaceState('http://runtime.local', 'ws-1', {
      subview: 'complete',
      focusedChangeName: 'done-change',
    });

    expect(clientGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/openspec?subview=complete&focusedChangeName=done-change',
    );
  });

  it('omits query params when no context is provided', async () => {
    await openSpecApi.getWorkspaceState('http://runtime.local', 'ws-1');

    expect(clientGetMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/openspec');
  });
});
