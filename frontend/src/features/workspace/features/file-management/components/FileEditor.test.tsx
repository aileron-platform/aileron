import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import { FileEditor } from './FileEditor';

const { useWorkspaceMock, toggleFileManagementEditorExpandedMock, fileTypeState } = vi.hoisted(() => ({
  useWorkspaceMock: vi.fn(),
  toggleFileManagementEditorExpandedMock: vi.fn(),
  fileTypeState: {
    markdown: false,
    mermaid: false,
    drawio: false,
    image: false,
  },
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => useWorkspaceMock(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/shared/components/file-viewer-workbench/CodeTextEditor', () => ({
  CodeTextEditor: ({ content, onContentChange }: { content: string; onContentChange: (content: string) => void }) => (
    <textarea
      aria-label="code-editor"
      value={content}
      onChange={(event) => onContentChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/file-viewer-workbench/SharedMarkdownViewer', () => ({
  SharedMarkdownViewer: ({ isFocusMode }: { isFocusMode?: boolean }) => (
    <div data-focus-mode={String(Boolean(isFocusMode))} data-testid="markdown-viewer" />
  ),
}));

vi.mock('@/shared/utils/fileIconUtils', () => ({
  getFileIcon: () => null,
  getFileLanguage: () => 'TypeScript',
  isMermaidFile: () => fileTypeState.mermaid,
  isMarkdownFile: () => fileTypeState.markdown,
  isDrawioFile: () => fileTypeState.drawio,
}));

vi.mock('@/shared/utils/fileTypeUtils', () => ({
  formatFileSize: (size: number) => `${size} B`,
  isImageFile: () => fileTypeState.image,
}));

const createWorkspaceValue = (expanded = false) => ({
  workspace: {
    openTabs: [
      {
        id: '/src/App.tsx',
        name: 'App.tsx',
        path: '/src/App.tsx',
        content: 'const value = 1;',
      },
    ],
    activeTabId: '/src/App.tsx',
  },
  workspaceRuntime: {
    workspaceId: 'ws-1',
    runtimeBaseUrl: 'http://runtime.local',
  },
  layout: {
    fileManagementEditorExpanded: expanded,
  },
  closeTab: vi.fn(),
  switchToTab: vi.fn(),
  closeAllTabs: vi.fn(),
  fileTreeActions: {
    readFileContent: vi.fn(),
    saveFileContent: vi.fn().mockResolvedValue({ success: true }),
    selectFile: vi.fn(),
  },
  fileEditor: {
    modifiedTabs: ['/src/App.tsx'],
    originalContents: {
      '/src/App.tsx': 'const value = 0;',
    },
    updateTabContent: vi.fn(),
    setOriginalContent: vi.fn(),
    setTabModified: vi.fn(),
    saveFile: vi.fn(),
    saveAllFiles: vi.fn(),
    revertFile: vi.fn(() => ({ success: true })),
    revertAllFiles: vi.fn(() => ({ success: true, failed: [] })),
  },
  toggleFileManagementEditorExpanded: toggleFileManagementEditorExpandedMock,
});

describe('FileEditor editor-pane expansion', () => {
  beforeEach(() => {
    useWorkspaceMock.mockReset();
    toggleFileManagementEditorExpandedMock.mockReset();
    fileTypeState.markdown = false;
    fileTypeState.mermaid = false;
    fileTypeState.drawio = false;
    fileTypeState.image = false;
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(false));
  });

  it('renders a localized expand control in the shared action menu', () => {
    render(<FileEditor />);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));

    expect(screen.getByText('shared.fileViewer.toolbar.expand')).toBeInTheDocument();
  });

  it('toggles file focus mode and reflects the focused code toolbar', () => {
    const view = render(<FileEditor />);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.expand'));

    expect(toggleFileManagementEditorExpandedMock).toHaveBeenCalledTimes(1);

    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));
    view.rerender(<FileEditor />);

    expect(screen.getByLabelText('workspace.fileManagement.focus.exit')).toBeInTheDocument();
    expect(screen.queryByText('shared.fileViewer.toolbar.expand')).not.toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
  });

  it('keeps active content and modified state visible while focused', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getAllByText('App.tsx').length).toBeGreaterThan(0);
    expect(screen.getByText('shared.fileViewer.status.modified')).toBeInTheDocument();
    expect(screen.getByLabelText('code-editor')).toHaveValue('const value = 1;');
  });

  it('passes focus mode to specialized viewers and hides file tabs', () => {
    fileTypeState.markdown = true;
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getByTestId('markdown-viewer')).toHaveAttribute('data-focus-mode', 'true');
    expect(screen.queryByLabelText('shared.fileViewer.toolbar.more')).not.toBeInTheDocument();
  });

  it('saves the active tab through the workspace adapter and clears modified state', async () => {
    const workspaceValue = createWorkspaceValue(false);
    useWorkspaceMock.mockReturnValue(workspaceValue);

    render(<FileEditor />);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.save'));

    await waitFor(() => {
      expect(workspaceValue.fileTreeActions.saveFileContent).toHaveBeenCalledWith(
        '/src/App.tsx',
        'const value = 1;',
      );
    });
    expect(workspaceValue.fileEditor.updateTabContent).toHaveBeenCalledWith('/src/App.tsx', 'const value = 1;');
    expect(workspaceValue.fileEditor.setOriginalContent).toHaveBeenCalledWith('/src/App.tsx', 'const value = 1;');
    expect(workspaceValue.fileEditor.setTabModified).toHaveBeenCalledWith('/src/App.tsx', false);
  });

  it('syncs tab switching and reveal-in-tree through workspace selection', () => {
    const workspaceValue = createWorkspaceValue(false);
    workspaceValue.workspace.openTabs.push({
      id: '/src/Other.ts',
      name: 'Other.ts',
      path: '/src/Other.ts',
      content: 'const other = 1;',
    });
    useWorkspaceMock.mockReturnValue(workspaceValue);

    render(<FileEditor />);

    fireEvent.click(screen.getByText('Other.ts'));

    expect(workspaceValue.switchToTab).toHaveBeenCalledWith('/src/Other.ts');
    expect(workspaceValue.fileTreeActions.selectFile).toHaveBeenCalledWith('/src/Other.ts');

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.revealInTree'));

    expect(workspaceValue.fileTreeActions.selectFile).toHaveBeenCalledWith('/src/App.tsx');
  });
});
