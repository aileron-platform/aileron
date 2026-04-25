import { beforeEach, describe, expect, it, vi } from 'vitest';
import type React from 'react';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
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

vi.mock('./EditorToolbar', () => ({
  EditorToolbar: ({ editorExpansionControl }: { editorExpansionControl?: React.ReactNode }) => (
    <div data-testid="editor-toolbar">
      {editorExpansionControl}
      <button aria-label="workspace.fileManagement.editor.toolbar.more" type="button" />
    </div>
  ),
}));

vi.mock('./CodeEditor', () => ({
  CodeEditor: ({ content, onContentChange }: { content: string; onContentChange: (content: string) => void }) => (
    <textarea
      aria-label="code-editor"
      value={content}
      onChange={(event) => onContentChange(event.target.value)}
    />
  ),
}));

vi.mock('./MermaidViewer', () => ({
  MermaidViewer: ({ isFocusMode }: { isFocusMode?: boolean }) => (
    <div data-focus-mode={String(Boolean(isFocusMode))} data-testid="mermaid-viewer" />
  ),
}));

vi.mock('./MarkdownViewer', () => ({
  MarkdownViewer: ({ isFocusMode }: { isFocusMode?: boolean }) => (
    <div data-focus-mode={String(Boolean(isFocusMode))} data-testid="markdown-viewer" />
  ),
}));

vi.mock('./ImageViewer', () => ({
  ImageViewer: ({ isFocusMode }: { isFocusMode?: boolean }) => (
    <div data-focus-mode={String(Boolean(isFocusMode))} data-testid="image-viewer" />
  ),
}));

vi.mock('./DrawioViewer', () => ({
  DrawioViewer: ({ isFocusMode }: { isFocusMode?: boolean }) => (
    <div data-focus-mode={String(Boolean(isFocusMode))} data-testid="drawio-viewer" />
  ),
}));

vi.mock('../utils/fileIconUtils', () => ({
  getFileIcon: () => null,
  getFileLanguage: () => 'TypeScript',
  isMermaidFile: () => fileTypeState.mermaid,
  isMarkdownFile: () => fileTypeState.markdown,
  isDrawioFile: () => fileTypeState.drawio,
}));

vi.mock('../utils/fileTypeUtils', () => ({
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
    selectFile: vi.fn(),
  },
  fileEditor: {
    modifiedTabs: ['/src/App.tsx'],
    originalContents: {
      '/src/App.tsx': 'const value = 0;',
    },
    updateTabContent: vi.fn(),
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

  it('renders a localized expand control in the file tab area', () => {
    render(<FileEditor />);

    expect(screen.getByLabelText('workspace.fileManagement.focus.enter')).toBeInTheDocument();
  });

  it('toggles file focus mode and reflects the focused code toolbar', () => {
    const view = render(<FileEditor />);

    fireEvent.click(screen.getByLabelText('workspace.fileManagement.focus.enter'));

    expect(toggleFileManagementEditorExpandedMock).toHaveBeenCalledTimes(1);

    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));
    view.rerender(<FileEditor />);

    expect(screen.getByLabelText('workspace.fileManagement.focus.exit')).toBeInTheDocument();
    expect(screen.queryByTestId('editor-toolbar')).not.toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
  });

  it('keeps active content and modified state visible while focused', () => {
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getAllByText('App.tsx').length).toBeGreaterThan(0);
    expect(screen.getByText('workspace.fileManagement.editor.status.modified')).toBeInTheDocument();
    expect(screen.getByLabelText('code-editor')).toHaveValue('const value = 1;');
  });

  it('passes focus mode to specialized viewers and hides file tabs', () => {
    fileTypeState.markdown = true;
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));

    render(<FileEditor />);

    expect(screen.getByTestId('markdown-viewer')).toHaveAttribute('data-focus-mode', 'true');
    expect(screen.queryByTestId('editor-toolbar')).not.toBeInTheDocument();
  });
});
