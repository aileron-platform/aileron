import type { DragEvent, ReactElement, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { render as baseRender, screen } from '@/__tests__/utils/render';
import { FileManagementSidebar } from './FileManagementSidebar';

const {
  useWorkspaceMock,
  useFileTreeManagerMock,
  useFileOperationsWithDialogMock,
  fetchArchiveDownloadStatusMock,
  fetchExtractArchiveStatusMock,
  downloadArchiveBlobMock,
  startArchiveDownloadMock,
  startExtractArchiveMock,
  useFileTreeContextMenuMock,
  queryClientMock,
  fileManagementDialogsMock,
  loadTreeMock,
  sidebarWorkflowPropsMock,
  fileTreePanelPropsMock,
  setDraggingPathMock,
  setDragOverPathMock,
  toastMock,
  workflowInteractionState,
  fileConflictStartMock,
  fileConflictControllerOptionsMock,
} = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  useFileTreeManagerMock: vi.fn(),
  useFileOperationsWithDialogMock: vi.fn(),
  fetchArchiveDownloadStatusMock: vi.fn(),
  fetchExtractArchiveStatusMock: vi.fn(),
  downloadArchiveBlobMock: vi.fn(),
  startArchiveDownloadMock: vi.fn(),
  startExtractArchiveMock: vi.fn(),
  useFileTreeContextMenuMock: vi.fn(),
  queryClientMock: {},
  fileManagementDialogsMock: vi.fn(),
  loadTreeMock: vi.fn(),
  sidebarWorkflowPropsMock: vi.fn(),
  fileTreePanelPropsMock: vi.fn(),
  setDraggingPathMock: vi.fn(),
  setDragOverPathMock: vi.fn(),
  toastMock: vi.fn(),
  workflowInteractionState: {
    dialogState: null,
    setDialogState: vi.fn(),
    closeDialog: vi.fn(),
    draggingPath: '/README.md',
    setDraggingPath: vi.fn(),
    dragOverPath: '/docs',
    setDragOverPath: vi.fn(),
  },
  fileConflictStartMock: vi.fn(),
  fileConflictControllerOptionsMock: vi.fn(),
}));

workflowInteractionState.setDraggingPath = setDraggingPathMock;
workflowInteractionState.setDragOverPath = setDragOverPathMock;

const dispatchMock = vi.fn();

const render = (ui: ReactElement, options?: Parameters<typeof baseRender>[1]) => baseRender(
  <>{ui}</>,
  options,
);

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
    toast: toastMock,
  }),
}));

vi.mock('@/shared/components/file-workbench', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/file-workbench')>();
  return {
    ...actual,
    FileManagementDialogs: (props: unknown) => {
      fileManagementDialogsMock(props);
      return null;
    },
    FileManagementSidebarWorkflow: (props: {
      manager?: unknown;
      toolbarRightContent?: ReactNode;
      renderBody?: (args: {
        manager: unknown;
        isReadOnly: boolean;
        interactionState: typeof workflowInteractionState;
      }) => ReactNode;
      onCreateFile?: () => void;
      onCreateFolder?: () => void;
      onUpload?: () => void;
      loadEnabled?: boolean;
    }) => {
      sidebarWorkflowPropsMock(props);
      return (
        <div>
          {props.onCreateFile ? <button type="button" aria-label="workspace.fileManagement.tree.actions.create.file" onClick={props.onCreateFile} /> : null}
          {props.onCreateFolder ? <button type="button" aria-label="workspace.fileManagement.tree.actions.create.folder" onClick={props.onCreateFolder} /> : null}
          {props.onUpload ? <button type="button" aria-label="workspace.fileManagement.tree.actions.create.upload" onClick={props.onUpload} /> : null}
          {props.toolbarRightContent}
          {props.renderBody?.({
            manager: props.manager,
            isReadOnly: false,
            interactionState: workflowInteractionState,
          })}
        </div>
      );
    },
    FileTreePanel: (props: {
      enableToolbar?: boolean;
      renderToolbar?: () => ReactNode;
      [key: string]: unknown;
    }) => {
      fileTreePanelPropsMock(props);
      return (
        <div data-testid="file-tree-panel">
          {props.enableToolbar || props.renderToolbar ? (
            <div data-testid="file-tree-panel-toolbar">
              {props.renderToolbar?.()}
            </div>
          ) : null}
        </div>
      );
    },
    FileTreeContextMenu: () => null,
    useFileManagementContextMenuBuilder: (config: unknown) => {
      useFileTreeContextMenuMock(config);
      return [];
    },
    useFileTreeContextMenu: (config: unknown) => {
      useFileTreeContextMenuMock(config);
      return [];
    },
    useFileTreeManager: (config: unknown) => useFileTreeManagerMock(config),
    useFileOperationsWithDialog: (config: unknown) => useFileOperationsWithDialogMock(config),
    useFileConflictController: (options: unknown) => {
      fileConflictControllerOptionsMock(options);
      return ({
      open: false, pending: false, operation: null, conflicts: [], defaultStrategy: 'keep-both', itemStrategies: {}, error: null,
      start: fileConflictStartMock, setDefaultStrategy: vi.fn(), setItemStrategy: vi.fn(), cancel: vi.fn(), confirm: vi.fn(),
      });
    },
    FileCreateDialog: () => null,
    FileRenameDialog: () => null,
    FileDeleteDialog: () => null,
    BatchDeleteDialog: () => null,
  };
});

