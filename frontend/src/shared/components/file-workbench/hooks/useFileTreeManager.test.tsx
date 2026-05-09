import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFileTreeManager } from './useFileTreeManager';
import type { FileTreeDataAdapter, FileTreeNode } from '../types';

vi.mock('./useFileOperations', () => ({
  useFileOperations: () => ({
    createFile: vi.fn(),
    updateFile: vi.fn(),
    deleteFile: vi.fn(),
    batchDelete: vi.fn(),
    renameFile: vi.fn(),
    readFile: vi.fn(),
  }),
}));

vi.mock('./useFileEditor', () => ({
  useFileEditor: () => ({
    activeTab: null,
    tabs: [],
    isTabOpen: vi.fn(() => false),
    setActiveTab: vi.fn(),
    openTab: vi.fn(),
    saveTab: vi.fn(),
    saveAllTabs: vi.fn(),
    closeTab: vi.fn(),
    closeTabsForPath: vi.fn(),
    remapPath: vi.fn(),
  }),
}));

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

const createDeferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
};

const createAdapter = (
  getTree: FileTreeDataAdapter['getTree'],
  overrides: Partial<FileTreeDataAdapter> = {},
): FileTreeDataAdapter => ({
  getTree,
  getChildren: vi.fn().mockResolvedValue([]),
  getContent: vi.fn().mockResolvedValue(''),
  create: vi.fn().mockResolvedValue({ success: true }),
  update: vi.fn().mockResolvedValue({ success: true }),
  delete: vi.fn().mockResolvedValue({ success: true }),
  batchDelete: vi.fn().mockResolvedValue({
    success: true,
    deleted: [],
    failed: [],
    total: 0,
    successCount: 0,
    failedCount: 0,
  }),
  move: vi.fn().mockResolvedValue({ success: true }),
  upload: vi.fn().mockResolvedValue([]),
  download: vi.fn().mockResolvedValue(undefined),
  ...overrides,
});

