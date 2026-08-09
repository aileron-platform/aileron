import type { DragEvent, ReactNode } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { KnowledgeBaseFilesTab } from './KnowledgeBaseFilesTab';

const workbenchPropsMock = vi.hoisted(() => vi.fn());
const fileTreePanelPropsMock = vi.hoisted(() => vi.fn());
const fileTreeDragPropsMock = vi.hoisted(() => vi.fn());
const contextMenuConfigMock = vi.hoisted(() => vi.fn());
const fileManagementDialogsMock = vi.hoisted(() => vi.fn());
const fileTreeManagerOptionsMock = vi.hoisted(() => vi.fn());
const sidebarWorkflowPropsMock = vi.hoisted(() => vi.fn());
const toastMock = vi.hoisted(() => vi.fn());
const queryClientMock = vi.hoisted(() => ({
  getQueryCache: vi.fn(() => ({ findAll: () => [] })),
  invalidateQueries: vi.fn(),
  refetchQueries: vi.fn(),
}));
const fileConflictStartMock = vi.hoisted(() => vi.fn());
const fileConflictControllerOptionsMock = vi.hoisted(() => vi.fn());
const sidebarInteractionStateMock = vi.hoisted(() => ({
  dialogState: null,
  setDialogState: vi.fn(),
  closeDialog: vi.fn(),
  draggingPath: '/workflow-dragging.md',
  setDraggingPath: vi.fn(),
  dragOverPath: '/workflow-drop-target',
  setDragOverPath: vi.fn(),
}));
const knowledgeBaseFileApiMock = vi.hoisted(() => ({
  buildKnowledgeBaseFileDownloadUrl: vi.fn(),
  downloadKnowledgeBaseArchiveBlob: vi.fn(),
  fetchKnowledgeBaseArchiveDownloadStatus: vi.fn(),
  startKnowledgeBaseArchiveDownload: vi.fn(),
}));

const mockManager = {
  state: {
    searchQuery: '',
    setSearchQuery: vi.fn(),
    clearSearch: vi.fn(),
    error: null as string | null,
    isLoading: false,
    contextMenu: null,
    closeContextMenu: vi.fn(),
    openContextMenu: vi.fn(),
    selectedIds: new Set<string>(),
    flatNodes: [],
    clearSelection: vi.fn(),
    selectNodeWithModifier: vi.fn(),
    selectNode: vi.fn(),
  },
  operations: {
    readFile: vi.fn(),
    uploadFiles: vi.fn(),
    updateFile: vi.fn(),
    createDirectory: vi.fn(),
    moveFile: vi.fn(),
  },
  editor: {
    tabs: [{
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'kb content',
      originalContent: 'kb content',
      isModified: false,
      revision: 'kb-version-1',
      node: {
        id: '/docs/readme.md',
        name: 'readme.md',
        path: '/docs/readme.md',
        type: 'file' as const,
      },
    }],
    activeTabPath: '/docs/readme.md',
    activeTab: {
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'kb content',
      originalContent: 'kb content',
      isModified: false,
      revision: 'kb-version-1',
      node: {
        id: '/docs/readme.md',
        name: 'readme.md',
        path: '/docs/readme.md',
        type: 'file' as const,
      },
    },
    saveTab: vi.fn(),
    closeTab: vi.fn(),
    getTab: vi.fn(),
    updateContent: vi.fn(),
    setActiveTab: vi.fn(),
    revertTab: vi.fn(),
  },
  loadTree: vi.fn(),
  createFileAndOpen: vi.fn(),
  handleFileSelect: vi.fn(),
  handleFileDoubleClick: vi.fn(),
  renameFileAndUpdateTab: vi.fn(),
  deleteFileAndCloseTab: vi.fn(),
  batchDeleteAndCloseTabs: vi.fn(),
  moveFileAndUpdateTabs: vi.fn(),
};

const mockFileOps = {
  dialogState: { type: null, data: undefined },
  closeDialog: vi.fn(),
  openCreateFileDialog: vi.fn(),
  openCreateFolderDialog: vi.fn(),
  openRenameDialog: vi.fn(),
  openDeleteDialog: vi.fn(),
  openBatchDeleteDialog: vi.fn(),
  handleCreateFile: vi.fn(),
  handleCreateFolder: vi.fn(),
  handleRename: vi.fn(),
  handleDelete: vi.fn(),
  handleBatchDelete: vi.fn(),
};

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@tanstack/react-query', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@tanstack/react-query')>()),
  useQueryClient: () => queryClientMock,
}));

