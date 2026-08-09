import React from 'react';
import { File } from 'lucide-react';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createFileTreeResourceIdentity } from '../model/fileTreeAsyncCoordinator';
import type { FileTreeDataAdapter } from '../types';
import { FileManagementSidebarWorkflow } from './FileManagementSidebarWorkflow';

const useFileTreeManagerMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/layout/CollapsedSidebarPlaceholder', () => ({
  CollapsedSidebarPlaceholder: ({ testId }: { testId?: string }) => (
    <div data-testid={testId}>collapsed-placeholder</div>
  ),
}));

vi.mock('@/shared/components/resource-workflow', () => ({
  ResourceSidebarShell: ({
    header,
    search,
    scopeFilter,
    body,
  }: {
    header?: React.ReactNode;
    search?: React.ReactNode;
    scopeFilter?: React.ReactNode;
    body?: React.ReactNode;
  }) => (
    <div>
      <div>{header}</div>
      <div>{search}</div>
      <div>{scopeFilter}</div>
      <div>{body}</div>
    </div>
  ),
}));

vi.mock('../tree/FileTreePanel', () => ({
  FileTreePanel: () => <div>file-tree-panel</div>,
}));

vi.mock('../tree/FileTreeContextMenu', () => ({
  FileTreeContextMenu: () => null,
}));

vi.mock('../primitives/FileTreeSearchBar', () => ({
  FileTreeSearchBar: ({ placeholder }: { placeholder: string }) => <div>{placeholder}</div>,
}));

vi.mock('../tree/FileOperationDialogs', () => ({
  FileCreateDialog: () => null,
  FileRenameDialog: () => null,
  FileDeleteDialog: () => null,
}));

vi.mock('../hooks/useFileTreeContextMenu', () => ({
  useFileTreeContextMenu: () => [],
}));

vi.mock('../hooks/useFileTreeManager', () => ({
  useFileTreeManager: useFileTreeManagerMock,
}));

const createAdapter = (): FileTreeDataAdapter => ({
  getTree: vi.fn().mockResolvedValue([]),
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
});

const resourceIdentity = createFileTreeResourceIdentity('test-resource', {
  key: 'file-management-sidebar',
});

describe('FileManagementSidebarWorkflow', () => {
  const createManager = () => ({
    state: {
      isLoading: false,
      searchQuery: '',
      setSearchQuery: vi.fn(),
      clearSearch: vi.fn(),
      contextMenu: null,
      closeContextMenu: vi.fn(),
      clearSelection: vi.fn(),
      selectNodeWithModifier: vi.fn(),
      openContextMenu: vi.fn(),
    },
    operations: {
      uploadFiles: vi.fn(),
      createFile: vi.fn(),
      renameFile: vi.fn(),
      deleteFile: vi.fn(),
      moveFile: vi.fn(),
    },
    loadTree: vi.fn().mockResolvedValue(undefined),
    createFileAndOpen: vi.fn().mockResolvedValue(undefined),
    batchDeleteAndCloseTabs: vi.fn().mockResolvedValue(undefined),
  });

  useFileTreeManagerMock.mockImplementation(() => createManager());

  it('hides the complete toolbar row when capabilities are read-only', () => {
    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        scopeContent={<div>scope-content</div>}
        capabilities={{
          canCreateFile: false,
          canCreateFolder: false,
          canUpload: false,
        }}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText('common.fileTree.toolbar.moreActions')).not.toBeInTheDocument();
    expect(screen.queryByText('scope-content')).not.toBeInTheDocument();
    expect(screen.getByText('Search files')).toBeInTheDocument();
  });

  it('routes create actions through shared toolbar callbacks', async () => {
    const user = userEvent.setup();
    const onCreateFile = vi.fn();

    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        scopeContent={<div>scope-content</div>}
        capabilities={{
          canCreateFile: true,
          canCreateFolder: false,
          canUpload: false,
        }}
        onCreateFile={onCreateFile}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
      />,
    );

    await user.click(screen.getByLabelText('common.fileTree.toolbar.moreActions'));
    await user.click(await screen.findByText('common.fileTree.contextMenu.createFile'));

    expect(onCreateFile).toHaveBeenCalledTimes(1);
  });

  it('renders the complete shared toolbar action set below search', () => {
    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        showHeader={false}
        capabilities={{
          canCreateFile: true,
          canCreateFolder: true,
          canUpload: true,
        }}
        onCreateFile={vi.fn()}
        onCreateFolder={vi.fn()}
        onUpload={vi.fn()}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFile' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFolder' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.upload' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.fileTree.contextMenu.refresh' })).not.toBeInTheDocument();

    expect(
      screen.getByText('Search files').compareDocumentPosition(
        screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFile' }),
      ),
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('can hide the shared toolbar when actions are hosted externally', () => {
    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        showHeader={false}
        showToolbar={false}
        capabilities={{
          canCreateFile: true,
          canCreateFolder: true,
          canUpload: true,
        }}
        onCreateFile={vi.fn()}
        onCreateFolder={vi.fn()}
        onUpload={vi.fn()}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.getByText('Search files')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.fileTree.contextMenu.createFile' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.fileTree.contextMenu.createFolder' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.fileTree.contextMenu.upload' })).not.toBeInTheDocument();
  });

  it('can hide the shared header when hosted inside another sidebar shell', () => {
    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        showHeader={false}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.queryByText('Agent files')).not.toBeInTheDocument();
    expect(screen.getByText('Search files')).toBeInTheDocument();
  });

  it('renders a collapsed icon placeholder when the sidebar is collapsed', () => {
    render(
      <FileManagementSidebarWorkflow
        adapter={createAdapter()}
        resourceIdentity={resourceIdentity}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        isCollapsed
        onToggleCollapse={vi.fn()}
      />,
    );

    expect(screen.getByTestId('file-management-sidebar-collapsed-icon')).toHaveTextContent('collapsed-placeholder');
    expect(screen.queryByText('Search files')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.sidebar.expand' })).toBeInTheDocument();
  });

  it('loads a provided manager without managed-adapter configuration', async () => {
    const providedManager = createManager();
    useFileTreeManagerMock.mockClear();

    const renderWorkflow = (loadEnabled: boolean, refreshSignal: string) => (
      <FileManagementSidebarWorkflow
        manager={providedManager}
        title="Agent files"
        searchPlaceholder="Search files"
        headerIcon={File}
        isCollapsed={false}
        onToggleCollapse={vi.fn()}
        loadEnabled={loadEnabled}
        refreshSignal={refreshSignal}
      />
    );

    const { rerender } = render(renderWorkflow(false, 'initial'));

    expect(providedManager.loadTree).not.toHaveBeenCalled();
    expect(useFileTreeManagerMock).not.toHaveBeenCalled();

    rerender(renderWorkflow(true, 'initial'));

    await waitFor(() => {
      expect(providedManager.loadTree).toHaveBeenCalledTimes(1);
    });

    rerender(renderWorkflow(true, 'refresh'));

    await waitFor(() => {
      expect(providedManager.loadTree).toHaveBeenCalledTimes(2);
    });
    expect(useFileTreeManagerMock).not.toHaveBeenCalled();
  });

});
