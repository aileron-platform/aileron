import { describe, expect, it, vi } from 'vitest';
import { WorkspaceFileTreeDataAdapter } from './workspaceFileTreeDataAdapter';

const { apiClientMock, ApiClientMock } = vi.hoisted(() => {
  const apiClientMock = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    getBlob: vi.fn(),
  };

  return {
    apiClientMock,
    ApiClientMock: vi.fn(() => apiClientMock),
  };
});

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: ApiClientMock,
}));

describe('WorkspaceFileTreeDataAdapter', () => {
  it('uses workspace runtime base URL and appends git context to tree requests', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [{ id: 'readme', name: 'README.md', path: '/README.md', type: 'file' }] });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-auth',
      includeHidden: true,
    });

    await expect(adapter.getTree()).resolves.toHaveLength(1);

    expect(ApiClientMock).toHaveBeenCalledWith({ baseUrl: 'http://runtime.local/api/v1' });
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/files/tree?path=%2F&includeHidden=true&maxDepth=2&contextId=worktree%3Afeature-auth',
    );
  });

  it('calls the current move endpoint for move requests', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
      contextId: null,
    });

    await adapter.move('/docs/old.md', '/docs/new.md');

    expect(apiClientMock.post).toHaveBeenCalledWith('/files/move', {
      sourcePath: '/docs/old.md',
      destPath: '/docs/new.md',
    });
  });
});
