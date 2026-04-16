import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspaceFileTreeAdapter } from './useWorkspaceFileTreeAdapter';

const {
  saveFileContentMock,
  refreshVersionControlQueriesMock,
  managerLoadTreeMock,
  managerStateMock,
  managerResetStateMock,
  managerApiConfigSnapshots,
} = vi.hoisted(() => ({
  saveFileContentMock: vi.fn().mockResolvedValue({ path: '/docs/guide.md' }),
  refreshVersionControlQueriesMock: vi.fn().mockResolvedValue(undefined),
  managerLoadTreeMock: vi.fn().mockResolvedValue(undefined),
  managerResetStateMock: vi.fn(),
  managerApiConfigSnapshots: [] as Array<Record<string, unknown>>,
  managerStateMock: {
    nodes: [],
    expandedIds: new Set<string>(),
    selectedId: null,
    selectedIds: new Set<string>(),
    lastSelectedId: null,
    isLoading: false,
    error: null as string | null,
    setError: vi.fn(),
    resetState: vi.fn(),
    selectNode: vi.fn(),
    selectNodeWithModifier: vi.fn(),
    clearSelection: vi.fn(),
    expandNode: vi.fn(),
    collapseNode: vi.fn(),
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/file-tree-manager/hooks/useFileTreeManager', () => ({
  useFileTreeManager: ({ apiConfig }: { apiConfig: Record<string, unknown> }) => {
    managerApiConfigSnapshots.push(apiConfig);
    return {
    state: managerStateMock,
    loadTree: managerLoadTreeMock,
    };
  },
}));

vi.mock('../services/workspaceRuntimeApi', () => ({
  buildRuntimeUrl: vi.fn(),
  createFileOrFolder: vi.fn(),
  renameFile: vi.fn(),
  deleteFile: vi.fn(),
  batchDeleteFiles: vi.fn(),
  duplicateFile: vi.fn(),
  moveFile: vi.fn(),
  uploadFiles: vi.fn(),
  downloadFile: vi.fn(),
  batchDownloadFiles: vi.fn(),
  fetchFileContent: vi.fn(),
  saveFileContent: saveFileContentMock,
}));

vi.mock('../features/version-control/lib/queryClient', async () => {
  const actual = await vi.importActual<typeof import('../features/version-control/lib/queryClient')>(
    '../features/version-control/lib/queryClient',
  );
  return {
    ...actual,
    refreshVersionControlQueries: refreshVersionControlQueriesMock,
  };
});

describe('useWorkspaceFileTreeAdapter', () => {
  beforeEach(() => {
    saveFileContentMock.mockClear();
    saveFileContentMock.mockResolvedValue({ path: '/docs/guide.md' });
    refreshVersionControlQueriesMock.mockClear();
    managerLoadTreeMock.mockClear();
    managerStateMock.setError.mockClear();
    managerResetStateMock.mockClear();
    managerStateMock.resetState = managerResetStateMock;
    managerApiConfigSnapshots.length = 0;
  });

  it('refreshes version-control queries after saving a file successfully', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useWorkspaceFileTreeAdapter({
        workspaceId: 'ws-save',
        runtimeBaseUrl: 'http://runtime',
        contextId: 'worktree:feature-auth',
        showHiddenEntries: false,
      }),
      { wrapper },
    );

    await act(async () => {
      await result.current.actions.saveFileContent('/docs/guide.md', '# updated');
    });

    expect(saveFileContentMock).toHaveBeenCalledWith('http://runtime', '/docs/guide.md', '# updated', 'worktree:feature-auth');
    expect(refreshVersionControlQueriesMock).toHaveBeenCalledWith(
      queryClient,
      'ws-save',
      { contextId: 'worktree:feature-auth' },
    );
  });

  it('resets workspace-scoped tree state when the workspace identity changes', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { rerender } = renderHook(
      ({ workspaceId, runtimeBaseUrl }: { workspaceId: string; runtimeBaseUrl: string }) =>
        useWorkspaceFileTreeAdapter({ workspaceId, runtimeBaseUrl, showHiddenEntries: false }),
        
      {
        wrapper,
        initialProps: {
          workspaceId: 'ws-a',
          runtimeBaseUrl: 'http://runtime-a',
        },
      }
    );

    expect(managerResetStateMock).not.toHaveBeenCalled();

    rerender({
      workspaceId: 'ws-b',
      runtimeBaseUrl: 'http://runtime-b',
    });

    expect(managerResetStateMock).toHaveBeenCalledTimes(1);
  });

  it('resets workspace-scoped tree state when the git context changes', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { rerender } = renderHook(
      ({ contextId }: { contextId: string | null }) =>
        useWorkspaceFileTreeAdapter({
          workspaceId: 'ws-a',
          runtimeBaseUrl: 'http://runtime-a',
          contextId,
          showHiddenEntries: false,
        }),
      {
        wrapper,
        initialProps: {
          contextId: 'primary',
        },
      }
    );

    expect(managerResetStateMock).not.toHaveBeenCalled();

    rerender({
      contextId: 'worktree:feature-auth',
    });

    expect(managerResetStateMock).toHaveBeenCalledTimes(1);
  });

  it('defaults workspace tree loads to hiding hidden entries', () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useWorkspaceFileTreeAdapter({
        workspaceId: 'ws-a',
        runtimeBaseUrl: 'http://runtime-a',
        showHiddenEntries: false,
      }),
      { wrapper }
    );

    expect(result.current.state.showHiddenEntries).toBe(false);
    expect(managerApiConfigSnapshots.at(-1)?.includeHidden).toBe(false);
  });

  it('toggles hidden entry visibility and reloads the tree with includeHidden enabled', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const onShowHiddenEntriesChange = vi.fn();

    const { result, rerender } = renderHook(
      ({ showHiddenEntries }: { showHiddenEntries: boolean }) =>
        useWorkspaceFileTreeAdapter({
          workspaceId: 'ws-a',
          runtimeBaseUrl: 'http://runtime-a',
          showHiddenEntries,
          onShowHiddenEntriesChange,
        }),
      {
        wrapper,
        initialProps: {
          showHiddenEntries: false,
        },
      }
    );

    managerLoadTreeMock.mockClear();
    managerResetStateMock.mockClear();

    await act(async () => {
      await result.current.actions.toggleShowHiddenEntries();
    });

    expect(onShowHiddenEntriesChange).toHaveBeenCalledWith(true);

    rerender({ showHiddenEntries: true });

    expect(result.current.state.showHiddenEntries).toBe(true);
    expect(managerApiConfigSnapshots.at(-1)?.includeHidden).toBe(true);
    expect(managerResetStateMock).toHaveBeenCalledTimes(1);
    expect(managerLoadTreeMock).toHaveBeenCalledTimes(1);
  });
});
