import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from '@/__tests__/utils/render';
import { FileManagementView } from './FileManagementView';

const {
  useWorkspaceMock,
  useFileTreeManagerMock,
  useFileOperationsWithDialogMock,
  queryClientMock,
} = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  useFileTreeManagerMock: vi.fn(),
  useFileOperationsWithDialogMock: vi.fn(),
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
  useFileTreeContextMenu: () => [],
  FileCreateDialog: () => null,
  FileRenameDialog: () => null,
  FileDeleteDialog: () => null,
  BatchDeleteDialog: () => null,
}));

vi.mock('@/shared/components/layout/CollapsedSidebarPlaceholder', () => ({
  CollapsedSidebarPlaceholder: () => null,
}));

vi.mock('lucide-react', () => ({
  Folder: () => null,
  Loader2: () => null,
}));

vi.mock('@/shared/utils/fileTypeUtils', () => ({
  isImageFile: () => false,
}));

vi.mock('../../../services/workspaceRuntimeApi', () => ({
  duplicateFile: vi.fn(),
  fetchExtractArchiveStatus: vi.fn(),
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
    dispatchMock.mockReset();

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
});