describe('useFileTreeManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('ignores a stale tree response after the active workspace changes', async () => {
    const deferredByWorkspace = new Map<string, Deferred<FileTreeNode[]>>();

    const getTree = vi.fn((workspaceId: string) => {
      const key = workspaceId ?? 'unknown';
      let deferred = deferredByWorkspace.get(key);
      if (!deferred) {
        deferred = createDeferred<FileTreeNode[]>();
        deferredByWorkspace.set(key, deferred);
      }
      return deferred.promise;
    });

    const { result, rerender } = renderHook(
      ({ workspaceId }: { workspaceId: string }) =>
        useFileTreeManager({
          adapter: createAdapter(() => getTree(workspaceId)),
          adapterKey: `workspace:${workspaceId}`,
          autoLoad: false,
        }),
      {
        initialProps: { workspaceId: 'ws-a' },
      }
    );

    let loadWorkspaceA!: Promise<void>;
    await act(async () => {
      loadWorkspaceA = result.current.loadTree();
    });

    rerender({ workspaceId: 'ws-b' });

    let loadWorkspaceB!: Promise<void>;
    await act(async () => {
      loadWorkspaceB = result.current.loadTree();
    });

    await act(async () => {
      deferredByWorkspace.get('ws-b')?.resolve([
        { id: 'b', name: 'b', path: '/b', type: 'file' },
      ]);
      await loadWorkspaceB;
    });

    await waitFor(() => {
      expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/b']);
    });

    await act(async () => {
      deferredByWorkspace.get('ws-a')?.resolve([
        { id: 'a', name: 'a', path: '/a', type: 'file' },
      ]);
      await loadWorkspaceA;
    });

    await waitFor(() => {
      expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/b']);
    });
  });

  it('treats includeHidden as part of the active workspace tree identity', async () => {
    const deferredByVisibility = new Map<string, Deferred<FileTreeNode[]>>();

    const getTree = vi.fn((includeHidden: boolean) => {
      const key = includeHidden ? 'show-hidden' : 'hide-hidden';
      let deferred = deferredByVisibility.get(key);
      if (!deferred) {
        deferred = createDeferred<FileTreeNode[]>();
        deferredByVisibility.set(key, deferred);
      }
      return deferred.promise;
    });

    const { result, rerender } = renderHook(
      ({ includeHidden }: { includeHidden: boolean }) =>
        useFileTreeManager({
          adapter: createAdapter(() => getTree(includeHidden)),
          adapterKey: `workspace:ws-a:${includeHidden ? 'show-hidden' : 'hide-hidden'}`,
          autoLoad: false,
        }),
      {
        initialProps: { includeHidden: false },
      }
    );

    let loadHiddenOff!: Promise<void>;
    await act(async () => {
      loadHiddenOff = result.current.loadTree();
    });

    rerender({ includeHidden: true });

    let loadHiddenOn!: Promise<void>;
    await act(async () => {
      loadHiddenOn = result.current.loadTree();
    });

    await act(async () => {
      deferredByVisibility.get('show-hidden')?.resolve([
        { id: 'hidden', name: '.env', path: '/.env', type: 'file' },
      ]);
      await loadHiddenOn;
    });

    await waitFor(() => {
      expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/.env']);
    });

    await act(async () => {
      deferredByVisibility.get('hide-hidden')?.resolve([
        { id: 'visible', name: 'README.md', path: '/README.md', type: 'file' },
      ]);
      await loadHiddenOff;
    });

    await waitFor(() => {
      expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/.env']);
    });
  });

  it('does not auto-reload the tree on rerender when the logical api config is unchanged', async () => {
    const getTreeMock = vi.fn().mockResolvedValue([
      { id: 'root-readme', name: 'README.md', path: '/README.md', type: 'file' },
    ]);

    const { rerender } = renderHook(
      ({ knowledgeBaseId }: { knowledgeBaseId: string }) =>
        useFileTreeManager({
          adapter: createAdapter(getTreeMock),
          adapterKey: `knowledge-base:${knowledgeBaseId}:hide-hidden`,
          autoLoad: true,
        }),
      {
        initialProps: { knowledgeBaseId: 'kb-1' },
      }
    );

    await waitFor(() => {
      expect(getTreeMock).toHaveBeenCalledTimes(1);
    });

    rerender({ knowledgeBaseId: 'kb-1' });

    await waitFor(() => {
      expect(getTreeMock).toHaveBeenCalledTimes(1);
    });
  });

  it('persists expanded directory paths per adapter key', async () => {
    const adapterKey = 'workspace:ws-a:hide-hidden';
    const srcNode: FileTreeNode = {
      id: 'src',
      name: 'src',
      path: '/src',
      type: 'directory',
      hasChildren: false,
    };

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([srcNode])),
        adapterKey,
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.loadTree();
    });

    await act(async () => {
      await result.current.toggleDirectory(srcNode);
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(`fileTree.expandedPaths.v1:${encodeURIComponent(adapterKey)}`))
        .toBe(JSON.stringify(['/src']));
    });
  });

  it('restores persisted expanded directories and lazy-loads their children', async () => {
    const adapterKey = 'workspace:ws-a:hide-hidden';
    window.localStorage.setItem(
      `fileTree.expandedPaths.v1:${encodeURIComponent(adapterKey)}`,
      JSON.stringify(['/src']),
    );

    const getChildrenMock = vi.fn().mockResolvedValue([
      { id: 'src/index.ts', name: 'index.ts', path: '/src/index.ts', type: 'file' },
    ]);

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(
          vi.fn().mockResolvedValue([
            {
              id: 'src',
              name: 'src',
              path: '/src',
              type: 'directory',
              hasChildren: true,
            },
          ]),
          { getChildren: getChildrenMock },
        ),
        adapterKey,
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.loadTree();
    });

    await waitFor(() => {
      expect(getChildrenMock).toHaveBeenCalledWith('/src');
      expect(result.current.state.expandedIds.has('/src')).toBe(true);
      expect(result.current.state.nodes[0]?.children?.map((node) => node.path)).toEqual(['/src/index.ts']);
    });
  });
});
