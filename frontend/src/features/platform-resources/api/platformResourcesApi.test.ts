import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({ apiClient: apiClientMock }));

import {
  getPlatformResourceCapacityTrend,
  getPlatformResourceResourceTrend,
  getPlatformResourceSummary,
  getWorkspaceCapacityExpansion,
  listPlatformKnowledgeBases,
  listPlatformWorkspaces,
  reassignPlatformResourceOwner,
  requestWorkspaceCapacityExpansion,
  searchPlatformResourceOwnerCandidates,
  updatePlatformKnowledgeBaseQuota,
} from './platformResourcesApi';

describe('platformResourcesApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the paged Admin-only workspace and knowledge base endpoints', async () => {
    apiClientMock.get.mockResolvedValue({ items: [], total: 0, page: 2, pageSize: 25 });

    await listPlatformWorkspaces({ q: 'platform docs', page: 2, pageSize: 25 });
    await listPlatformKnowledgeBases({ q: '', page: 1, pageSize: 25 });

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/platform-resources/workspaces?q=platform%20docs&page=2&pageSize=25',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/platform-resources/knowledge-bases?q=&page=1&pageSize=25',
    );
  });

  it('loads each statistics block through an independent endpoint', async () => {
    apiClientMock.get.mockResolvedValue({});

    await getPlatformResourceSummary('workspaces', '30d', true);
    await getPlatformResourceResourceTrend('knowledge-bases', '7d');
    await getPlatformResourceCapacityTrend('workspaces', '90d');

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/platform-resources/workspaces/statistics/summary?range=30d&refresh=true',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/platform-resources/knowledge-bases/statistics/resource-trend?range=7d&refresh=false',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      3,
      '/platform-resources/workspaces/statistics/capacity-trend?range=90d&refresh=false',
    );
  });

  it('uses dedicated Admin governance endpoints for quota and expansion', async () => {
    apiClientMock.put.mockResolvedValue({});
    apiClientMock.post.mockResolvedValue({});

    await updatePlatformKnowledgeBaseQuota('kb/one', null);
    await requestWorkspaceCapacityExpansion('ws/one', {
      storageKind: 'runtime_home',
      requestedBytes: 4 * 1024 ** 3,
    });
    await getWorkspaceCapacityExpansion('ws/one', 'request/one');

    expect(apiClientMock.put).toHaveBeenCalledWith(
      '/platform-resources/knowledge-bases/kb%2Fone/quota',
      { quotaBytes: null },
    );
    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/platform-resources/workspaces/ws%2Fone/capacity-expansions',
      { storageKind: 'runtime_home', requestedBytes: 4 * 1024 ** 3 },
    );
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/platform-resources/workspaces/ws%2Fone/capacity-expansions/request%2Fone',
    );
  });

  it('posts the canonical owner reassignment payload and returns the safe summary', async () => {
    const response = {
      id: 'ws-1',
      name: 'Workspace One',
      runtimeStatus: 'stopped',
      owner: {
        id: 'user-2',
        username: 'next-owner',
        displayName: 'Next Owner',
        avatarUrl: null,
      },
    };
    apiClientMock.post.mockResolvedValue(response);

    await expect(reassignPlatformResourceOwner('workspaces', 'ws-1', {
      targetUserId: 'user-2',
      reason: 'Operational ownership change',
    })).resolves.toEqual(response);

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/platform-resources/workspaces/ws-1/owner-reassignment',
      {
        targetUserId: 'user-2',
        reason: 'Operational ownership change',
      },
    );
  });

  it('searches owner candidates through the member-safe user endpoint', async () => {
    apiClientMock.get.mockResolvedValue({
      items: [{
        id: 'user-2',
        username: 'next-owner',
        displayName: 'Next Owner',
        email: 'not-exposed-by-platform-resource-summary@example.com',
      }],
    });

    await expect(searchPlatformResourceOwnerCandidates('next owner')).resolves.toEqual([{
      id: 'user-2',
      username: 'next-owner',
      displayName: 'Next Owner',
    }]);
    expect(apiClientMock.get).toHaveBeenCalledWith('/users?query=next%20owner&limit=8');
  });

  it('forwards AbortSignal through read requests', async () => {
    const signal = new AbortController().signal;
    apiClientMock.get.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 25 });

    await listPlatformWorkspaces({ q: '', page: 1, pageSize: 25 }, signal);

    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/platform-resources/workspaces?q=&page=1&pageSize=25',
      { signal },
    );
  });
});
