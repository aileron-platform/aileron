import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarkdownViewer } from './MarkdownViewer';

vi.mock('rehype-katex', () => ({ default: () => (tree: any) => tree }));
vi.mock('katex/dist/katex.min.css', () => ({}));

const {
  openFileInTabMock,
  saveFileContentMock,
  toastMock,
  updateTabContentMock,
  setTabModifiedMock,
  setOriginalContentMock,
  reloadCurrentFileMock,
  modifiedTabsMock,
  setDraftMessageMock,
  ensureLoadedMock,
  tMock,
} = vi.hoisted(() => ({
  openFileInTabMock: vi.fn(),
  saveFileContentMock: vi.fn().mockResolvedValue({ success: true, message: 'saved' }),
  toastMock: vi.fn(),
  updateTabContentMock: vi.fn(),
  setTabModifiedMock: vi.fn(),
  setOriginalContentMock: vi.fn(),
  reloadCurrentFileMock: vi.fn().mockResolvedValue({ success: true }),
  modifiedTabsMock: [] as string[],
  setDraftMessageMock: vi.fn(),
  ensureLoadedMock: vi.fn().mockResolvedValue(undefined),
  tMock: (key: string) =>
    ({
      'workspace.fileManagement.markdown.title': 'Markdown',
      'workspace.fileManagement.markdown.refresh': '重新載入 Markdown',
      'workspace.fileManagement.markdown.refreshing': '正在重新載入 Markdown',
      'workspace.fileManagement.markdown.refreshConfirm': '確認覆蓋本地修改？',
      'workspace.fileManagement.markdown.refreshFailed': '重新載入 Markdown 失敗',
      'workspace.fileManagement.markdown.empty': '空白內容',
      'workspace.fileManagement.markdown.linkOpenFailed': '無法開啟連結檔案',
      'workspace.fileManagement.focus.exit': '離開檔案專注模式',
      'workspace.openspec.tasks.summary': '已完成 {{done}} / {{total}}',
      'workspace.openspec.tasks.nextIncomplete': '下一個未完成項目',
      'workspace.openspec.tasks.noTasks': '沒有工作項',
      'workspace.openspec.tasks.saving': '儲存中...',
      'workspace.openspec.tasks.saveFailed': '任務狀態儲存失敗',
      'workspace.openspec.spec.tocTitle': 'Spec 目錄',
      'workspace.openspec.spec.showToc': '顯示目錄',
      'workspace.openspec.spec.hideToc': '隱藏目錄',
      'workspace.openspec.spec.searchPlaceholder': '搜尋 Requirement 或 Scenario',
      'workspace.openspec.spec.collapseRequirement': '收折 Requirement',
      'workspace.openspec.spec.expandRequirement': '展開 Requirement',
      'workspace.openspec.spec.emptyToc': '沒有目錄',
    }[key] ?? key),
}));

const mockNodes = [
  {
    id: '/docs',
    name: 'docs',
    path: '/docs',
    type: 'directory' as const,
    depth: 0,
    children: [
      {
        id: '/docs/guide.md',
        name: 'guide.md',
        path: '/docs/guide.md',
        type: 'file' as const,
        depth: 1,
      },
      {
        id: '/docs/claim-manage',
        name: 'claim-manage',
        path: '/docs/claim-manage',
        type: 'directory' as const,
        depth: 1,
        children: [
          {
            id: '/docs/claim-manage/contracts',
            name: 'contracts',
            path: '/docs/claim-manage/contracts',
            type: 'directory' as const,
            depth: 2,
            children: [
              {
                id: '/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md',
                name: 'personaltag-wclaimnoandseq-update.md',
                path: '/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md',
                type: 'file' as const,
                depth: 3,
              },
            ],
          },
        ],
      },
    ],
  },
];

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspace: {
      openTabs: [
        {
          id: '/docs/guide.md',
          name: 'guide.md',
          path: '/docs/guide.md',
          content: '',
        },
      ],
      activeTabId: '/docs/guide.md',
    },
    fileEditor: {
      modifiedTabs: modifiedTabsMock,
      originalContents: {},
      updateTabContent: updateTabContentMock,
      setTabModified: setTabModifiedMock,
      setOriginalContent: setOriginalContentMock,
      saveFile: vi.fn(),
      saveAllFiles: vi.fn(),
      reloadCurrentFile: reloadCurrentFileMock,
      revertFile: vi.fn(),
      revertAllFiles: vi.fn(),
    },
    fileTreeActions: {
      saveFileContent: saveFileContentMock,
    },
    fileTreeState: {
      nodes: mockNodes,
    },
    openFileInTab: openFileInTabMock,
    dispatch: vi.fn(),
    state: {
      rightChatCollapsed: false,
    },
  }),
}));

vi.mock('../../../components/ChatPanel/chatPanelStateContext', () => ({
  useChatPanelStateContext: () => ([{}, { setDraftMessage: setDraftMessageMock }]),
}));

