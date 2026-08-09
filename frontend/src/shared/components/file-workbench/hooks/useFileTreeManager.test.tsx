import React from 'react';
import { act, render, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFileTreeManager } from './useFileTreeManager';
import type { UseFileEditorOptions } from './useFileEditor';
import {
  createFileTreeResourceIdentity,
  serializeFileTreeResourceIdentity,
} from '../model/fileTreeAsyncCoordinator';
import type { FileOperationResponse, FileTab, FileTreeDataAdapter, FileTreeNode } from '../types';

const testResourceIdentity = (key: string) => (
  createFileTreeResourceIdentity('test-resource', { key })
);

const mocks = vi.hoisted(() => {
  const operations = {
    createFile: vi.fn(),
    updateFile: vi.fn(),
    deleteFile: vi.fn(),
    batchDelete: vi.fn(),
    renameFile: vi.fn(),
    readFile: vi.fn(),
  };

  const editor = {
    activeTab: null as FileTab | null,
    tabs: [] as FileTab[],
    isTabOpen: vi.fn(() => false),
    setActiveTab: vi.fn(),
    openTab: vi.fn(),
    saveTab: vi.fn(),
    saveAllTabs: vi.fn(),
    closeTab: vi.fn(),
    closeAllTabs: vi.fn(),
    closeTabsForPath: vi.fn(),
    remapPath: vi.fn(),
  };

  let editorOptions: UseFileEditorOptions | undefined;

  return {
    operations,
    editor,
    getEditorOptions: () => editorOptions,
    setEditorOptions: (options: UseFileEditorOptions) => {
      editorOptions = options;
    },
  };
});

vi.mock('./useFileOperations', () => ({
  useFileOperations: () => mocks.operations,
}));

