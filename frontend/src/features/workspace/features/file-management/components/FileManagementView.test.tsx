import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { render } from '@/__tests__/utils/render';
import { FileManagementView } from './FileManagementView';

const {
  useWorkspaceMock,
  useFileTreeManagerMock,
  useFileOperationsWithDialogMock,
  fetchArchiveDownloadStatusMock,
  downloadArchiveBlobMock,
  startArchiveDownloadMock,
  useFileTreeContextMenuMock,
  queryClientMock,
} = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  useFileTreeManagerMock: vi.fn(),
  useFileOperationsWithDialogMock: vi.fn(),
  fetchArchiveDownloadStatusMock: vi.fn(),
  downloadArchiveBlobMock: vi.fn(),
  startArchiveDownloadMock: vi.fn(),
  useFileTreeContextMenuMock: vi.fn(),
  queryClientMock: {},
}));

const dispatchMock = vi.fn();

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQueryClient: () => queryClientMock,
  };
});

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => useWorkspaceMock(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: { defaultValue?: string }) => fallback?.defaultValue ?? key,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/shared/components/file-workbench', () => ({
  useFileTreeManager: (config: unknown) => useFileTreeManagerMock(config),
  useFileOperationsWithDialog: (config: unknown) => useFileOperationsWithDialogMock(config),
  FileTreePanel: () => <div data-testid="file-tree-panel" />,
  StandardFileTreeLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  FileTreeContextMenu: () => null,
  useFileTreeContextMenu: (config: unknown) => {
    useFileTreeContextMenuMock(config);
    return [];
  },
  FileCreateDialog: () => null,
  FileRenameDialog: () => null,
  FileDeleteDialog: () => null,
  BatchDeleteDialog: () => null,
}));

vi.mock('@/shared/components/layout/CollapsedSidebarPlaceholder', () => ({
  CollapsedSidebarPlaceholder: () => null,
}));

vi.mock('lucide-react', () => ({
  Eye: () => null,
  EyeOff: () => null,
  FilePlus: () => null,
  Folder: () => null,
  FolderPlus: () => null,
  Loader2: () => null,
  RefreshCw: () => null,
  Upload: () => null,
}));

vi.mock('@/shared/utils/fileTypeUtils', () => ({
  isImageFile: () => false,
}));

vi.mock('../../../services/workspaceRuntimeApi', () => ({
  downloadArchiveBlob: downloadArchiveBlobMock,
  duplicateFile: vi.fn(),
  fetchArchiveDownloadStatus: fetchArchiveDownloadStatusMock,
  fetchExtractArchiveStatus: vi.fn(),
  startArchiveDownload: startArchiveDownloadMock,
  startExtractArchive: vi.fn(),
}));

vi.mock('../../version-control/lib/queryClient', () => ({
  refreshVersionControlQueries: vi.fn(),
}));

