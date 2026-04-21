import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { KnowledgeBaseFilesTab } from './KnowledgeBaseFilesTab';

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
  },
  operations: {
    uploadFiles: vi.fn(),
    updateFile: vi.fn(),
    createDirectory: vi.fn(),
    moveFile: vi.fn(),
  },
  editor: {
    activeTab: {
      path: '/docs/readme.md',
      name: 'readme.md',
      content: 'kb content',
      originalContent: 'kb content',
      isModified: false,
      node: {
        id: '/docs/readme.md',
        name: 'readme.md',
        path: '/docs/readme.md',
        type: 'file' as const,
      },
    },
    saveTab: vi.fn(),
  },
  loadTree: vi.fn(),
  createFileAndOpen: vi.fn(),
  handleFileSelect: vi.fn(),
  handleFileDoubleClick: vi.fn(),
  renameFileAndUpdateTab: vi.fn(),
  deleteFileAndCloseTab: vi.fn(),
  batchDeleteAndCloseTabs: vi.fn(),
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
    toast: vi.fn(),
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'knowledgeBase.files.toolbarTitle': '知識庫檔案',
        'knowledgeBase.files.headerTitle': '檔案與資料夾',
        'knowledgeBase.files.readOnlyBadge': '唯讀',
        'knowledgeBase.files.viewerBadge': '檢視者',
        'knowledgeBase.files.viewerNotice': '檢視者僅可讀取',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/file-tree-manager', () => ({
  StandardFileTreeLayout: ({ toolbarContent, children }: { toolbarContent?: ReactNode; children: ReactNode }) => (
    <div>
      {toolbarContent}
      {children}
    </div>
  ),
  FileTreeToolbar: ({
    leftContent,
    isReadOnly,
  }: {
    leftContent?: ReactNode;
    isReadOnly?: boolean;
  }) => (
    <div>
      {leftContent}
      <span>{isReadOnly ? 'toolbar-readonly' : 'toolbar-editable'}</span>
    </div>
  ),
  FileTreePanel: ({
    enableDragDrop,
    enableMultiSelectBar,
  }: {
    enableDragDrop?: boolean;
    enableMultiSelectBar?: boolean;
  }) => (
    <div>{`tree-panel:${enableDragDrop ? 'drag' : 'static'}:${enableMultiSelectBar ? 'multi' : 'single'}`}</div>
  ),
  FileTreeContextMenu: () => null,
  FileEditorPanel: ({
    renderEditor,
  }: {
    renderEditor?: (tab: typeof mockManager.editor.activeTab) => ReactNode;
  }) => (
    <div>
      {renderEditor
        ? renderEditor(mockManager.editor.activeTab)
        : <div>editable-editor</div>}
    </div>
  ),
  FileCreateDialog: () => null,
  FileRenameDialog: () => null,
  FileDeleteDialog: () => null,
  BatchDeleteDialog: () => null,
  useFileTreeManager: () => mockManager,
  useFileOperationsWithDialog: () => mockFileOps,
  useFileTreeContextMenu: () => [],
}));

describe('KnowledgeBaseFilesTab', () => {
  beforeEach(() => {
    mockManager.state.error = null;
  });

  it('在可編輯模式渲染檔案管理介面', () => {
    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

    expect(screen.getByText('知識庫檔案')).toBeInTheDocument();
    expect(screen.getByText('檔案與資料夾')).toBeInTheDocument();
    expect(screen.getByText('toolbar-editable')).toBeInTheDocument();
    expect(screen.getByText('tree-panel:drag:multi')).toBeInTheDocument();
    expect(screen.getByText('editable-editor')).toBeInTheDocument();
  });

  it('在 viewer 模式顯示唯讀 editor 與 badge', () => {
    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly />);

    expect(screen.getByText('唯讀')).toBeInTheDocument();
    expect(screen.getByText('檢視者')).toBeInTheDocument();
    expect(screen.getByText('檢視者僅可讀取')).toBeInTheDocument();
    expect(screen.getByText('toolbar-readonly')).toBeInTheDocument();
    expect(screen.getByDisplayValue('kb content')).toBeInTheDocument();
    expect(screen.getByText('tree-panel:static:single')).toBeInTheDocument();
  });
});