vi.mock('./useFileEditor', () => ({
  useFileEditor: (options: UseFileEditorOptions) => {
    mocks.setEditorOptions(options);
    return mocks.editor;
  },
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
    mocks.editor.activeTab = null;
    mocks.editor.tabs = [];
    mocks.editor.isTabOpen.mockReturnValue(false);
    mocks.operations.createFile.mockResolvedValue({ success: true });
    mocks.operations.updateFile.mockResolvedValue({ success: true });
    mocks.operations.deleteFile.mockResolvedValue({ success: true });
    mocks.operations.batchDelete.mockResolvedValue({
      success: true,
      deleted: [],
      failed: [],
      total: 0,
      successCount: 0,
      failedCount: 0,
    });
    mocks.operations.renameFile.mockResolvedValue({ success: true });
    mocks.operations.readFile.mockResolvedValue({ content: '' });
    mocks.setEditorOptions({});
    window.localStorage.clear();
  });

  it('does not reload the tree when callback props change identity', async () => {
    const getTree = vi.fn().mockResolvedValue([
      { id: '/src', name: 'src', path: '/src', type: 'directory' },
    ]);

    const { rerender } = renderHook(
      ({ callbackToken }: { callbackToken: number }) =>
        useFileTreeManager({
          adapter: createAdapter(getTree),
          resourceIdentity: testResourceIdentity('workspace:ws-a'),
          autoLoad: true,
          onError: () => {
            void callbackToken;
          },
          onTreeLoaded: () => {
            void callbackToken;
          },
        }),
      {
        initialProps: { callbackToken: 1 },
      },
    );

    await waitFor(() => {
      expect(getTree).toHaveBeenCalledTimes(1);
    });

    rerender({ callbackToken: 2 });

    await act(async () => {
      await new Promise(resolve => globalThis.setTimeout(resolve, 0));
    });

    expect(getTree).toHaveBeenCalledTimes(1);
  });

  it('applies the tree when a child effect loads on the initial resource identity', async () => {
    // Real callers with autoLoad:false (e.g. KnowledgeBaseFilesTab) trigger the initial
    // loadTree() from a *child* component's mount effect (FileManagementSidebarWorkflow).
    // React fires child effects before parent effects in the same commit, so that
    // loadTree() starts before this hook's own passive effects run. The initial
    // semantic identity must not supersede that in-flight load.
    const getTree = vi.fn().mockResolvedValue([
      { id: '/README.md', name: 'README.md', path: '/README.md', type: 'file' },
    ]);

    let latestManager: ReturnType<typeof useFileTreeManager> | undefined;

    const ChildTriggersLoad: React.FC<{ loadTree: () => Promise<void> }> = ({ loadTree }) => {
      React.useEffect(() => {
        void loadTree();
      }, [loadTree]);
      return null;
    };

    const Harness: React.FC = () => {
      const manager = useFileTreeManager({
        adapter: createAdapter(getTree),
        resourceIdentity: testResourceIdentity('knowledge-base:kb-1:visible'),
        autoLoad: false,
      });
      latestManager = manager;
      return <ChildTriggersLoad loadTree={manager.loadTree} />;
    };

    await act(async () => {
      render(<Harness />);
    });

    await waitFor(() => {
      expect(latestManager?.state.nodes.map((node) => node.path)).toEqual(['/README.md']);
    });
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
          resourceIdentity: testResourceIdentity(`workspace:${workspaceId}`),
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

  it('keeps the committed identity active when another render is abandoned', async () => {
    const workspaceA = createDeferred<FileTreeNode[]>();
    const suspended = new Promise<never>(() => undefined);
    let committedManager: ReturnType<typeof useFileTreeManager> | undefined;

    const CaptureCommittedManager: React.FC<{
      manager: ReturnType<typeof useFileTreeManager>;
    }> = ({ manager }) => {
      React.useLayoutEffect(() => {
        committedManager = manager;
      }, [manager]);
      return null;
    };

    const Harness: React.FC<{
      shouldSuspend: boolean;
      workspaceId: string;
    }> = ({ shouldSuspend, workspaceId }) => {
      const manager = useFileTreeManager({
        adapter: createAdapter(() => (
          workspaceId === 'ws-a' ? workspaceA.promise : Promise.resolve([])
        )),
        resourceIdentity: testResourceIdentity(`workspace:${workspaceId}`),
        autoLoad: false,
      });
      if (shouldSuspend) {
        throw suspended;
      }
      return <CaptureCommittedManager manager={manager} />;
    };

    const view = render(
      <React.Suspense fallback={null}>
        <Harness workspaceId="ws-a" shouldSuspend={false} />
      </React.Suspense>,
    );

    let loadWorkspaceA!: Promise<void>;
    await act(async () => {
      loadWorkspaceA = committedManager!.loadTree();
    });

    view.rerender(
      <React.Suspense fallback={null}>
        <Harness workspaceId="ws-b" shouldSuspend />
      </React.Suspense>,
    );
    view.rerender(
      <React.Suspense fallback={null}>
        <Harness workspaceId="ws-a" shouldSuspend={false} />
      </React.Suspense>,
    );

    await act(async () => {
      workspaceA.resolve([
        { id: 'a', name: 'a', path: '/a', type: 'file' },
      ]);
      await loadWorkspaceA;
    });

    expect(committedManager?.state.nodes.map((node) => node.path)).toEqual(['/a']);
  });

  it('only applies the latest tree load within the same resource identity', async () => {
    const requests: Array<Deferred<FileTreeNode[]>> = [];
    const getTree = vi.fn(() => {
      const deferred = createDeferred<FileTreeNode[]>();
      requests.push(deferred);
      return deferred.promise;
    });
    const resourceIdentity = testResourceIdentity('workspace:ws-a');
    const { result } = renderHook(() => useFileTreeManager({
      adapter: createAdapter(getTree),
      resourceIdentity,
      autoLoad: false,
    }));

    let previousLoad!: Promise<void>;
    let latestLoad!: Promise<void>;
    await act(async () => {
      previousLoad = result.current.loadTree();
      latestLoad = result.current.loadTree();
    });

    await act(async () => {
      requests[1]?.resolve([
        { id: 'latest', name: 'latest', path: '/latest', type: 'file' },
      ]);
      await latestLoad;
    });
    expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/latest']);
    expect(result.current.state.isLoading).toBe(true);

    await act(async () => {
      requests[0]?.resolve([
        { id: 'previous', name: 'previous', path: '/previous', type: 'file' },
      ]);
      await previousLoad;
    });

    expect(result.current.state.nodes.map((node) => node.path)).toEqual(['/latest']);
    expect(result.current.state.isLoading).toBe(false);
  });

  it('clears the previous identity and applies the load started by a child effect', async () => {
    const deferredByWorkspace = new Map<string, Deferred<FileTreeNode[]>>();
    const getTree = vi.fn((workspaceId: string) => {
      let deferred = deferredByWorkspace.get(workspaceId);
      if (!deferred) {
        deferred = createDeferred<FileTreeNode[]>();
        deferredByWorkspace.set(workspaceId, deferred);
      }
      return deferred.promise;
    });
    let latestManager: ReturnType<typeof useFileTreeManager> | undefined;

    const ChildTriggersLoad: React.FC<{ loadTree: () => Promise<void> }> = ({ loadTree }) => {
      React.useEffect(() => {
        void loadTree();
      }, [loadTree]);
      return null;
    };

    const Harness: React.FC<{ workspaceId: string }> = ({ workspaceId }) => {
      const manager = useFileTreeManager({
        adapter: createAdapter(() => getTree(workspaceId)),
        resourceIdentity: testResourceIdentity(`workspace:${workspaceId}`),
        autoLoad: false,
      });
      latestManager = manager;
      return <ChildTriggersLoad loadTree={manager.loadTree} />;
    };

    const { rerender } = render(<Harness workspaceId="ws-a" />);

    await act(async () => {
      deferredByWorkspace.get('ws-a')?.resolve([
        { id: 'a', name: 'a', path: '/a', type: 'file' },
      ]);
    });
    await waitFor(() => {
      expect(latestManager?.state.nodes.map((node) => node.path)).toEqual(['/a']);
    });

    act(() => {
      latestManager?.state.selectNode('/a');
      latestManager?.state.setSearchQuery('a');
      latestManager?.state.openContextMenu(
        10,
        20,
        { id: 'a', name: 'a', path: '/a', type: 'file' },
      );
    });

    rerender(<Harness workspaceId="ws-b" />);

    expect(latestManager?.state.nodes).toEqual([]);
    expect(latestManager?.state.selectedId).toBeNull();
    expect(latestManager?.state.searchQuery).toBe('');
    expect(latestManager?.state.contextMenu).toBeNull();
    expect(mocks.editor.closeAllTabs).toHaveBeenCalledTimes(1);
    expect(getTree).toHaveBeenCalledWith('ws-b');

    await act(async () => {
      deferredByWorkspace.get('ws-b')?.resolve([
        { id: 'b', name: 'b', path: '/b', type: 'file' },
      ]);
    });
    await waitFor(() => {
      expect(latestManager?.state.nodes.map((node) => node.path)).toEqual(['/b']);
    });
  });

  it('clears loading even when the last settled request was superseded', async () => {
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
          resourceIdentity: testResourceIdentity(`workspace:${workspaceId}`),
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

    expect(result.current.state.isLoading).toBe(true);

    // Changing the semantic resource identity invalidates the in-flight ws-a load
    // without requiring a replacement request.
    rerender({ workspaceId: 'ws-b' });

    await act(async () => {
      deferredByWorkspace.get('ws-a')?.resolve([
        { id: 'a', name: 'a', path: '/a', type: 'file' },
      ]);
      await loadWorkspaceA;
    });

    // The stale response must not be applied, but loading must still be cleared.
    await waitFor(() => {
      expect(result.current.state.isLoading).toBe(false);
    });
    expect(result.current.state.nodes).toEqual([]);
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
          resourceIdentity: testResourceIdentity(
            `workspace:ws-a:${includeHidden ? 'show-hidden' : 'hide-hidden'}`,
          ),
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
          resourceIdentity: testResourceIdentity(`knowledge-base:${knowledgeBaseId}:hide-hidden`),
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

  it('persists expanded directory paths per resource identity', async () => {
    const resourceIdentity = testResourceIdentity('workspace:ws-a:hide-hidden');
    const identityKey = serializeFileTreeResourceIdentity(resourceIdentity);
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
        resourceIdentity,
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
      expect(window.localStorage.getItem(`fileTree.expandedPaths.v1:${encodeURIComponent(identityKey)}`))
        .toBe(JSON.stringify(['/src']));
    });
  });

  it('restores persisted expanded directories and lazy-loads their children', async () => {
    const resourceIdentity = testResourceIdentity('workspace:ws-a:hide-hidden');
    const identityKey = serializeFileTreeResourceIdentity(resourceIdentity);
    window.localStorage.setItem(
      `fileTree.expandedPaths.v1:${encodeURIComponent(identityKey)}`,
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
        resourceIdentity,
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

  it('re-fetches children for depth-truncated expanded directories on initial load', async () => {
    const resourceIdentity = testResourceIdentity('workspace:ws-a:hide-hidden');
    const identityKey = serializeFileTreeResourceIdentity(resourceIdentity);
    window.localStorage.setItem(
      `fileTree.expandedPaths.v1:${encodeURIComponent(identityKey)}`,
      JSON.stringify(['/src', '/src/lib', '/src/lib/inner']),
    );

    // Simulates the backend response when getTree(maxDepth=2) hits a deeply
    // nested directory: children is [] but hasChildren is true.
    const truncatedTree: FileTreeNode[] = [
      {
        id: '/src',
        name: 'src',
        path: '/src',
        type: 'directory',
        hasChildren: true,
        children: [
          {
            id: '/src/lib',
            name: 'lib',
            path: '/src/lib',
            type: 'directory',
            hasChildren: true,
            children: [
              {
                id: '/src/lib/inner',
                name: 'inner',
                path: '/src/lib/inner',
                type: 'directory',
                hasChildren: true,
                children: [], // depth-truncated by maxDepth boundary
              },
            ],
          },
        ],
      },
    ];

    const getChildrenMock = vi.fn(async (path: string): Promise<FileTreeNode[]> => {
      if (path === '/src/lib/inner') {
        return [
          {
            id: '/src/lib/inner/deep.ts',
            name: 'deep.ts',
            path: '/src/lib/inner/deep.ts',
            type: 'file',
          },
        ];
      }
      return [];
    });

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(
          vi.fn().mockResolvedValue(truncatedTree),
          { getChildren: getChildrenMock },
        ),
        resourceIdentity,
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.loadTree();
    });

    await waitFor(() => {
      expect(getChildrenMock).toHaveBeenCalledWith('/src/lib/inner');
      expect(getChildrenMock).toHaveBeenCalledTimes(1);
      expect(result.current.state.expandedIds.has('/src/lib/inner')).toBe(true);
    });

    const innerNode = result.current.state.nodes[0]?.children?.[0]?.children?.[0];
    expect(innerNode?.path).toBe('/src/lib/inner');
    expect(innerNode?.children?.map((node) => node.path)).toEqual([
      '/src/lib/inner/deep.ts',
    ]);
  });

  it('keeps deeply nested expansion across a refresh that re-serves a truncated tree', async () => {
    const resourceIdentity = testResourceIdentity('workspace:ws-a:hide-hidden');

    // Two calls: first an "initial" tree with real children at depth 3,
    // then a "refreshed" tree where the depth-3 directory is back to the
    // truncated form (children=[], hasChildren=true) - exactly how
    // getTree(maxDepth=2) would respond after a file inside is deleted.
    const initialTree: FileTreeNode[] = [
      {
        id: '/src',
        name: 'src',
        path: '/src',
        type: 'directory',
        hasChildren: true,
        children: [
          {
            id: '/src/lib',
            name: 'lib',
            path: '/src/lib',
            type: 'directory',
            hasChildren: true,
            children: [
              {
                id: '/src/lib/inner',
                name: 'inner',
                path: '/src/lib/inner',
                type: 'directory',
                hasChildren: true,
                children: [
                  {
                    id: '/src/lib/inner/old.ts',
                    name: 'old.ts',
                    path: '/src/lib/inner/old.ts',
                    type: 'file',
                  },
                ],
              },
            ],
          },
        ],
      },
    ];

    const refreshedTree: FileTreeNode[] = [
      {
        id: '/src',
        name: 'src',
        path: '/src',
        type: 'directory',
        hasChildren: true,
        children: [
          {
            id: '/src/lib',
            name: 'lib',
            path: '/src/lib',
            type: 'directory',
            hasChildren: true,
            children: [
              {
                id: '/src/lib/inner',
                name: 'inner',
                path: '/src/lib/inner',
                type: 'directory',
                hasChildren: true,
                children: [], // depth-truncated again on refresh
              },
            ],
          },
        ],
      },
    ];

    const getTreeMock = vi
      .fn<() => Promise<FileTreeNode[]>>()
      .mockResolvedValueOnce(initialTree)
      .mockResolvedValueOnce(refreshedTree);

    const getChildrenMock = vi.fn(async (path: string): Promise<FileTreeNode[]> => {
      if (path === '/src/lib/inner') {
        return [
          {
            id: '/src/lib/inner/new.ts',
            name: 'new.ts',
            path: '/src/lib/inner/new.ts',
            type: 'file',
          },
        ];
      }
      return [];
    });

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(getTreeMock, { getChildren: getChildrenMock }),
        resourceIdentity,
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.loadTree();
    });

    const innerNode = result.current.state.nodes[0]?.children?.[0]?.children?.[0];
    expect(innerNode?.path).toBe('/src/lib/inner');

    await act(async () => {
      await result.current.toggleDirectory(innerNode!);
    });

    expect(result.current.state.expandedIds.has('/src/lib/inner')).toBe(true);

    // Simulate a refresh, e.g. triggered by deleting a file in the workspace.
    getChildrenMock.mockClear();
    await act(async () => {
      await result.current.loadTree();
    });

    expect(result.current.state.expandedIds.has('/src/lib/inner')).toBe(true);
    expect(getChildrenMock).toHaveBeenCalledWith('/src/lib/inner');
    expect(getChildrenMock).toHaveBeenCalledTimes(1);

    const refreshedInner = result.current.state.nodes[0]?.children?.[0]?.children?.[0];
    expect(refreshedInner?.path).toBe('/src/lib/inner');
    expect(refreshedInner?.children?.map((node) => node.path)).toEqual([
      '/src/lib/inner/new.ts',
    ]);
  });

  it('closes deleted tabs only after a successful delete and refreshes the authoritative tree', async () => {
    const getTreeMock = vi
      .fn<() => Promise<FileTreeNode[]>>()
      .mockResolvedValueOnce([
        { id: '/old.md', name: 'old.md', path: '/old.md', type: 'file' },
      ])
      .mockResolvedValueOnce([]);
    const { result } = renderHook(() => useFileTreeManager({
      adapter: createAdapter(getTreeMock),
      resourceIdentity: testResourceIdentity('workspace:delete'),
      autoLoad: false,
    }));

    await act(async () => {
      await result.current.loadTree();
    });
    await act(async () => {
      await result.current.deleteFileAndCloseTab('/old.md');
    });

    expect(mocks.editor.closeTabsForPath).toHaveBeenCalledWith('/old.md', false);
    expect(getTreeMock).toHaveBeenCalledTimes(2);
    expect(result.current.state.nodes).toEqual([]);
  });

  it('settles only successful paths after a partially successful batch delete', async () => {
    const getTreeMock = vi
      .fn<() => Promise<FileTreeNode[]>>()
      .mockResolvedValueOnce([
        { id: '/deleted.md', name: 'deleted.md', path: '/deleted.md', type: 'file' },
        { id: '/failed.md', name: 'failed.md', path: '/failed.md', type: 'file' },
      ])
      .mockResolvedValueOnce([
        { id: '/failed.md', name: 'failed.md', path: '/failed.md', type: 'file' },
      ]);
    mocks.operations.batchDelete.mockResolvedValue({
      success: false,
      deleted: ['/deleted.md'],
      failed: [{ path: '/failed.md', error: 'Permission denied' }],
      total: 2,
      successCount: 1,
      failedCount: 1,
    });
    const { result } = renderHook(() => useFileTreeManager({
      adapter: createAdapter(getTreeMock),
      resourceIdentity: testResourceIdentity('workspace:batch-delete'),
      autoLoad: false,
    }));

    await act(async () => {
      await result.current.loadTree();
    });
    await act(async () => {
      await result.current.batchDeleteAndCloseTabs(['/deleted.md', '/failed.md']);
    });

    expect(mocks.editor.closeTabsForPath).toHaveBeenCalledTimes(1);
    expect(mocks.editor.closeTabsForPath).toHaveBeenCalledWith('/deleted.md', false);
    expect(mocks.editor.closeTabsForPath).not.toHaveBeenCalledWith('/failed.md', false);
    expect(getTreeMock).toHaveBeenCalledTimes(2);
    expect(result.current.state.flatNodes.map(node => node.path)).toEqual(['/failed.md']);
  });

  it('opens selected files with their content version id', async () => {
    const fileNode: FileTreeNode = {
      id: '/README.md',
      name: 'README.md',
      path: '/README.md',
      type: 'file',
    };
    mocks.operations.readFile.mockResolvedValue({
      content: 'current content',
      revision: 'version-1',
    });

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('workspace:ws-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.handleFileSelect(fileNode);
    });

    expect(mocks.operations.readFile).toHaveBeenCalledWith('/README.md');
    expect(mocks.editor.openTab).toHaveBeenCalledWith(fileNode, 'current content', 'version-1');
  });

  it('opens binary files with unreadable metadata instead of reporting a path error', async () => {
    const fileNode: FileTreeNode = {
      id: '/cube-web-design-style (1).zip',
      name: 'cube-web-design-style (1).zip',
      path: '/cube-web-design-style (1).zip',
      type: 'file',
    };
    mocks.operations.readFile.mockResolvedValue({
      content: '',
      revision: 'version-zip',
      readable: false,
      unreadableReason: 'binary',
    });

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('knowledge-base:kb-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.handleFileSelect(fileNode);
    });

    expect(mocks.editor.openTab).toHaveBeenCalledWith(
      fileNode,
      '',
      'version-zip',
      { readable: false, unreadableReason: 'binary' },
    );
  });

  it('opens image files without reading them through the text content API', async () => {
    const fileNode: FileTreeNode = {
      id: '/IMG_7754.jpg',
      name: 'IMG_7754.jpg',
      path: '/IMG_7754.jpg',
      type: 'file',
    };

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('knowledge-base:kb-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.handleFileSelect(fileNode);
    });

    expect(mocks.operations.readFile).not.toHaveBeenCalled();
    expect(mocks.editor.openTab).toHaveBeenCalledWith(fileNode, '', undefined);
  });

  it('saves the active tab with its expected version id and records the returned version id', async () => {
    const activeTab = createTab('/README.md', {
      content: 'draft',
      originalContent: 'base',
      isModified: true,
      revision: 'version-1',
    });
    mocks.editor.activeTab = activeTab;
    mocks.operations.updateFile.mockResolvedValue({
      success: true,
      data: { revision: 'version-2' },
    } satisfies FileOperationResponse);

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('workspace:ws-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.saveActiveTab();
    });

    expect(mocks.operations.updateFile).toHaveBeenCalledWith('/README.md', 'draft', {
      revision: 'version-1',
    });
    expect(mocks.editor.saveTab).toHaveBeenCalledWith('/README.md', 'draft', 'version-2');
  });

  it('uses the captured active tab content when a save resolves after later edits', async () => {
    const activeTab = createTab('/README.md', {
      content: 'draft sent to server',
      originalContent: 'base',
      isModified: true,
      revision: 'version-1',
    });
    const deferred = createDeferred<FileOperationResponse>();
    mocks.editor.activeTab = activeTab;
    mocks.operations.updateFile.mockReturnValue(deferred.promise);

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('workspace:ws-a'),
        autoLoad: false,
      })
    );

    let savePromise!: Promise<void>;
    act(() => {
      savePromise = result.current.saveActiveTab();
    });

    mocks.editor.activeTab = {
      ...activeTab,
      content: 'newer draft',
    };

    await act(async () => {
      deferred.resolve({
        success: true,
        data: { revision: 'version-2' },
      });
      await savePromise;
    });

    expect(mocks.operations.updateFile).toHaveBeenCalledWith('/README.md', 'draft sent to server', {
      revision: 'version-1',
    });
    expect(mocks.editor.saveTab).toHaveBeenCalledWith(
      '/README.md',
      'draft sent to server',
      'version-2',
    );
  });

  it('keeps failed tabs dirty when saving all modified tabs', async () => {
    const successTab = createTab('/success.md', {
      content: 'success draft',
      originalContent: 'success base',
      isModified: true,
      revision: 'success-v1',
    });
    const failedTab = createTab('/failed.md', {
      content: 'failed draft',
      originalContent: 'failed base',
      isModified: true,
      revision: 'failed-v1',
    });
    mocks.editor.tabs = [successTab, failedTab];
    mocks.operations.updateFile
      .mockResolvedValueOnce({
        success: true,
        data: { revision: 'success-v2' },
      } satisfies FileOperationResponse)
      .mockRejectedValueOnce(new Error('conflict'));

    const { result } = renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('workspace:ws-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await result.current.saveAllTabs();
    });

    expect(mocks.operations.updateFile).toHaveBeenNthCalledWith(1, '/success.md', 'success draft', {
      revision: 'success-v1',
    });
    expect(mocks.operations.updateFile).toHaveBeenNthCalledWith(2, '/failed.md', 'failed draft', {
      revision: 'failed-v1',
    });
    expect(mocks.editor.saveTab).toHaveBeenCalledTimes(1);
    expect(mocks.editor.saveTab).toHaveBeenCalledWith('/success.md', 'success draft', 'success-v2');
    expect(mocks.editor.saveAllTabs).not.toHaveBeenCalled();
  });

  it('auto-saves with the captured expected version id and records the returned version id', async () => {
    mocks.operations.updateFile.mockResolvedValue({
      success: true,
      data: { revision: 'version-2' },
    } satisfies FileOperationResponse);

    renderHook(() =>
      useFileTreeManager({
        adapter: createAdapter(vi.fn().mockResolvedValue([])),
        resourceIdentity: testResourceIdentity('workspace:ws-a'),
        autoLoad: false,
      })
    );

    await act(async () => {
      await mocks.getEditorOptions()?.onAutoSave?.('/README.md', 'draft sent to server', 'version-1');
    });

    expect(mocks.operations.updateFile).toHaveBeenCalledWith('/README.md', 'draft sent to server', {
      revision: 'version-1',
    });
    expect(mocks.editor.saveTab).toHaveBeenCalledWith(
      '/README.md',
      'draft sent to server',
      'version-2',
      { clearAutoSaveTimer: false },
    );
  });
});

const createTab = (path: string, overrides: Partial<FileTab> = {}): FileTab => ({
  path,
  name: path.split('/').pop() || path,
  content: 'content',
  originalContent: 'content',
  isModified: false,
  node: {
    id: path,
    path,
    name: path.split('/').pop() || path,
    type: 'file',
  },
  ...overrides,
});
