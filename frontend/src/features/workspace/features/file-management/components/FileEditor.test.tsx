import React from 'react';
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

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      ui: {
        currentTheme: 'light',
      },
    },
  }),
}));

vi.mock('@monaco-editor/react', () => ({
  default: ({ onChange, value }: { onChange?: (value: string) => void; value?: string }) => (
    <textarea
      aria-label="code-editor"
      value={value ?? ''}
      onChange={(event) => onChange?.(event.target.value)}
    />
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

const createWorkspaceValue = (expanded = false, tabScope: 'file-management' | 'openspec' = 'file-management') => ({
  workspace: {
    tabScope,
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

  it('toggles editor expansion through the toolbar more menu', () => {
    const view = render(<FileEditor />);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    fireEvent.click(screen.getByText('shared.fileViewer.toolbar.expand'));

    expect(toggleFileManagementEditorExpandedMock).toHaveBeenCalledTimes(1);

    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));
    view.rerender(<FileEditor />);

    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    expect(screen.getByText('shared.fileViewer.toolbar.collapse')).toBeInTheDocument();
  });

  it('keeps active content and modified state visible while expanded', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getAllByText('App.tsx').length).toBeGreaterThan(0);
    expect(screen.getByText('shared.fileViewer.status.modified')).toBeInTheDocument();
    expect(screen.getByLabelText('code-editor')).toHaveValue('const value = 1;');
  });

  it('expands to the viewport when the editor is expanded', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    const { container } = render(<FileEditor />);

    expect(container.firstElementChild).toHaveClass('fixed', 'inset-0', 'h-screen', 'w-screen');
  });

  it('keeps the tab list visible when expanded', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getByLabelText('shared.fileViewer.toolbar.more')).toBeInTheDocument();
    expect(screen.getAllByText('App.tsx').length).toBeGreaterThan(0);
  });

  it('collapses automatically when the last tab is closed while expanded', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));
    const view = render(<FileEditor />);

    expect(toggleFileManagementEditorExpandedMock).not.toHaveBeenCalled();

    const expandedEmptyValue = createWorkspaceValue(true);
    expandedEmptyValue.workspace.openTabs = [];
    expandedEmptyValue.workspace.activeTabId = null;
    expandedEmptyValue.fileEditor.modifiedTabs = [];
    expandedEmptyValue.fileEditor.originalContents = {};
    useWorkspaceMock.mockReturnValue(expandedEmptyValue);
    view.rerender(<FileEditor />);

    expect(toggleFileManagementEditorExpandedMock).toHaveBeenCalledTimes(1);
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
