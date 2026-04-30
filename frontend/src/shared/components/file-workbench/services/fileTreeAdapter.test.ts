import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileTreeApiAdapter } from './fileTreeAdapter';

const getMock = vi.fn();

vi.mock('@/shared/api/apiClient', () => {
  class MockApiClient {
    constructor(_options?: unknown) {}

    get(path: string) {
      return getMock(path);
    }
  }

  return {
    apiClient: new MockApiClient(),
    ApiClient: MockApiClient,
  };
});

describe('FileTreeApiAdapter', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('deduplicates identical in-flight workspace root tree requests', async () => {
    let resolveRequest!: (value: { nodes: Array<{ id: string; name: string; path: string; type: string }> }) => void;
    const requestPromise = new Promise<{ nodes: Array<{ id: string; name: string; path: string; type: string }> }>((resolve) => {
      resolveRequest = resolve;
    });
    getMock.mockReturnValue(requestPromise);

    const adapterA = new FileTreeApiAdapter({
      type: 'workspace',
      workspaceId: 'ws-1',
      baseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-a',
      includeHidden: false,
    });
    const adapterB = new FileTreeApiAdapter({
      type: 'workspace',
      workspaceId: 'ws-1',
      baseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-a',
      includeHidden: false,
    });

    const loadA = adapterA.getTree();
    const loadB = adapterB.getTree();

    expect(getMock).toHaveBeenCalledTimes(1);

    resolveRequest({
      nodes: [{ id: 'readme', name: 'README.md', path: '/README.md', type: 'file' }],
    });

    await expect(loadA).resolves.toEqual([
      { id: 'readme', name: 'README.md', path: '/README.md', type: 'file' },
    ]);
    await expect(loadB).resolves.toEqual([
      { id: 'readme', name: 'README.md', path: '/README.md', type: 'file' },
    ]);
  });

  it('creates a fresh request after the previous workspace root load settles', async () => {
    getMock
      .mockResolvedValueOnce({
        nodes: [{ id: 'first', name: 'README.md', path: '/README.md', type: 'file' }],
      })
      .mockResolvedValueOnce({
        nodes: [{ id: 'second', name: 'src', path: '/src', type: 'directory' }],
      });

    const adapter = new FileTreeApiAdapter({
      type: 'workspace',
      workspaceId: 'ws-1',
      baseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-a',
      includeHidden: false,
    });

    await adapter.getTree();
    await adapter.getTree();

    expect(getMock).toHaveBeenCalledTimes(2);
  });

  it('does not deduplicate distinct workspace tree identities', async () => {
    getMock.mockResolvedValue({ nodes: [] });

    const hiddenOff = new FileTreeApiAdapter({
      type: 'workspace',
      workspaceId: 'ws-1',
      baseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-a',
      includeHidden: false,
    });
    const hiddenOn = new FileTreeApiAdapter({
      type: 'workspace',
      workspaceId: 'ws-1',
      baseUrl: 'http://runtime.local',
      contextId: 'worktree:feature-a',
      includeHidden: true,
    });

    await Promise.all([hiddenOff.getTree(), hiddenOn.getTree()]);

    expect(getMock).toHaveBeenCalledTimes(2);
  });
});
