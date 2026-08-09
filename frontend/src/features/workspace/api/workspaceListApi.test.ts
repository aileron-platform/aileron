import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({ apiClient: apiClientMock }));

import { fetchWorkspaceList } from './workspaceListApi';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';

describe('workspace API', () => {
  beforeEach(() => {
    apiClientMock.get.mockReset();
  });

  it('fetches the workspace list using the requested page size', async () => {
    const response = {
      items: [{
        id: 'workspace-1',
        name: 'Workspace One',
        accessRole: 'manager',
        accessSource: 'direct_share',
        accessSources: ['direct_share'],
        allowedOperations: [OPERATION_IDS.workspaceDetailRead],
      }],
    };
    apiClientMock.get.mockResolvedValue(response);

    await expect(fetchWorkspaceList(100)).resolves.toEqual(response);
    expect(apiClientMock.get).toHaveBeenCalledWith('/workspaces?page=1&pageSize=100');
  });

  it('filters list entries with malformed or incomplete authorization fields', async () => {
    apiClientMock.get.mockResolvedValue({
      items: [
        {
          id: 'workspace-reader',
          accessRole: 'reader',
          accessSource: 'direct_share',
          accessSources: ['direct_share'],
          allowedOperations: [OPERATION_IDS.workspaceDetailRead],
        },
        { id: 'workspace-missing-role' },
        { id: 'workspace-unknown-role', accessRole: 'admin' },
        {
          id: 'workspace-missing-access-source',
          accessRole: 'reader',
          allowedOperations: [OPERATION_IDS.workspaceDetailRead],
        },
      ],
    });

    await expect(fetchWorkspaceList()).resolves.toEqual({
      items: [{
        id: 'workspace-reader',
        accessRole: 'reader',
        accessSource: 'direct_share',
        accessSources: ['direct_share'],
        allowedOperations: [OPERATION_IDS.workspaceDetailRead],
      }],
    });
  });

});