describe('FileManagementView', () => {
  beforeEach(() => {
    useWorkspaceMock.mockReset();
    useFileTreeManagerMock.mockReset();
    useFileOperationsWithDialogMock.mockReset();
    fetchArchiveDownloadStatusMock.mockReset();
    downloadArchiveBlobMock.mockReset();
    startArchiveDownloadMock.mockReset();
    useFileTreeContextMenuMock.mockReset();
    dispatchMock.mockReset();
    window.localStorage.clear();
    downloadArchiveBlobMock.mockResolvedValue(new Blob(['ok'], { type: 'application/zip' }));

    useWorkspaceMock.mockReturnValue({
      workspace: {
        openTabs: [],
      },
      dispatch: dispatchMock,
      state: {
        fileTreeShowHiddenEntries: false,
        versionControl: {
          selectedGitContextId: 'worktree:feature-auth',
        },
      },
      workspaceRuntime: {
        workspaceId: 'ws-1',
        runtimeBaseUrl: 'http://runtime.local',
        isLoading: false,
        error: null,
      },
      layout: {
        secondColumnCollapsed: false,
      },
      toggleSecondColumn: vi.fn(),
      openFileInTab: vi.fn(),
      closeTab: vi.fn(),
    });

    useFileTreeManagerMock.mockReturnValue({
      state: {
        isLoading: false,
        error: null,
        nodes: [],
        flatNodes: [],
        searchQuery: '',
        selectedId: null,
        selectedIds: new Set<string>(),
        contextMenu: null,
        closeContextMenu: vi.fn(),
        clearSelection: vi.fn(),
        setSearchQuery: vi.fn(),
        clearSearch: vi.fn(),
        selectNodeWithModifier: vi.fn(),
        toggleNode: vi.fn(),
      },
      loadTree: vi.fn(),
      operations: {
        createFile: vi.fn(),
        createDirectory: vi.fn(),
        renameFile: vi.fn(),
        deleteFile: vi.fn(),
        batchDelete: vi.fn(),
        uploadFiles: vi.fn(),
        moveFile: vi.fn(),
      },
    });

    useFileOperationsWithDialogMock.mockReturnValue({
      openCreateFileDialog: vi.fn(),
      openCreateFolderDialog: vi.fn(),
      openRenameDialog: vi.fn(),
      openDeleteDialog: vi.fn(),
      openBatchDeleteDialog: vi.fn(),
      dialogState: {
        type: null,
        data: null,
      },
      closeDialog: vi.fn(),
      handleCreateFile: vi.fn(),
      handleCreateFolder: vi.fn(),
      handleRename: vi.fn(),
      handleDelete: vi.fn(),
      handleBatchDelete: vi.fn(),
    });
  });

  it('passes the selected git context to the file tree manager', () => {
    render(<FileManagementView />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        adapterKey: expect.stringContaining('"contextId":"worktree:feature-auth"'),
      })
    );
    expect(useFileTreeManagerMock.mock.calls.at(-1)?.[0].adapterKey).toContain('"workspaceId":"ws-1"');
    expect(useFileTreeManagerMock.mock.calls.at(-1)?.[0].adapterKey).toContain('"runtimeBaseUrl":"http://runtime.local"');
  });

  it('omits contextId when no git context is selected', () => {
    useWorkspaceMock.mockReturnValue({
      workspace: {
        openTabs: [],
      },
      dispatch: dispatchMock,
      state: {
        fileTreeShowHiddenEntries: false,
        versionControl: {
          selectedGitContextId: null,
        },
      },
      workspaceRuntime: {
        workspaceId: 'ws-1',
        runtimeBaseUrl: 'http://runtime.local',
        isLoading: false,
        error: null,
      },
      layout: {
        secondColumnCollapsed: false,
      },
      toggleSecondColumn: vi.fn(),
      openFileInTab: vi.fn(),
      closeTab: vi.fn(),
    });

    render(<FileManagementView />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        adapterKey: expect.stringContaining('"contextId":null'),
      })
    );
  });

  it('uses the workspace-level hidden-entry visibility in file tree requests', () => {
    useWorkspaceMock.mockReturnValue({
      workspace: {
        openTabs: [],
      },
      dispatch: dispatchMock,
      state: {
        fileTreeShowHiddenEntries: true,
        versionControl: {
          selectedGitContextId: 'worktree:feature-auth',
        },
      },
      workspaceRuntime: {
        workspaceId: 'ws-1',
        runtimeBaseUrl: 'http://runtime.local',
        isLoading: false,
        error: null,
      },
      layout: {
        secondColumnCollapsed: false,
      },
      toggleSecondColumn: vi.fn(),
      openFileInTab: vi.fn(),
      closeTab: vi.fn(),
    });

    render(<FileManagementView />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        adapterKey: expect.stringContaining('"includeHidden":true'),
      })
    );
  });

  it('restores an active archive operation from localStorage after refresh', async () => {
    fetchArchiveDownloadStatusMock.mockResolvedValue({
      operationId: 'archive-123',
      status: 'running',
      progress: 0.5,
      message: 'Packaging files...',
      startedAt: '2026-01-01T00:00:00Z',
      result: null,
    });
    window.localStorage.setItem('workspace.fileManagement.archiveOperations.v1', JSON.stringify([
      {
        operationId: 'archive-123',
        archiveName: 'selection.zip',
        paths: ['/src'],
        workspaceId: 'ws-1',
        contextId: 'worktree:feature-auth',
        runtimeBaseUrl: 'http://runtime.local',
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    render(<FileManagementView />);

    await waitFor(() => {
      expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledWith('http://runtime.local', 'archive-123');
    });
  });

  it('clears persisted archive metadata when restore cannot find the operation', async () => {
    fetchArchiveDownloadStatusMock.mockRejectedValue(new Error('not found'));
    window.localStorage.setItem('workspace.fileManagement.archiveOperations.v1', JSON.stringify([
      {
        operationId: 'archive-missing',
        archiveName: 'selection.zip',
        paths: ['/src'],
        workspaceId: 'ws-1',
        contextId: 'worktree:feature-auth',
        runtimeBaseUrl: 'http://runtime.local',
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    render(<FileManagementView />);

    await waitFor(() => {
      expect(window.localStorage.getItem('workspace.fileManagement.archiveOperations.v1')).toBe('[]');
    });
  });

  it('keeps archive metadata available for retry when automatic download fails', async () => {
    useFileTreeManagerMock.mockReturnValue({
      state: {
        isLoading: false,
        error: null,
        nodes: [],
        flatNodes: [],
        searchQuery: '',
        selectedId: null,
        selectedIds: new Set<string>(),
        contextMenu: {
          node: {
            id: '/src',
            name: 'src',
            path: '/src',
            type: 'directory',
            children: [],
          },
          x: 0,
          y: 0,
        },
        closeContextMenu: vi.fn(),
        clearSelection: vi.fn(),
        setSearchQuery: vi.fn(),
        clearSearch: vi.fn(),
        selectNodeWithModifier: vi.fn(),
        toggleNode: vi.fn(),
      },
      loadTree: vi.fn(),
      operations: {
        createFile: vi.fn(),
        createDirectory: vi.fn(),
        renameFile: vi.fn(),
        deleteFile: vi.fn(),
        batchDelete: vi.fn(),
        uploadFiles: vi.fn(),
        moveFile: vi.fn(),
      },
    });
    startArchiveDownloadMock.mockResolvedValue({
      operationId: 'archive-failed-download',
      status: 'running',
      message: 'Packaging files...',
      startedAt: '2026-01-01T00:00:00Z',
    });
    fetchArchiveDownloadStatusMock.mockResolvedValue({
      operationId: 'archive-failed-download',
      status: 'completed',
      progress: 1,
      message: 'Archive ready',
      startedAt: '2026-01-01T00:00:00Z',
      result: {
        archiveName: 'src.zip',
        downloadUrl: '/api/workspaces/ws-1/archive-downloads/archive-failed-download/file',
      },
    });
    downloadArchiveBlobMock.mockRejectedValue(new Error('Unauthorized'));

    render(<FileManagementView />);

    const contextMenuConfig = useFileTreeContextMenuMock.mock.calls.at(-1)?.[0];
    await act(async () => {
      await contextMenuConfig.callbacks.onDownload(contextMenuConfig.node, ['/src']);
    });

    const persisted = JSON.parse(
      window.localStorage.getItem('workspace.fileManagement.archiveOperations.v1') ?? '[]',
    );
    expect(persisted).toEqual([
      expect.objectContaining({
        operationId: 'archive-failed-download',
        archiveName: 'src.zip',
      }),
    ]);
    expect(persisted[0].downloadTriggeredAt).toBeUndefined();
  });
});