vi.mock('@/shared/api/apiClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api/apiClient')>()),
  apiClient: {
    post: vi.fn(),
  },
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => knowledgeBaseFileApiMock);

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'knowledgeBase.files.toolbarTitle': '\u77e5\u8b58\u5eab\u6a94\u6848',
        'knowledgeBase.navigation.files': '\u77e5\u8b58\u5eab\u6a94\u6848',
        'knowledgeBase.files.actions.createFile': '\u65b0\u589e\u6587\u5b57\u6a94',
        'knowledgeBase.files.actions.createFolder': '\u65b0\u589e\u8cc7\u6599\u593e',
        'knowledgeBase.files.actions.upload': '\u4e0a\u50b3',
        'knowledgeBase.files.actions.refresh': '\u91cd\u65b0\u6574\u7406',
        'knowledgeBase.files.actions.hidden.showLabel': '\u986f\u793a\u96b1\u85cf\u9805\u76ee',
        'knowledgeBase.files.actions.hidden.showTooltip': '\u986f\u793a\u96b1\u85cf\u9805\u76ee',
        'knowledgeBase.files.actions.hidden.hideLabel': '\u96b1\u85cf\u96b1\u85cf\u9805\u76ee',
        'knowledgeBase.files.actions.hidden.hideTooltip': '\u96b1\u85cf\u96b1\u85cf\u9805\u76ee',
        'shared.shell.collapseSidebar': '\u6536\u6298\u5074\u6b04',
        'shared.shell.expandSidebar': '\u5c55\u958b\u5074\u6b04',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/file-workbench', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/file-workbench')>();
  return {
    ...actual,
    ArchiveProgressOverlays: ({
      extractProgress,
      archiveProgress,
    }: {
      extractProgress: { archiveName: string } | null;
      archiveProgress: { archiveName: string } | null;
    }) => (
      <div>
        {extractProgress ? <div>{`extract:${extractProgress.archiveName}`}</div> : null}
        {archiveProgress ? <div>{`archive:${archiveProgress.archiveName}`}</div> : null}
      </div>
    ),
    FileManagementDialogs: (props: unknown) => {
      fileManagementDialogsMock(props);
      return null;
    },
    FileManagementSidebarWorkflow: (props: {
      toolbarRightContent?: ReactNode;
      renderBody?: (args: {
        interactionState: typeof sidebarInteractionStateMock;
      }) => ReactNode;
      onCreateFile?: () => void;
      onCreateFolder?: () => void;
      onUpload?: () => void;
      loadEnabled?: boolean;
    }) => {
      sidebarWorkflowPropsMock(props);
      const { toolbarRightContent, renderBody, onCreateFile, onCreateFolder, onUpload } = props;
      return (
        <div>
          {onCreateFile ? <button type="button" onClick={onCreateFile} aria-label="common.fileTree.contextMenu.createFile" /> : null}
          {onCreateFolder ? <button type="button" onClick={onCreateFolder} aria-label="common.fileTree.contextMenu.createFolder" /> : null}
          {onUpload ? <button type="button" onClick={onUpload} aria-label="common.fileTree.contextMenu.upload" /> : null}
          {toolbarRightContent}
          {renderBody?.({
            interactionState: sidebarInteractionStateMock,
          })}
        </div>
      );
    },
    FileTreePanel: (props: {
      enableDragDrop?: boolean;
      enableMultiSelectBar?: boolean;
      renderToolbar?: () => ReactNode;
      onDragStart?: (node: { path: string }, event: DragEvent) => void;
      onDragEnd?: (node: { path: string }, event: DragEvent) => void;
      onDragOver?: (node: { path: string }, event: DragEvent) => void;
      onDragLeave?: (node: { path: string }, event: DragEvent) => void;
      onDrop?: (node: { path: string }, event: DragEvent) => void;
      draggingPath?: string | null;
      dragOverPath?: string | null;
    }) => {
      const { enableDragDrop, enableMultiSelectBar, renderToolbar } = props;
      fileTreePanelPropsMock({ enableDragDrop, enableMultiSelectBar });
      fileTreeDragPropsMock({
        onDragStart: props.onDragStart,
        onDragEnd: props.onDragEnd,
        onDragOver: props.onDragOver,
        onDragLeave: props.onDragLeave,
        onDrop: props.onDrop,
        draggingPath: props.draggingPath,
        dragOverPath: props.dragOverPath,
      });
      return (
        <div>
          {renderToolbar?.()}
          <div>{`tree-panel:${enableDragDrop ? 'drag' : 'static'}:${enableMultiSelectBar ? 'multi' : 'single'}`}</div>
        </div>
      );
    },
    FileTreeContextMenu: () => null,
    FileCreateDialog: () => null,
    FileRenameDialog: () => null,
    FileDeleteDialog: () => null,
    BatchDeleteDialog: () => null,
    useFileTreeManager: (options: unknown) => {
      fileTreeManagerOptionsMock(options);
      return mockManager;
    },
    useFileOperationsWithDialog: () => mockFileOps,
    useFileConflictController: (options: unknown) => {
      fileConflictControllerOptionsMock(options);
      return ({
      open: false, pending: false, operation: null, conflicts: [], defaultStrategy: 'keep-both', itemStrategies: {}, error: null,
      start: fileConflictStartMock, setDefaultStrategy: vi.fn(), setItemStrategy: vi.fn(), cancel: vi.fn(), confirm: vi.fn(),
      });
    },
    useFileTreeContextMenu: (config: unknown) => {
      contextMenuConfigMock(config);
      return [];
    },
    useFileManagementContextMenuBuilder: (config: unknown) => {
      contextMenuConfigMock(config);
      return [];
    },
    toFileWorkbenchTab: (tab: {
      id?: string;
      path: string;
      name: string;
      content: string;
      originalContent: string;
      isModified: boolean;
    }) => ({
      id: tab.id ?? tab.path,
      path: tab.path,
      name: tab.name,
      content: tab.content,
      originalContent: tab.originalContent,
      isModified: tab.isModified,
    }),
  };
});

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  FileViewerWorkbench: (props: {
    readOnly?: boolean;
    tabs: Array<{ name: string; content: string }>;
    activeTabId: string | null;
    isExpanded?: boolean;
    onExpandedChange?: (expanded: boolean) => void;
  }) => {
    workbenchPropsMock(props);
    return (
      <div>
        <div>{props.readOnly ? 'readonly-workbench' : 'editable-workbench'}</div>
        <div>{`active:${props.activeTabId ?? 'none'}`}</div>
        {props.tabs.map((tab) => (
          <div key={tab.name}>{`${tab.name}:${tab.content}`}</div>
        ))}
      </div>
    );
  },
}));