vi.mock('@/shared/components/layout/CollapsedSidebarPlaceholder', () => ({
  CollapsedSidebarPlaceholder: () => null,
}));

vi.mock('lucide-react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('lucide-react')>();
  return {
    ...actual,
    Eye: () => null,
    EyeOff: () => null,
    Download: () => null,
    FilePlus: () => null,
    Folder: () => null,
    FolderPlus: () => null,
    Loader2: () => null,
    RefreshCw: () => null,
    Upload: () => null,
  };
});

vi.mock('../../../api/workspaceRuntimeApi', () => ({
  downloadArchiveBlob: downloadArchiveBlobMock,
  fetchArchiveDownloadStatus: fetchArchiveDownloadStatusMock,
  fetchExtractArchiveStatus: fetchExtractArchiveStatusMock,
  startArchiveDownload: startArchiveDownloadMock,
  startExtractArchive: startExtractArchiveMock,
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      refresh: vi.fn().mockResolvedValue(undefined),
    }),
  };
});

describe('FileManagementSidebar', () => {
  beforeEach(() => {
    useWorkspaceMock.mockReset();
    useFileTreeManagerMock.mockReset();
    useFileOperationsWithDialogMock.mockReset();
    fetchArchiveDownloadStatusMock.mockReset();
    fetchExtractArchiveStatusMock.mockReset();
    downloadArchiveBlobMock.mockReset();
    startArchiveDownloadMock.mockReset();
    startExtractArchiveMock.mockReset();
    useFileTreeContextMenuMock.mockReset();
    fileManagementDialogsMock.mockReset();
    loadTreeMock.mockReset();
    loadTreeMock.mockResolvedValue(undefined);
    sidebarWorkflowPropsMock.mockReset();
    fileTreePanelPropsMock.mockReset();
    setDraggingPathMock.mockReset();
    setDragOverPathMock.mockReset();
    toastMock.mockReset();
    fileConflictStartMock.mockReset();
    fileConflictControllerOptionsMock.mockReset();
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
      permissions: {
        canWrite: true,
      },
      fileEditor: { modifiedTabs: [] },
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
        selectNode: vi.fn(),
        toggleNode: vi.fn(),
      },
      loadTree: loadTreeMock,
      operations: {
        createFile: vi.fn(),
        createDirectory: vi.fn(),
        renameFile: vi.fn(),
        deleteFile: vi.fn(),
        batchDelete: vi.fn(),
        uploadFiles: vi.fn(),
        moveFile: vi.fn().mockResolvedValue({ success: true }),
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
    render(<FileManagementSidebar />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        resourceIdentity: {
          kind: 'workspace',
          attributes: expect.objectContaining({
            contextId: 'worktree:feature-auth',
            workspaceId: 'ws-1',
            runtimeBaseUrl: 'http://runtime.local',
          }),
        },
      })
    );
  });

  it('loads the file tree when File Management mounts with a runtime URL', async () => {
    render(<FileManagementSidebar />);

    await waitFor(() => {
      expect(loadTreeMock).toHaveBeenCalledTimes(1);
    });
    expect(sidebarWorkflowPropsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      loadEnabled: false,
    });
  });

  it('waits for the runtime URL before loading the file tree exactly once', async () => {
    const readyWorkspace = useWorkspaceMock();
    const pendingWorkspace = {
      ...readyWorkspace,
      workspaceRuntime: {
        ...readyWorkspace.workspaceRuntime,
        runtimeBaseUrl: null,
      },
    };
    useWorkspaceMock.mockReturnValue(pendingWorkspace);

    const view = render(<FileManagementSidebar />);

    expect(loadTreeMock).not.toHaveBeenCalled();

    useWorkspaceMock.mockReturnValue(readyWorkspace);
    view.rerender(
      <>
        <FileManagementSidebar />
      </>,
    );

    await waitFor(() => {
      expect(loadTreeMock).toHaveBeenCalledTimes(1);
    });
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
      permissions: {
        canWrite: true,
      },
      fileEditor: { modifiedTabs: [] },
      openFileInTab: vi.fn(),
      closeTab: vi.fn(),
    });

    render(<FileManagementSidebar />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        resourceIdentity: expect.objectContaining({
          attributes: expect.objectContaining({
            contextId: null,
          }),
        }),
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
      permissions: {
        canWrite: true,
      },
      fileEditor: { modifiedTabs: [] },
      openFileInTab: vi.fn(),
      closeTab: vi.fn(),
    });

    render(<FileManagementSidebar />);

    expect(useFileTreeManagerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        resourceIdentity: expect.objectContaining({
          attributes: expect.objectContaining({
            includeHidden: true,
          }),
        }),
      })
    );
  });

  it('routes create, rename, and delete dialogs through the shared file management dialogs', () => {
    useFileOperationsWithDialogMock.mockReturnValue({
      openCreateFileDialog: vi.fn(),
      openCreateFolderDialog: vi.fn(),
      openRenameDialog: vi.fn(),
      openDeleteDialog: vi.fn(),
      openBatchDeleteDialog: vi.fn(),
      dialogState: {
        type: 'rename',
        data: {
          currentName: 'README.md',
          node: { name: 'README.md', path: '/README.md', type: 'file' },
        },
      },
      closeDialog: vi.fn(),
      handleCreateFile: vi.fn(),
      handleCreateFolder: vi.fn(),
      handleRename: vi.fn(),
      handleDelete: vi.fn(),
      handleBatchDelete: vi.fn(),
    });

    render(<FileManagementSidebar />);

    expect(fileManagementDialogsMock).toHaveBeenCalledWith(expect.objectContaining({
      dialogState: {
        type: 'rename',
        node: { name: 'README.md', path: '/README.md', type: 'file' },
      },
      onRename: expect.any(Function),
      onCreateFile: expect.any(Function),
      onCreateFolder: expect.any(Function),
      onDelete: expect.any(Function),
    }));
  });

  it('keeps file actions in the shared sidebar toolbar without rendering a second tree toolbar', () => {
    render(<FileManagementSidebar />);

    expect(screen.queryByRole('button', {
      name: 'workspace.fileManagement.tree.actions.refresh.tooltip',
    })).not.toBeInTheDocument();
    expect(screen.queryByTestId('file-tree-panel-toolbar')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'workspace.fileManagement.tree.actions.create.file',
    })).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'workspace.fileManagement.tree.actions.create.folder',
    })).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'workspace.fileManagement.tree.actions.create.upload',
    })).toBeInTheDocument();
  });

  it('fails closed after Workspace write access is revoked', async () => {
    const writableWorkspace = useWorkspaceMock();
    useWorkspaceMock.mockReturnValue({
      ...writableWorkspace,
      permissions: {
        canWrite: false,
      },
    });
    window.localStorage.setItem(
      'workspace.fileManagement.archiveOperations.v1',
      JSON.stringify([{
        operationId: 'archive-revoked',
        archiveName: 'revoked.zip',
        paths: ['/src'],
        context: {
          workspaceId: 'ws-1',
          contextId: 'worktree:feature-auth',
          runtimeBaseUrl: 'http://runtime.local',
        },
        startedAt: '2026-01-01T00:00:00Z',
      }]),
    );

    render(<FileManagementSidebar />);

    expect(sidebarWorkflowPropsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      capabilities: {
        canCreateFile: false,
        canCreateFolder: false,
        canUpload: false,
      },
    });
    expect(useFileTreeContextMenuMock.mock.calls.at(-1)?.[0]).toMatchObject({
      readOnly: true,
    });
    expect(fileManagementDialogsMock).not.toHaveBeenCalled();
    expect(fetchArchiveDownloadStatusMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          'workspace.fileManagement.archiveOperations.v1',
        ),
      ).toBe('[]');
    });

    const guardedOperations = useFileOperationsWithDialogMock.mock.calls.at(-1)?.[0] as {
      onCreateFile: (name: string, parentPath: string) => Promise<void>;
    };
    const manager = useFileTreeManagerMock.mock.results.at(-1)?.value;
    await guardedOperations.onCreateFile('blocked.md', '/');
    expect(manager.operations.createFile).not.toHaveBeenCalled();
  });

  it('uses the shared workflow drag state and setters for file tree drag operations', async () => {
    render(<FileManagementSidebar />);

    const manager = useFileTreeManagerMock.mock.results.at(-1)?.value as {
      state: { flatNodes: Array<{ id: string; name: string; path: string; type: 'file' | 'directory'; children: never[] }> };
    };
    manager.state.flatNodes = [
      {
        id: '/README.md',
        name: 'README.md',
        path: '/README.md',
        type: 'file',
        children: [],
      },
      {
        id: '/docs',
        name: 'docs',
        path: '/docs',
        type: 'directory',
        children: [],
      },
    ];

    type DragNode = {
      id: string;
      name: string;
      path: string;
      type: 'file' | 'directory';
      children: never[];
    };
    type FileTreeDragProps = {
      draggingPath: string | null;
      dragOverPath: string | null;
      onDragStart: (node: DragNode, event: DragEvent) => void;
      onDragEnd: (node: DragNode, event: DragEvent) => void;
      onDragOver: (node: DragNode, event: DragEvent) => void;
      onDragLeave: (node: DragNode, event: DragEvent) => void;
      onDrop: (node: DragNode, event: DragEvent) => Promise<void>;
    };

    const panelProps = fileTreePanelPropsMock.mock.calls.at(-1)?.[0] as FileTreeDragProps;
    const sourceNode: DragNode = {
      id: '/README.md',
      name: 'README.md',
      path: '/README.md',
      type: 'file',
      children: [],
    };
    const docsNode: DragNode = {
      id: '/docs',
      name: 'docs',
      path: '/docs',
      type: 'directory',
      children: [],
    };
    const sourceEvent = {
      dataTransfer: {
        effectAllowed: 'none',
        dropEffect: 'none',
        setData: vi.fn(),
      },
      preventDefault: vi.fn(),
    } as unknown as DragEvent;

    expect(panelProps.draggingPath).toBe('/README.md');
    expect(panelProps.dragOverPath).toBe('/docs');

    panelProps.onDragStart(sourceNode, sourceEvent);
    expect(setDraggingPathMock).toHaveBeenCalledWith('/README.md');
    expect(sourceEvent.dataTransfer.setData).toHaveBeenCalledWith('text/plain', '/README.md');

    panelProps.onDragOver({ ...docsNode, id: '/src', name: 'src', path: '/src' }, sourceEvent);
    expect(setDragOverPathMock).toHaveBeenCalledWith('/src');

    panelProps.onDragLeave(docsNode, sourceEvent);
    expect(setDragOverPathMock).toHaveBeenCalledWith(null);

    setDraggingPathMock.mockClear();
    setDragOverPathMock.mockClear();
    await act(async () => {
      await panelProps.onDrop(docsNode, sourceEvent);
    });

    expect(fileConflictStartMock).toHaveBeenCalledWith({
      operation: 'move',
      targetPath: '/docs/README.md',
      sources: [{ sourcePath: '/README.md', entryType: 'file' }],
      archivePath: null,
    }, {
      files: [],
      sourcePath: '/README.md',
      entryType: 'file',
    });
    expect(setDraggingPathMock).toHaveBeenCalledWith(null);
    expect(setDragOverPathMock).toHaveBeenCalledWith(null);

    setDraggingPathMock.mockClear();
    setDragOverPathMock.mockClear();
    panelProps.onDragEnd(sourceNode, sourceEvent);
    expect(setDraggingPathMock).toHaveBeenCalledWith(null);
    expect(setDragOverPathMock).toHaveBeenCalledWith(null);
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
        context: {
          workspaceId: 'ws-1',
          contextId: 'worktree:feature-auth',
          runtimeBaseUrl: 'http://runtime.local',
        },
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    render(<FileManagementSidebar />);

    await waitFor(() => {
      expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledWith('http://runtime.local', 'archive-123');
    });
  });

  it('stops restored archive polling without downloading after write access is revoked', async () => {
    let resolvePolling!: (value: {
      operationId: string;
      status: 'completed';
      progress: number;
      message: string;
      startedAt: string;
      result: {
        archiveName: string;
        downloadUrl: string;
      };
    }) => void;
    fetchArchiveDownloadStatusMock
      .mockResolvedValueOnce({
        operationId: 'archive-revoke-during-poll',
        status: 'running',
        progress: 0.5,
        message: 'Packaging files...',
        startedAt: '2026-01-01T00:00:00Z',
        result: null,
      })
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolvePolling = resolve;
      }));
    window.localStorage.setItem('workspace.fileManagement.archiveOperations.v1', JSON.stringify([
      {
        operationId: 'archive-revoke-during-poll',
        archiveName: 'selection.zip',
        paths: ['/src'],
        context: {
          workspaceId: 'ws-1',
          contextId: 'worktree:feature-auth',
          runtimeBaseUrl: 'http://runtime.local',
        },
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    const view = render(<FileManagementSidebar />);
    await waitFor(() => {
      expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledTimes(2);
    });

    const writableWorkspace = useWorkspaceMock();
    useWorkspaceMock.mockReturnValue({
      ...writableWorkspace,
      permissions: { ...writableWorkspace.permissions, canWrite: false },
    });
    view.rerender(
      <>
        <FileManagementSidebar />
      </>,
    );

    await act(async () => {
      resolvePolling({
        operationId: 'archive-revoke-during-poll',
        status: 'completed',
        progress: 1,
        message: 'Archive ready',
        startedAt: '2026-01-01T00:00:00Z',
        result: {
          archiveName: 'selection.zip',
          downloadUrl: '/api/v1/files/archive/archive-revoke-during-poll/download',
        },
      });
      await Promise.resolve();
    });

    expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledTimes(2);
    expect(downloadArchiveBlobMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(window.localStorage.getItem('workspace.fileManagement.archiveOperations.v1')).toBe('[]');
    });
  });

  it('does not emit archive failure side effects after unmount', async () => {
    let rejectArchivePolling!: (error: Error) => void;
    startArchiveDownloadMock.mockResolvedValue({
      operationId: 'archive-unmounted',
      status: 'running',
      message: 'Packaging files...',
      startedAt: '2026-01-01T00:00:00Z',
    });
    fetchArchiveDownloadStatusMock.mockImplementation(() => new Promise((_, reject) => {
      rejectArchivePolling = reject;
    }));
    const directoryNode = {
      id: '/src',
      name: 'src',
      path: '/src',
      type: 'directory' as const,
      children: [],
    };

    const view = render(<FileManagementSidebar />);
    const contextMenuConfig = useFileTreeContextMenuMock.mock.calls.at(-1)?.[0];
    void contextMenuConfig.callbacks.onDownload(directoryNode, ['/src']);
    await waitFor(() => {
      expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledTimes(1);
    });
    const toastCountBeforeUnmount = toastMock.mock.calls.length;

    view.unmount();
    await act(async () => {
      rejectArchivePolling(new Error('Request aborted after unmount'));
      await Promise.resolve();
    });

    expect(toastMock).toHaveBeenCalledTimes(toastCountBeforeUnmount);
    expect(toastMock).not.toHaveBeenCalledWith(expect.objectContaining({
      title: 'workspace.fileManagement.tree.notifications.archiveFailed',
    }));
  });

  it('does not emit restored archive polling failure side effects after unmount', async () => {
    let rejectRestoredPolling!: (error: Error) => void;
    fetchArchiveDownloadStatusMock
      .mockResolvedValueOnce({
        operationId: 'archive-restored-unmounted',
        status: 'running',
        progress: 0.5,
        message: 'Packaging files...',
        startedAt: '2026-01-01T00:00:00Z',
        result: null,
      })
      .mockImplementationOnce(() => new Promise((_, reject) => {
        rejectRestoredPolling = reject;
      }));
    window.localStorage.setItem('workspace.fileManagement.archiveOperations.v1', JSON.stringify([
      {
        operationId: 'archive-restored-unmounted',
        archiveName: 'selection.zip',
        paths: ['/src'],
        context: {
          workspaceId: 'ws-1',
          contextId: 'worktree:feature-auth',
          runtimeBaseUrl: 'http://runtime.local',
        },
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    const view = render(<FileManagementSidebar />);
    await waitFor(() => {
      expect(fetchArchiveDownloadStatusMock).toHaveBeenCalledTimes(2);
    });

    view.unmount();
    await act(async () => {
      rejectRestoredPolling(new Error('Request aborted after unmount'));
      await Promise.resolve();
    });

    expect(toastMock).not.toHaveBeenCalled();
  });

  it('clears persisted archive metadata when restore cannot find the operation', async () => {
    fetchArchiveDownloadStatusMock.mockRejectedValue(new Error('not found'));
    window.localStorage.setItem('workspace.fileManagement.archiveOperations.v1', JSON.stringify([
      {
        operationId: 'archive-missing',
        archiveName: 'selection.zip',
        paths: ['/src'],
        context: {
          workspaceId: 'ws-1',
          contextId: 'worktree:feature-auth',
          runtimeBaseUrl: 'http://runtime.local',
        },
        startedAt: '2026-01-01T00:00:00Z',
      },
    ]));

    render(<FileManagementSidebar />);

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
        moveFile: vi.fn().mockResolvedValue({ success: true }),
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

    render(<FileManagementSidebar />);

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

  it('routes workspace extract through one shared conflict preflight request', async () => {
    render(<FileManagementSidebar />);
    const config = useFileTreeContextMenuMock.mock.calls.at(-1)?.[0];
    const zipNode = { id: '/src.zip', name: 'src.zip', path: '/src.zip', type: 'file' as const };
    await config.callbacks.onExtractArchive(zipNode);
    expect(fileConflictStartMock).toHaveBeenCalledWith({
      operation: 'extract', targetPath: '/', sources: null, archivePath: '/src.zip',
    }, {});
  });

  it('preserves selection and clipboard when a conflict batch partially fails', async () => {
    render(<FileManagementSidebar />);
    const config = useFileTreeContextMenuMock.mock.calls.at(-1)?.[0];
    const source = { id: '/source.md', name: 'source.md', path: '/source.md', type: 'file' as const };
    await act(async () => {
      config.callbacks.onCopy(source);
      await Promise.resolve();
    });
    const options = fileConflictControllerOptionsMock.mock.calls.at(-1)?.[0];
    await act(async () => {
      options.onCompleted({
        items: [{ sourcePath: '/source.md', finalPath: '/target/source.md', status: 'created', size: 1, type: 'file', error: null }, { sourcePath: '/failed.md', finalPath: null, status: 'failed', size: 0, type: 'file', error: 'failed' }],
        total: 2, succeeded: 1, skipped: 0, failed: 1,
      });
      await Promise.resolve();
    });
    expect(useFileTreeManagerMock.mock.results.at(-1)?.value.state.selectNode).not.toHaveBeenCalled();
    fileConflictStartMock.mockClear();
    const currentConfig = useFileTreeContextMenuMock.mock.calls.at(-1)?.[0];
    await currentConfig.callbacks.onPaste();
    expect(fileConflictStartMock).toHaveBeenCalledWith(expect.objectContaining({
      operation: 'paste', sources: [{ sourcePath: '/source.md', entryType: 'file' }],
    }), {});
  });
});
