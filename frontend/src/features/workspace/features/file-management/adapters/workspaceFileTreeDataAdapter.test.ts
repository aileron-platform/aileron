import { beforeEach, describe, expect, it, vi } from 'vitest';
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
  registerCsrfTokenProvider: vi.fn(),
  registerExecutionGrantProvider: vi.fn(),
  registerExecutionGrantRejectionHandler: vi.fn(),
  ApiClient: ApiClientMock,
}));

describe('WorkspaceFileTreeDataAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses workspace runtime base URL and appends git context to tree requests', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [{ id: 'readme', name: 'README.md', path: '/README.md', type: 'file' }] });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-auth',
      includeHidden: true,
    });

    await expect(adapter.getTree()).resolves.toHaveLength(1);

    expect(ApiClientMock).toHaveBeenCalledWith({
      baseUrl: 'http://runtime.local/api/v1',
      unauthorizedBehavior: 'propagate',
      executionAudience: 'workspace-runtime',
    });
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/files/tree?path=%2F&includeHidden=true&maxDepth=2&contextId=worktree%3Afeature-auth',
    );
  });

  it('normalizes plain file tree arrays through the shared parser', async () => {
    apiClientMock.get.mockResolvedValueOnce([
      { id: 'readme', name: 'README.md', path: '/README.md', type: 'file' },
    ]);

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await expect(adapter.getTree()).resolves.toEqual([
      { id: 'readme', name: 'README.md', path: '/README.md', type: 'file' },
    ]);
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

  it('normalizes an empty upload target to the root directory', async () => {
    apiClientMock.post
      .mockResolvedValueOnce({ conflicts: [], total: 1 })
      .mockResolvedValueOnce({ items: [], total: 1, succeeded: 1, skipped: 0, failed: 0 });
    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await adapter.upload({ targetPath: '', files: [new File(['content'], 'README.md')] });

    const [, formData] = apiClientMock.post.mock.calls[1] as [string, FormData];
    expect(formData.get('targetPath')).toBe('/');
  });

  it('does not reuse a pre-upload root tree request when refreshing after upload', async () => {
    let resolveTreeBeforeUpload!: (value: { nodes: unknown[] }) => void;
    let resolveRefreshedTree!: (value: { nodes: unknown[] }) => void;
    const treeBeforeUpload = new Promise<{ nodes: unknown[] }>((resolve) => {
      resolveTreeBeforeUpload = resolve;
    });
    const refreshedTree = new Promise<{ nodes: unknown[] }>((resolve) => {
      resolveRefreshedTree = resolve;
    });
    apiClientMock.get
      .mockReturnValueOnce(treeBeforeUpload)
      .mockReturnValueOnce(refreshedTree);
    apiClientMock.post
      .mockResolvedValueOnce({ conflicts: [], total: 1 })
      .mockResolvedValueOnce({ items: [{ sourcePath: 'uploaded.md', finalPath: '/uploaded.md', status: 'created', size: 1, type: 'file', error: null }], total: 1, succeeded: 1, skipped: 0, failed: 0 });
    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-upload-refresh',
      runtimeBaseUrl: 'http://runtime.local',
    });

    const pendingTreeBeforeUpload = adapter.getTree();
    await adapter.upload({
      targetPath: '/',
      files: [new File(['content'], 'uploaded.md')],
    });
    const pendingRefreshedTree = adapter.getTree();
    const requestCountAfterUploadRefresh = apiClientMock.get.mock.calls.length;

    resolveTreeBeforeUpload({ nodes: [] });
    await pendingTreeBeforeUpload;

    const concurrentRefreshedTree = adapter.getTree();
    const requestCountWithConcurrentRefresh = apiClientMock.get.mock.calls.length;

    resolveRefreshedTree({
      nodes: [{
        id: '/uploaded.md',
        name: 'uploaded.md',
        path: '/uploaded.md',
        type: 'file',
      }],
    });
    await expect(pendingRefreshedTree).resolves.toEqual([
      {
        id: '/uploaded.md',
        name: 'uploaded.md',
        path: '/uploaded.md',
        type: 'file',
      },
    ]);
    await expect(concurrentRefreshedTree).resolves.toHaveLength(1);
    expect(requestCountAfterUploadRefresh).toBe(2);
    expect(requestCountWithConcurrentRefresh).toBe(2);
  });

  it('preserves version tokens when loading file content', async () => {
    apiClientMock.get.mockResolvedValueOnce({ content: 'Hello', revision: 'version-1' });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await expect(adapter.getContent('/README.md')).resolves.toEqual({
      content: 'Hello',
      revision: 'version-1',
    });

    expect(apiClientMock.get).toHaveBeenCalledWith('/files/content?path=%2FREADME.md');
  });

  it('normalizes content hashes through the shared parser', async () => {
    apiClientMock.get.mockResolvedValueOnce({ path: '/README.md', content: 'Hello', revision: 'hash-1' });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await expect(adapter.getContent('/README.md')).resolves.toEqual({
      content: 'Hello',
      revision: 'hash-1',
    });
  });

  it('sends expected version tokens on update and preserves response version tokens', async () => {
    apiClientMock.put.mockResolvedValueOnce({ success: true, revision: 'version-2' });

    const adapter = new WorkspaceFileTreeDataAdapter({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-auth',
    });

    await expect(
      adapter.update('/README.md', 'Updated', { revision: 'version-1' }),
    ).resolves.toEqual({
      success: true,
      revision: 'version-2',
      data: { revision: 'version-2' },
    });

    expect(apiClientMock.put).toHaveBeenCalledWith('/files/content?contextId=worktree%3Afeature-auth', {
      path: '/README.md',
      content: 'Updated',
      revision: 'version-1',
    });
  });
});
