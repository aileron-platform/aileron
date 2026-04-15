import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFileTreeManager } from './useFileTreeManager';
import type { FileTreeNode } from '../types';

const { getTreeMock } = vi.hoisted(() => ({
  getTreeMock: vi.fn(),
}));

vi.mock('../services/fileTreeAdapter', () => ({
  FileTreeApiAdapter: class {
    private readonly apiConfig: { workspaceId?: string };

    constructor(apiConfig: { workspaceId?: string }) {
      this.apiConfig = apiConfig;
    }

    getTree() {
      return getTreeMock(this.apiConfig);
    }
  },
}));

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

describe('useFileTreeManager', () => {
  beforeEach(() => {
    getTreeMock.mockReset();
  });

  it('ignores a stale tree response after the active workspace changes', async () => {
    const deferredByWorkspace = new Map<string, Deferred<FileTreeNode[]>>();

    getTreeMock.mockImplementation(({ workspaceId }: { workspaceId?: string }) => {
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
          apiConfig: {
            type: 'workspace',
            workspaceId,
            baseUrl: 'http://runtime',
          },
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
});