vi.mock('../adapters/file-workbench/knowledgeBaseFileWorkbenchAdapter', () => ({
  createKnowledgeBaseFileWorkbenchAdapter: ({
    readFile,
    saveFile,
    copyPath,
    revealInTree,
  }: {
    readFile: (path: string) => Promise<string>;
    saveFile?: (path: string, content: string) => Promise<void>;
    copyPath?: (path: string) => Promise<void>;
    revealInTree?: (path: string) => void;
  }) => ({
    readFile,
    saveFile,
    copyPath,
    revealInTree,
  }),
}));

describe('KnowledgeBaseFilesTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    workbenchPropsMock.mockReset();
    fileTreePanelPropsMock.mockReset();
    fileTreeDragPropsMock.mockReset();
    contextMenuConfigMock.mockReset();
    fileManagementDialogsMock.mockReset();
    fileTreeManagerOptionsMock.mockReset();
    sidebarWorkflowPropsMock.mockReset();
    toastMock.mockReset();
    sidebarInteractionStateMock.setDialogState.mockReset();
    sidebarInteractionStateMock.closeDialog.mockReset();
    sidebarInteractionStateMock.setDraggingPath.mockReset();
    sidebarInteractionStateMock.setDragOverPath.mockReset();
    Object.values(knowledgeBaseFileApiMock).forEach((mock) => mock.mockReset());
    knowledgeBaseFileApiMock.buildKnowledgeBaseFileDownloadUrl.mockReturnValue(
      '/api/v1/knowledge-bases/kb-1/files/download?path=%2Fdocs%2Fa.md',
    );
    knowledgeBaseFileApiMock.downloadKnowledgeBaseArchiveBlob.mockResolvedValue(
      new Blob(['zip'], { type: 'application/zip' }),
    );
    knowledgeBaseFileApiMock.startKnowledgeBaseArchiveDownload.mockResolvedValue({
      operationId: 'archive-123',
      status: 'pending',
      message: 'Preparing ZIP download...',
      startedAt: '2026-06-10T00:00:00Z',
    });
    knowledgeBaseFileApiMock.fetchKnowledgeBaseArchiveDownloadStatus.mockResolvedValue({
      operationId: 'archive-123',
      status: 'completed',
      progress: 1,
      message: 'Archive ready',
      startedAt: '2026-06-10T00:00:00Z',
      result: {
        archiveName: 'docs.zip',
        downloadUrl: '/api/v1/knowledge-bases/kb-1/files/archive/archive-123/download',
        size: 12,
        expiresAt: '2026-06-10T00:30:00Z',
      },
    });
    vi.spyOn(window, 'open').mockReturnValue(null);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:archive'),
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });
    mockManager.state.error = null;
    mockManager.state.contextMenu = null;
    mockManager.state.selectedIds = new Set<string>();
    mockManager.state.flatNodes = [];
    mockManager.editor.tabs = [{
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'kb content',
      originalContent: 'kb content',
      isModified: false,
      revision: 'kb-version-1',
      node: {
        id: '/docs/readme.md',
        name: 'readme.md',
        path: '/docs/readme.md',
        type: 'file' as const,
      },
    }];
    mockManager.editor.activeTabPath = '/docs/readme.md';
    mockManager.editor.activeTab = mockManager.editor.tabs[0];
    mockManager.editor.getTab.mockImplementation((path: string) => (
      mockManager.editor.tabs.find((tab) => tab.path === path)
    ));
    Object.values(mockManager.operations).forEach((mock) => mock.mockReset());
    mockManager.editor.saveTab.mockReset();
    mockManager.editor.closeTab.mockReset();
    mockManager.editor.updateContent.mockReset();
    mockManager.editor.setActiveTab.mockReset();
    mockManager.editor.revertTab.mockReset();
    mockManager.state.selectNode.mockReset();
    mockManager.loadTree.mockReset();
    mockFileOps.openCreateFileDialog.mockReset();
    mockFileOps.closeDialog.mockReset();
  });

  it('renders the refresh action in the knowledge base files header', async () => {
    const user = userEvent.setup();
    mockManager.loadTree.mockResolvedValue(undefined);

    render(
      <KnowledgeBaseFilesTab
        knowledgeBaseId="kb-1"
        canWrite
        renderRegions={({ navigator, navigatorActions }) => (
          <div data-testid="semantic-files-surface">
            {navigator}
            {navigatorActions}
          </div>
        )}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: '\u91cd\u65b0\u6574\u7406',
    }));

    expect(mockManager.loadTree).toHaveBeenCalledTimes(1);
    expect(fileTreeManagerOptionsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      autoLoad: false,
      resourceIdentity: {
        kind: 'knowledge-base',
        attributes: {
          knowledgeBaseId: 'kb-1',
          includeHidden: false,
        },
      },
    });
    expect(sidebarWorkflowPropsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      loadEnabled: true,
    });
  });

  it('routes create, rename, and delete dialogs through the shared file management dialogs', () => {
    mockFileOps.dialogState = {
      type: 'delete',
      data: {
        node: {
          id: '/docs/readme.md',
          name: 'readme.md',
          path: '/docs/readme.md',
          type: 'file',
        },
      },
    };

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    expect(fileManagementDialogsMock).toHaveBeenCalledWith(expect.objectContaining({
      dialogState: {
        type: 'delete',
        node: {
          id: '/docs/readme.md',
          name: 'readme.md',
          path: '/docs/readme.md',
          type: 'file',
        },
      },
      onCreateFile: expect.any(Function),
      onCreateFolder: expect.any(Function),
      onRename: expect.any(Function),
      onDelete: expect.any(Function),
    }));
  });

  it('\u5728\u53ef\u7de8\u8f2f\u6a21\u5f0f\u6e32\u67d3\u6a94\u6848\u7ba1\u7406\u4ecb\u9762', () => {
    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    expect(screen.getByText('\u77e5\u8b58\u5eab\u6a94\u6848')).toBeInTheDocument();
    expect(screen.queryByText('\u6a94\u6848\u8207\u8cc7\u6599\u593e')).not.toBeInTheDocument();
    expect(screen.getByText('tree-panel:drag:multi')).toBeInTheDocument();
    expect(screen.getByText('editable-workbench')).toBeInTheDocument();
  });

  it('keeps single-file reads while removing write surfaces after downgrade', async () => {
    mockManager.state.contextMenu = {
      node: {
        id: '/docs/readme.md',
        name: 'readme.md',
        path: '/docs/readme.md',
        type: 'file',
      },
      x: 0,
      y: 0,
    };
    window.localStorage.setItem(
      'knowledgeBase.files.archiveOperations.v1',
      JSON.stringify([{
        operationId: 'archive-revoked',
        archiveName: 'revoked.zip',
        paths: ['/docs'],
        context: { knowledgeBaseId: 'kb-1' },
        startedAt: '2026-06-10T00:00:00Z',
      }]),
    );

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite={false} />,
    );

    expect(screen.getByText('readonly-workbench')).toBeInTheDocument();
    expect(screen.getByText('tree-panel:static:single')).toBeInTheDocument();
    expect(fileManagementDialogsMock).not.toHaveBeenCalled();
    expect(mockFileOps.closeDialog).toHaveBeenCalled();
    expect(contextMenuConfigMock.mock.calls.at(-1)?.[0]).toMatchObject({
      readOnly: true,
      features: {
        createFile: true,
        createFolder: true,
        delete: true,
        download: true,
        extractArchive: true,
        paste: true,
        rename: true,
        upload: true,
      },
    });
    expect(
      knowledgeBaseFileApiMock.fetchKnowledgeBaseArchiveDownloadStatus,
    ).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          'knowledgeBase.files.archiveOperations.v1',
        ),
      ).toBe('[]');
    });
  });

  it('fails closed when a detached upload input changes after write access is revoked', async () => {
    const user = userEvent.setup();
    const detachedInputs: HTMLInputElement[] = [];
    vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function captureInput() {
      detachedInputs.push(this);
    });
    const view = render(
        <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />
    );

    await user.click(screen.getByRole('button', {
      name: 'common.fileTree.contextMenu.upload',
    }));
    const input = detachedInputs[0];
    if (!input) {
      throw new Error('Expected the upload input to be created');
    }

    view.rerender(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite={false} />,
    );
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [new File(['content'], 'revoked.txt', { type: 'text/plain' })],
    });
    await act(async () => {
      input.dispatchEvent(new Event('change'));
      await Promise.resolve();
    });

    expect(mockManager.operations.uploadFiles).not.toHaveBeenCalled();
    expect(toastMock).not.toHaveBeenCalled();
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
        size: number;
        expiresAt: string;
      };
    }) => void;
    knowledgeBaseFileApiMock.fetchKnowledgeBaseArchiveDownloadStatus
      .mockResolvedValueOnce({
        operationId: 'archive-revoke-during-poll',
        status: 'running',
        progress: 0.5,
        message: 'Packaging files...',
        startedAt: '2026-06-10T00:00:00Z',
        result: null,
      })
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolvePolling = resolve;
      }));
    window.localStorage.setItem(
      'knowledgeBase.files.archiveOperations.v1',
      JSON.stringify([{
        operationId: 'archive-revoke-during-poll',
        archiveName: 'docs.zip',
        paths: ['/docs'],
        context: { knowledgeBaseId: 'kb-1' },
        startedAt: '2026-06-10T00:00:00Z',
      }]),
    );

    const view = render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );
    await waitFor(() => {
      expect(
        knowledgeBaseFileApiMock.fetchKnowledgeBaseArchiveDownloadStatus,
      ).toHaveBeenCalledTimes(2);
    });

    view.rerender(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite={false} />,
    );
    await act(async () => {
      resolvePolling({
        operationId: 'archive-revoke-during-poll',
        status: 'completed',
        progress: 1,
        message: 'Archive ready',
        startedAt: '2026-06-10T00:00:00Z',
        result: {
          archiveName: 'docs.zip',
          downloadUrl: '/api/v1/knowledge-bases/kb-1/files/archive/archive-revoke-during-poll/download',
          size: 12,
          expiresAt: '2026-06-10T00:30:00Z',
        },
      });
      await Promise.resolve();
    });

    expect(
      knowledgeBaseFileApiMock.fetchKnowledgeBaseArchiveDownloadStatus,
    ).toHaveBeenCalledTimes(2);
    expect(knowledgeBaseFileApiMock.downloadKnowledgeBaseArchiveBlob).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(window.localStorage.getItem('knowledgeBase.files.archiveOperations.v1')).toBe('[]');
    });
  });

  it('does not report a rejected archive request after write generation changes', async () => {
    let rejectArchive: ((reason: Error) => void) | undefined;
    knowledgeBaseFileApiMock.startKnowledgeBaseArchiveDownload.mockImplementation(
      () => new Promise((_resolve, reject) => {
        rejectArchive = reject;
      }),
    );
    const directoryNode = {
      id: '/docs',
      name: 'docs',
      path: '/docs',
      type: 'directory' as const,
    };
    mockManager.state.contextMenu = { x: 10, y: 10, node: directoryNode };
    const view = render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const config = contextMenuConfigMock.mock.calls.at(-1)?.[0];
    config.callbacks.onDownload(directoryNode, ['/docs']);
    await waitFor(() => {
      expect(knowledgeBaseFileApiMock.startKnowledgeBaseArchiveDownload).toHaveBeenCalled();
    });
    view.rerender(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite={false} />,
    );
    await act(async () => {
      rejectArchive?.(new Error('rejected after downgrade'));
      await Promise.resolve();
    });

    expect(toastMock).not.toHaveBeenCalled();
    expect(screen.queryByText('archive:docs.zip')).not.toBeInTheDocument();
  });

  it('routes drag interaction through the sidebar workflow state', async () => {
    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const dragProps = fileTreeDragPropsMock.mock.lastCall?.[0] as {
      onDragStart: (node: { path: string }, event: DragEvent) => void;
      onDragEnd: (node: { path: string }, event: DragEvent) => void;
      onDragOver: (node: { path: string }, event: DragEvent) => void;
      onDragLeave: (node: { path: string }, event: DragEvent) => void;
      onDrop: (node: { path: string; type: 'directory' }, event: DragEvent) => Promise<void>;
      draggingPath: string | null;
      dragOverPath: string | null;
    };
    const node = { path: '/docs', type: 'directory' as const };
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: {
        files: [],
        getData: vi.fn().mockReturnValue(''),
      },
    } as unknown as DragEvent;

    expect(dragProps.draggingPath).toBe('/workflow-dragging.md');
    expect(dragProps.dragOverPath).toBe('/workflow-drop-target');

    dragProps.onDragStart(node, event);
    expect(sidebarInteractionStateMock.setDraggingPath).toHaveBeenLastCalledWith('/docs');

    dragProps.onDragOver(node, event);
    expect(sidebarInteractionStateMock.setDragOverPath).toHaveBeenLastCalledWith('/docs');

    dragProps.onDragLeave(node, event);
    expect(sidebarInteractionStateMock.setDragOverPath).toHaveBeenLastCalledWith(null);

    sidebarInteractionStateMock.setDraggingPath.mockClear();
    sidebarInteractionStateMock.setDragOverPath.mockClear();
    dragProps.onDragEnd(node, event);
    expect(sidebarInteractionStateMock.setDraggingPath).toHaveBeenCalledWith(null);
    expect(sidebarInteractionStateMock.setDragOverPath).toHaveBeenCalledWith(null);
    expect(sidebarInteractionStateMock.setDraggingPath.mock.invocationCallOrder[0]).toBeLessThan(
      sidebarInteractionStateMock.setDragOverPath.mock.invocationCallOrder[0],
    );

    sidebarInteractionStateMock.setDraggingPath.mockClear();
    sidebarInteractionStateMock.setDragOverPath.mockClear();
    await dragProps.onDrop(node, event);
    expect(sidebarInteractionStateMock.setDragOverPath).toHaveBeenCalledWith(null);
    expect(sidebarInteractionStateMock.setDraggingPath).toHaveBeenCalledWith(null);
    expect(sidebarInteractionStateMock.setDragOverPath.mock.invocationCallOrder[0]).toBeLessThan(
      sidebarInteractionStateMock.setDraggingPath.mock.invocationCallOrder[0],
    );
  });

  it('allows creating entries anywhere in the tree', async () => {
    const user = userEvent.setup();
    const docsNode = {
      id: '/docs',
      name: 'docs',
      path: '/docs',
      type: 'directory' as const,
    };
    mockManager.state.selectedIds = new Set(['/docs']);
    mockManager.state.flatNodes = [docsNode];

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    await user.click(screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFile' }));

    expect(mockFileOps.openCreateFileDialog).toHaveBeenCalledWith(docsNode);
    expect(fileTreePanelPropsMock).toHaveBeenLastCalledWith({
      enableDragDrop: true,
      enableMultiSelectBar: true,
    });
  });

  it('shows download and extract archive in the context menu', () => {
    mockManager.state.contextMenu = {
      x: 10,
      y: 10,
      node: {
        id: '/docs/sample.zip',
        name: 'sample.zip',
        path: '/docs/sample.zip',
        type: 'file' as const,
      },
    };

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const config = contextMenuConfigMock.mock.calls.at(-1)?.[0];
    expect(config.features).toMatchObject({
      download: true,
      extractArchive: true,
    });
    expect(config.callbacks.onDownload).toBeTypeOf('function');
    expect(config.callbacks.onExtractArchive).toBeTypeOf('function');
  });

  it('starts an archive download for a directory', async () => {
    const directoryNode = {
      id: '/docs',
      name: 'docs',
      path: '/docs',
      type: 'directory' as const,
    };
    mockManager.state.contextMenu = { x: 10, y: 10, node: directoryNode };

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const config = contextMenuConfigMock.mock.calls.at(-1)?.[0];
    config.callbacks.onDownload(directoryNode, ['/docs']);

    await waitFor(() => {
      expect(knowledgeBaseFileApiMock.startKnowledgeBaseArchiveDownload).toHaveBeenCalledWith('kb-1', {
        paths: ['/docs'],
        archiveName: 'docs.zip',
      });
    });
  });

  it('starts extraction for a zip file', async () => {
    const zipNode = {
      id: '/docs/sample.zip',
      name: 'sample.zip',
      path: '/docs/sample.zip',
      type: 'file' as const,
    };
    mockManager.state.contextMenu = { x: 10, y: 10, node: zipNode };

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const config = contextMenuConfigMock.mock.calls.at(-1)?.[0];
    config.callbacks.onExtractArchive(zipNode);

    await waitFor(() => {
      expect(fileConflictStartMock).toHaveBeenCalledWith({
        operation: 'extract',
        archivePath: '/docs/sample.zip',
        targetPath: '/docs',
        sources: null,
      }, {});
    });
  });

  it('keeps the current selection when a conflict batch partially fails', async () => {
    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );
    const options = fileConflictControllerOptionsMock.mock.calls.at(-1)?.[0];
    mockManager.state.selectNode.mockClear();
    await act(async () => {
      options.onCompleted({
        items: [{ sourcePath: 'ok.md', finalPath: '/docs/ok.md', status: 'created', size: 1, type: 'file', error: null }, { sourcePath: 'failed.md', finalPath: null, status: 'failed', size: 0, type: 'file', error: 'failed' }],
        total: 2, succeeded: 1, skipped: 0, failed: 1,
      });
      await Promise.resolve();
    });
    expect(mockManager.state.selectNode).not.toHaveBeenCalled();
    expect(mockManager.handleFileSelect).not.toHaveBeenCalledWith(expect.objectContaining({ path: '/docs/ok.md' }));
  });

  it('\u628a\u591a\u500b\u5df2\u958b\u555f\u6a94\u6848\u8f49\u6210 shared workbench tabs \u4e26\u4fdd\u7559 active tab', () => {
    mockManager.editor.tabs = [
      mockManager.editor.tabs[0],
      {
        path: '/docs/guide.mmd',
        name: 'guide.mmd',
        content: 'graph TD; A-->B;',
        originalContent: 'graph TD; A-->B;',
        isModified: true,
        revision: 'guide-version-1',
        node: {
          id: '/docs/guide.mmd',
          name: 'guide.mmd',
          path: '/docs/guide.mmd',
          type: 'file' as const,
        },
      },
    ];
    mockManager.editor.activeTabPath = '/docs/guide.mmd';

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const props = workbenchPropsMock.mock.calls.at(-1)?.[0];
    expect(props.tabs).toMatchObject([
      {
        id: '/docs/readme.md',
        path: '/docs/readme.md',
        name: 'readme.md',
        content: 'kb content',
        originalContent: 'kb content',
        isModified: false,
      },
      {
        id: '/docs/guide.mmd',
        path: '/docs/guide.mmd',
        name: 'guide.mmd',
        content: 'graph TD; A-->B;',
        originalContent: 'graph TD; A-->B;',
        isModified: true,
      },
    ]);
    expect(screen.getByText('active:/docs/guide.mmd')).toBeInTheDocument();
    expect(screen.getByText('guide.mmd:graph TD; A-->B;')).toBeInTheDocument();
  });

  it('\u5c55\u958b shared workbench \u6642\u4fdd\u7559\u540c\u4e00\u5957 chrome \u8a2d\u5b9a', () => {
    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const props = workbenchPropsMock.mock.calls.at(-1)?.[0];
    expect(props.isExpanded).toBe(false);
    expect(props.onExpandedChange).toBeTypeOf('function');
  });

  it('\u63d0\u4f9b shared workbench adapter \u7684\u6587\u5b57\u8b80\u53d6、\u5132\u5b58、\u8907\u88fd\u8def\u5f91\u8207 reveal-in-tree \u80fd\u529b', async () => {
    const clipboardWriteText = vi.fn().mockResolvedValue(undefined);
    const clipboard = { writeText: clipboardWriteText };
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: clipboard,
    });
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      configurable: true,
      value: clipboard,
    });
    mockManager.operations.readFile.mockResolvedValue({ content: 'fresh content' });
    mockManager.operations.updateFile.mockResolvedValue({ success: true, data: { revision: 'kb-version-2' } });

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const props = workbenchPropsMock.mock.calls.at(-1)?.[0];

    await expect(props.adapter.readFile('/docs/readme.md')).resolves.toBe('fresh content');
    expect(mockManager.operations.readFile).toHaveBeenCalledWith('/docs/readme.md');

    await props.adapter.saveFile('/docs/readme.md', 'next content');
    expect(mockManager.operations.updateFile).toHaveBeenCalledWith('/docs/readme.md', 'next content', {
      revision: 'kb-version-1',
    });
    expect(mockManager.editor.saveTab).toHaveBeenCalledWith('/docs/readme.md', 'next content', 'kb-version-2');

    await props.adapter.copyPath('/docs/readme.md');
    expect(clipboardWriteText).toHaveBeenCalledWith('/docs/readme.md');

    props.adapter.revealInTree('/docs/readme.md');
    expect(mockManager.state.selectNode).toHaveBeenCalledWith('/docs/readme.md');
  });

  it('\u540c\u6b65 shared workbench \u7684\u95dc\u9589、\u5167\u5bb9\u66f4\u65b0、\u5132\u5b58\u72c0\u614b\u8207 active tab \u8b8a\u66f4', () => {
    mockManager.editor.tabs = [
      mockManager.editor.tabs[0],
      {
        path: '/docs/draft.md',
        name: 'draft.md',
        content: 'old draft',
        originalContent: 'base draft',
        isModified: true,
        revision: 'draft-version-1',
        node: {
          id: '/docs/draft.md',
          name: 'draft.md',
          path: '/docs/draft.md',
          type: 'file' as const,
        },
      },
    ];
    mockManager.editor.activeTabPath = '/docs/readme.md';

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    const props = workbenchPropsMock.mock.calls.at(-1)?.[0];
    props.onTabsChange([
      {
        id: '/docs/draft.md',
        path: '/docs/draft.md',
        name: 'draft.md',
        content: 'new draft',
        originalContent: 'new draft',
        isModified: false,
      },
    ]);
    props.onActiveTabChange('/docs/draft.md');

    expect(mockManager.editor.closeTab).toHaveBeenCalledWith('/docs/readme.md');
    expect(mockManager.editor.updateContent).toHaveBeenCalledWith('/docs/draft.md', 'new draft');
    expect(mockManager.editor.saveTab).toHaveBeenCalledWith('/docs/draft.md', 'new draft');
    expect(mockManager.editor.setActiveTab).toHaveBeenCalledWith('/docs/draft.md');
  });

  it('exposes navigator and main content through the semantic shell contract', () => {
    render(
      <KnowledgeBaseFilesTab
        knowledgeBaseId="kb-1"
        canWrite
        renderRegions={({ navigator, navigatorActions, main }) => (
          <div>
            <div data-testid="semantic-navigator">{navigator}</div>
            <div data-testid="semantic-navigator-actions">{navigatorActions}</div>
            <div data-testid="semantic-main">{main}</div>
          </div>
        )}
      />,
    );

    expect(screen.getByTestId('semantic-navigator')).toHaveTextContent('tree-panel:drag:multi');
    expect(screen.getByTestId('semantic-navigator-actions')).toBeInTheDocument();
    expect(screen.getByTestId('semantic-main')).toHaveTextContent('\u77e5\u8b58\u5eab\u6a94\u6848');
    expect(screen.getByTestId('semantic-main')).toHaveTextContent('editable-workbench');
  });

  it('saves the modified active tab with mod+s', async () => {
    mockManager.editor.tabs[0].isModified = true;
    mockManager.editor.activeTab = mockManager.editor.tabs[0];
    mockManager.operations.updateFile.mockResolvedValue({ success: true, data: { revision: 'kb-version-2' } });

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }));

    await waitFor(() => {
      expect(mockManager.operations.updateFile).toHaveBeenCalledWith('/docs/readme.md', 'kb content', {
        revision: 'kb-version-1',
      });
    });
    expect(mockManager.editor.saveTab).toHaveBeenCalledWith('/docs/readme.md', 'kb content', 'kb-version-2');
  });

  it('saves every modified tab with mod+shift+s', async () => {
    mockManager.editor.tabs = [
      { ...mockManager.editor.tabs[0], isModified: true },
      {
        path: '/docs/guide.md',
        name: 'guide.md',
        content: 'guide content',
        originalContent: 'old guide',
        isModified: true,
        revision: 'guide-version-1',
        node: {
          id: '/docs/guide.md',
          name: 'guide.md',
          path: '/docs/guide.md',
          type: 'file' as const,
        },
      },
    ];
    mockManager.editor.activeTab = mockManager.editor.tabs[0];
    mockManager.operations.updateFile.mockResolvedValue({ success: true, data: { revision: 'next-version' } });

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, shiftKey: true, bubbles: true }));

    await waitFor(() => {
      expect(mockManager.operations.updateFile).toHaveBeenCalledWith('/docs/readme.md', 'kb content', {
        revision: 'kb-version-1',
      });
    });
    await waitFor(() => {
      expect(mockManager.operations.updateFile).toHaveBeenCalledWith('/docs/guide.md', 'guide content', {
        revision: 'guide-version-1',
      });
    });
  });

  it('reverts the modified active tab with mod+alt+z', async () => {
    mockManager.editor.tabs[0].isModified = true;
    mockManager.editor.activeTab = mockManager.editor.tabs[0];

    render(
      <KnowledgeBaseFilesTab knowledgeBaseId="kb-1" canWrite />,
    );

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, altKey: true, bubbles: true }));

    await waitFor(() => {
      expect(mockManager.editor.revertTab).toHaveBeenCalledWith('/docs/readme.md');
    });
    expect(mockManager.operations.updateFile).not.toHaveBeenCalled();
  });
});
