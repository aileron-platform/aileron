import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useWorkspaceFileTreeAdapter } from './useWorkspaceFileTreeAdapter';

const {
  saveFileContentMock,
  sessionRefreshMock,
  managerLoadTreeMock,
  managerStateMock,
  managerResourceIdentitySnapshots,
} = vi.hoisted(() => ({
  saveFileContentMock: vi.fn().mockResolvedValue({ path: '/docs/guide.md' }),
  sessionRefreshMock: vi.fn().mockResolvedValue(undefined),
  managerLoadTreeMock: vi.fn().mockResolvedValue(undefined),
  managerResourceIdentitySnapshots: [] as Array<{
    kind: string;
    attributes: Record<string, unknown>;
  }>,
  managerStateMock: {
    nodes: [],
    expandedIds: new Set<string>(),
    selectedId: null,
    selectedIds: new Set<string>(),
    lastSelectedId: null,
    isLoading: false,
    error: null as string | null,
    setError: vi.fn(),
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

vi.mock('@/shared/components/file-workbench', () => ({
  createFileTreeResourceIdentity: (
    kind: string,
    attributes: Record<string, unknown>,
  ) => ({ kind, attributes }),
  serializeFileTreeResourceIdentity: (identity: {
    kind: string;
    attributes: Record<string, unknown>;
  }) => JSON.stringify(identity),
  useFileTreeManager: ({ resourceIdentity }: {
    resourceIdentity: { kind: string; attributes: Record<string, unknown> };
  }) => {
    managerResourceIdentitySnapshots.push(resourceIdentity);
    return {
    state: managerStateMock,
    loadTree: managerLoadTreeMock,
    };
  },
  findNodeByPath: vi.fn(),
}));

vi.mock('../../../api/workspaceRuntimeApi', () => ({
  buildArchiveDownloadUrl: vi.fn(),
  createFileOrFolder: vi.fn(),
  renameFile: vi.fn(),
  deleteFile: vi.fn(),
  batchDeleteFiles: vi.fn(),
  moveFile: vi.fn(),
  uploadFiles: vi.fn(),
  downloadFile: vi.fn(),
  fetchArchiveDownloadStatus: vi.fn(),
  startArchiveDownload: vi.fn(),
  fetchFileContent: vi.fn(),
  saveFileContent: saveFileContentMock,
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      refresh: sessionRefreshMock,
    }),
  };
});

describe('useWorkspaceFileTreeAdapter', () => {
  beforeEach(() => {
    saveFileContentMock.mockClear();
    saveFileContentMock.mockResolvedValue({ path: '/docs/guide.md' });
    sessionRefreshMock.mockClear();
    managerLoadTreeMock.mockClear();
    managerStateMock.setError.mockClear();
    managerResourceIdentitySnapshots.length = 0;
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

    expect(saveFileContentMock).toHaveBeenCalledWith('http://runtime', '/docs/guide.md', '# updated', 'worktree:feature-auth', undefined);
    expect(sessionRefreshMock).toHaveBeenCalledWith(
      queryClient,
      ['changes'],
    );
  });

  it('passes a new semantic resource identity when the workspace changes', async () => {
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

    expect(managerResourceIdentitySnapshots.at(-1)?.attributes.workspaceId).toBe('ws-a');

    rerender({
      workspaceId: 'ws-b',
      runtimeBaseUrl: 'http://runtime-b',
    });

    expect(managerResourceIdentitySnapshots.at(-1)?.attributes).toMatchObject({
      workspaceId: 'ws-b',
      runtimeBaseUrl: 'http://runtime-b',
    });
  });

  it('passes a new semantic resource identity when the git context changes', async () => {
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

    expect(managerResourceIdentitySnapshots.at(-1)?.attributes.contextId).toBe('primary');

    rerender({
      contextId: 'worktree:feature-auth',
    });

    expect(managerResourceIdentitySnapshots.at(-1)?.attributes.contextId)
      .toBe('worktree:feature-auth');
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
    expect(managerResourceIdentitySnapshots.at(-1)?.attributes.includeHidden).toBe(false);
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

    await act(async () => {
      await result.current.actions.toggleShowHiddenEntries();
    });

    expect(onShowHiddenEntriesChange).toHaveBeenCalledWith(true);

    rerender({ showHiddenEntries: true });

    expect(result.current.state.showHiddenEntries).toBe(true);
    expect(managerResourceIdentitySnapshots.at(-1)?.attributes.includeHidden).toBe(true);
    expect(managerLoadTreeMock).toHaveBeenCalledTimes(1);
  });
});