vi.mock('../../openspec/OpenSpecWorkspaceContext', () => ({
  useOpenSpecWorkspace: () => ({
    ensureLoaded: ensureLoadedMock,
    actions: [
      {
        id: 'apply',
        title: 'Apply',
        description: 'Implement the current change',
        group: 'implement',
        profile: 'core',
        availability: 'enabled',
        reason: null,
        recommended: true,
        recommendedReason: 'There is an active change with work ready to implement',
        requiresChange: true,
        supportsChangeArgument: true,
        inputKind: 'change',
        exampleCommand: '/opsx:apply demo',
        draftTemplate: '/opsx:apply demo',
      },
      {
        id: 'sync',
        title: 'Sync',
        description: 'Sync specs',
        group: 'finalize',
        profile: 'expanded',
        availability: 'enabled',
        reason: null,
        recommended: false,
        recommendedReason: null,
        requiresChange: true,
        supportsChangeArgument: true,
        inputKind: 'change',
        exampleCommand: '/opsx:sync demo',
        draftTemplate: '/opsx:sync demo',
      },
    ],
  }),
}));

describe('MarkdownViewer', () => {
  beforeEach(() => {
    openFileInTabMock.mockReset();
    toastMock.mockReset();
    updateTabContentMock.mockReset();
    setTabModifiedMock.mockReset();
    setOriginalContentMock.mockReset();
    reloadCurrentFileMock.mockReset();
    reloadCurrentFileMock.mockResolvedValue({ success: true });
    setDraftMessageMock.mockReset();
    ensureLoadedMock.mockReset();
    ensureLoadedMock.mockResolvedValue(undefined);
    modifiedTabsMock.length = 0;
    saveFileContentMock.mockReset();
    saveFileContentMock.mockResolvedValue({ success: true, message: 'saved' });
  });

  it('reloads the current Markdown file when refresh is clicked on an unmodified tab', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="# Guide"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('button', { name: '重新載入 Markdown' }));

    expect(reloadCurrentFileMock).toHaveBeenCalledTimes(1);
  });

  it('does not reload a modified Markdown tab when refresh is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    modifiedTabsMock.push('/docs/guide.md');

    render(
      <MarkdownViewer
        content="# Guide"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('button', { name: '重新載入 Markdown' }));

    expect(confirmSpy).toHaveBeenCalledWith('確認覆蓋本地修改？');
    expect(reloadCurrentFileMock).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('opens relative workspace links in a workspace tab', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="[spec](./claim-manage/contracts/personaltag-wclaimnoandseq-update.md)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('link', { name: 'spec' }));

    expect(openFileInTabMock).toHaveBeenCalledWith(
      '/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md',
    );
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('keeps external links as browser new-tab links', () => {
    render(
      <MarkdownViewer
        content="[external](https://example.com/spec)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    const link = screen.getByRole('link', { name: 'external' });
    expect(link).toHaveAttribute('href', 'https://example.com/spec');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders <br> tags as line breaks in the default markdown preview', () => {
    const { container, rerender } = render(
      <MarkdownViewer
        content="line 1<br>line 2"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    expect(container.querySelectorAll('br')).toHaveLength(1);

    rerender(
      <MarkdownViewer
        content="line 1<br/>line 2"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    expect(container.querySelectorAll('br')).toHaveLength(1);
  });

  it('uses the shared focus toolbar and removes the duplicate expand control', () => {
    const onExitFocusMode = vi.fn();

    render(
      <MarkdownViewer
        content="# Guide"
        fileName="guide.md"
        filePath="/docs/guide.md"
        isFocusMode
        onExitFocusMode={onExitFocusMode}
      />,
    );

    expect(screen.getByRole('button', { name: '離開檔案專注模式' })).toBeInTheDocument();
    expect(screen.queryByTitle('workspace.fileManagement.markdown.expand')).not.toBeInTheDocument();
  });

  it('shows an error when an internal workspace path cannot be opened', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="[missing](./missing.md)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('link', { name: 'missing' }));

    expect(openFileInTabMock).not.toHaveBeenCalled();
    expect(toastMock).toHaveBeenCalledWith({
      title: '無法開啟連結檔案',
      description: '/docs/missing.md',
      variant: 'destructive',
    });
  });

  it('opens root-relative workspace links in a workspace tab', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="[spec](/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('link', { name: 'spec' }));

    expect(openFileInTabMock).toHaveBeenCalledWith(
      '/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md',
    );
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('opens bare-relative workspace links in a workspace tab', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="[spec](claim-manage/contracts/personaltag-wclaimnoandseq-update.md)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    await user.click(screen.getByRole('link', { name: 'spec' }));

    expect(openFileInTabMock).toHaveBeenCalledWith(
      '/docs/claim-manage/contracts/personaltag-wclaimnoandseq-update.md',
    );
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('keeps anchor links as in-document navigation without opening tabs', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content="[jump](#overview)"
        fileName="guide.md"
        filePath="/docs/guide.md"
      />,
    );

    const link = screen.getByRole('link', { name: 'jump' });
    expect(link).toHaveAttribute('href', '#overview');
    expect(link).not.toHaveAttribute('target', '_blank');

    await user.click(link);

    expect(openFileInTabMock).not.toHaveBeenCalled();
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('renders OpenSpec tasks with interactive checkboxes', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content={`## 1. Navigation\n\n- [ ] 1.1 Add OpenSpec menu`}
        fileName="tasks.md"
        filePath="/openspec/changes/demo/tasks.md"
      />,
    );

    const checkbox = screen.getByRole('checkbox', { name: '1.1 Add OpenSpec menu' });
    await user.click(checkbox);

    expect(updateTabContentMock).toHaveBeenCalledWith(
      '/docs/guide.md',
      expect.stringContaining('- [x] 1.1 Add OpenSpec menu'),
    );
    expect(saveFileContentMock).toHaveBeenCalledWith(
      '/openspec/changes/demo/tasks.md',
      expect.stringContaining('- [x] 1.1 Add OpenSpec menu'),
    );
    expect(setOriginalContentMock).toHaveBeenCalledWith(
      '/docs/guide.md',
      expect.stringContaining('- [x] 1.1 Add OpenSpec menu'),
    );
    expect(setTabModifiedMock).toHaveBeenLastCalledWith('/docs/guide.md', false);
  });

  it('keeps modified state and shows error if OpenSpec tasks auto-save fails', async () => {
    saveFileContentMock.mockResolvedValueOnce({ success: false, message: 'save failed' });
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content={`## 1. Navigation\n\n- [ ] 1.1 Add OpenSpec menu`}
        fileName="tasks.md"
        filePath="/openspec/changes/demo/tasks.md"
      />,
    );

    await user.click(screen.getByRole('checkbox', { name: '1.1 Add OpenSpec menu' }));

    expect(toastMock).toHaveBeenCalledWith({
      title: '任務狀態儲存失敗',
      description: 'save failed',
      variant: 'destructive',
    });
    expect(setOriginalContentMock).not.toHaveBeenCalled();
  });

  it('renders OpenSpec spec outline from requirement and scenario headings', () => {
    render(
      <MarkdownViewer
        content={`## ADDED Requirements

### Requirement: OpenSpec shall show specs
#### Scenario: User opens outline`}
        fileName="spec.md"
        filePath="/openspec/changes/demo/specs/workspace-openspec-browser/spec.md"
      />,
    );

    expect(screen.getByText('Spec 目錄')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'OpenSpec shall show specs' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'User opens outline' })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Requirement: OpenSpec shall show specs' }),
    ).toHaveAttribute('id');
  });

  it('scrolls to the selected OpenSpec outline target', async () => {
    const user = userEvent.setup();
    const scrollToMock = vi.fn();
    const originalScrollTo = Element.prototype.scrollTo;
    Element.prototype.scrollTo = scrollToMock;

    render(
      <MarkdownViewer
        content={`## ADDED Requirements

### Requirement: OpenSpec shall show specs
#### Scenario: User opens outline`}
        fileName="spec.md"
        filePath="/openspec/changes/demo/specs/workspace-openspec-browser/spec.md"
      />,
    );

    const heading = screen.getByRole('heading', {
      name: 'Requirement: OpenSpec shall show specs',
    });
    Object.defineProperty(heading, 'offsetTop', {
      configurable: true,
      value: 240,
    });

    await user.click(screen.getByRole('button', { name: 'OpenSpec shall show specs' }));

    expect(scrollToMock).toHaveBeenCalledWith({
      top: 216,
      behavior: 'smooth',
    });

    Element.prototype.scrollTo = originalScrollTo;
  });

  it('supports hiding the spec outline and filtering its content', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content={`## ADDED Requirements

### Requirement: OpenSpec shall show specs
#### Scenario: User opens outline

### Requirement: OpenSpec shall show tasks
#### Scenario: User toggles tasks`}
        fileName="spec.md"
        filePath="/openspec/changes/demo/specs/workspace-openspec-browser/spec.md"
      />,
    );

    await user.type(
      screen.getByPlaceholderText('搜尋 Requirement 或 Scenario'),
      'tasks',
    );

    expect(screen.queryByRole('button', { name: 'OpenSpec shall show specs' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'OpenSpec shall show tasks' })).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: '隱藏目錄' })[1]);

    expect(screen.queryByPlaceholderText('搜尋 Requirement 或 Scenario')).not.toBeInTheDocument();
  });

  it('renders contextual OpenSpec actions and inserts the focused change draft', async () => {
    const user = userEvent.setup();

    render(
      <MarkdownViewer
        content={`## 1. Navigation\n\n- [ ] 1.1 Add OpenSpec menu`}
        fileName="tasks.md"
        filePath="/openspec/changes/demo/tasks.md"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(setDraftMessageMock).toHaveBeenCalledWith('/opsx:apply demo');
  });
});
