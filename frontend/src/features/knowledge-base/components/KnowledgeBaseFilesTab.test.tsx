import type { ReactNode } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { KnowledgeBaseFilesTab } from './KnowledgeBaseFilesTab';

const workbenchPropsMock = vi.hoisted(() => vi.fn());
const apiGetBlobMock = vi.hoisted(() => vi.fn());

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
    toast: vi.fn(),
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    getBlob: apiGetBlobMock,
    post: vi.fn(),
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'knowledgeBase.files.toolbarTitle': '知識庫檔案',
        'knowledgeBase.files.readOnlyBadge': '唯讀',
        'knowledgeBase.files.viewerBadge': '檢視者',
        'workspace.layout.collapseSidebar': '收折側欄',
        'workspace.layout.expandSidebar': '展開側欄',
      };
      return translations[key] ?? key;
    },
  }),
}));

vi.mock('@/shared/components/file-workbench', () => ({
  API_ENDPOINTS: {
    knowledgeBase: {
      copy: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/copy`,
      getContent: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
    },
  },
  StandardFileTreeLayout: ({
    toolbarContent,
    children,
    showToolbar,
  }: {
    toolbarContent?: ReactNode;
    children: ReactNode;
    showToolbar?: boolean;
  }) => (
    <div>
      {showToolbar === false ? null : toolbarContent}
      {children}
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
  FileCreateDialog: () => null,
  FileRenameDialog: () => null,
  FileDeleteDialog: () => null,
  BatchDeleteDialog: () => null,
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
  FileViewerWorkbench: (props: {
    readOnly?: boolean;
    tabs: Array<{ name: string; content: string }>;
    activeTabId: string | null;
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
  useFileTreeManager: () => mockManager,
  useFileOperationsWithDialog: () => mockFileOps,
  useFileTreeContextMenu: () => [],
}));

vi.mock('./file-workbench/knowledgeBaseFileWorkbenchAdapter', () => ({
  createKnowledgeBaseFileWorkbenchAdapter: ({
    knowledgeBaseId,
    readFile,
    saveFile,
    copyPath,
    revealInTree,
  }: {
    knowledgeBaseId: string;
    readFile: (path: string) => Promise<string>;
    saveFile?: (path: string, content: string) => Promise<void>;
    copyPath?: (path: string) => Promise<void>;
    revealInTree?: (path: string) => void;
  }) => ({
    readFile,
    readBlob: (path: string) => apiGetBlobMock(
      `/knowledge-bases/${knowledgeBaseId}/files/content?path=${encodeURIComponent(path)}&raw=true`,
    ),
    saveFile,
    copyPath,
    revealInTree,
  }),
}));

describe('KnowledgeBaseFilesTab', () => {
  beforeEach(() => {
    workbenchPropsMock.mockReset();
    apiGetBlobMock.mockReset();
    apiGetBlobMock.mockResolvedValue(new Blob(['image'], { type: 'image/png' }));
    mockManager.state.error = null;
    mockManager.state.selectedIds = new Set<string>();
    mockManager.state.flatNodes = [];
    mockManager.editor.tabs = [{
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
    mockManager.state.selectNode.mockReset();
  });

  it('在可編輯模式渲染檔案管理介面', () => {
    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

    expect(screen.getByText('知識庫檔案')).toBeInTheDocument();
    expect(screen.queryByText('檔案與資料夾')).not.toBeInTheDocument();
    expect(screen.getByText('tree-panel:drag:multi')).toBeInTheDocument();
    expect(screen.getByText('editable-workbench')).toBeInTheDocument();
  });

  it('在 viewer 模式顯示唯讀 workbench 與 badge', () => {
    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly />);

    expect(screen.getByText('唯讀')).toBeInTheDocument();
    expect(screen.queryByText('檢視者')).not.toBeInTheDocument();
    expect(screen.getByText('readonly-workbench')).toBeInTheDocument();
    expect(screen.getByText('readme.md:kb content')).toBeInTheDocument();
    expect(screen.getByText('tree-panel:static:single')).toBeInTheDocument();
  });

  it('把多個已開啟檔案轉成 shared workbench tabs 並保留 active tab', () => {
    mockManager.editor.tabs = [
      mockManager.editor.tabs[0],
      {
        path: '/docs/guide.mmd',
        name: 'guide.mmd',
        content: 'graph TD; A-->B;',
        originalContent: 'graph TD; A-->B;',
        isModified: true,
        node: {
          id: '/docs/guide.mmd',
          name: 'guide.mmd',
          path: '/docs/guide.mmd',
          type: 'file' as const,
        },
      },
    ];
    mockManager.editor.activeTabPath = '/docs/guide.mmd';

    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

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

  it('提供 shared workbench adapter 的文字讀取、儲存、raw blob、複製路徑與 reveal-in-tree 能力', async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    mockManager.operations.readFile.mockResolvedValue('fresh content');
    mockManager.operations.updateFile.mockResolvedValue(undefined);

    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

    const props = workbenchPropsMock.mock.calls.at(-1)?.[0];

    await expect(props.adapter.readFile('/docs/readme.md')).resolves.toBe('fresh content');
    expect(mockManager.operations.readFile).toHaveBeenCalledWith('/docs/readme.md');

    await props.adapter.saveFile('/docs/readme.md', 'next content');
    expect(mockManager.operations.updateFile).toHaveBeenCalledWith('/docs/readme.md', 'next content');
    expect(mockManager.editor.saveTab).toHaveBeenCalledWith('/docs/readme.md');

    await props.adapter.readBlob('/assets/logo.png');
    expect(apiGetBlobMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/files/content?path=%2Fassets%2Flogo.png&raw=true',
    );

    await props.adapter.copyPath('/docs/readme.md');
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/docs/readme.md');

    props.adapter.revealInTree('/docs/readme.md');
    expect(mockManager.state.selectNode).toHaveBeenCalledWith('/docs/readme.md');
  });

  it('同步 shared workbench 的關閉、內容更新、儲存狀態與 active tab 變更', () => {
    mockManager.editor.tabs = [
      mockManager.editor.tabs[0],
      {
        path: '/docs/draft.md',
        name: 'draft.md',
        content: 'old draft',
        originalContent: 'base draft',
        isModified: true,
        node: {
          id: '/docs/draft.md',
          name: 'draft.md',
          path: '/docs/draft.md',
          type: 'file' as const,
        },
      },
    ];
    mockManager.editor.activeTabPath = '/docs/readme.md';

    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

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
    expect(mockManager.editor.saveTab).toHaveBeenCalledWith('/docs/draft.md');
    expect(mockManager.editor.setActiveTab).toHaveBeenCalledWith('/docs/draft.md');
  });

  it('可收折並重新展開 tree panel', async () => {
    const user = userEvent.setup();
    render(<KnowledgeBaseFilesTab knowledgeBaseId="kb-1" readOnly={false} />);

    await user.click(screen.getByRole('button', { name: '收折側欄' }));
    expect(screen.queryByText('tree-panel:drag:multi')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展開側欄' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '展開側欄' }));
    expect(screen.getByText('tree-panel:drag:multi')).toBeInTheDocument();
  });
});
