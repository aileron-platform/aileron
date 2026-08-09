import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { FileEditor } from './FileEditor';

type CapturedPane = {
  id: string;
  tabIds: string[];
  activeTabId: string | null;
};

let capturedOnPanesChange: ((panes: CapturedPane[]) => void) | undefined;
let capturedOnSizesChange: ((sizes: number[]) => void) | undefined;
let capturedPanes: CapturedPane[] | undefined;
let capturedSizes: number[] | undefined;
let capturedOnTextSelectionChange: React.ComponentProps<
  typeof import('@/shared/components/file-workbench/viewer-entry').FileViewerWorkbench
>['onTextSelectionChange'];

const {
  selectCodeReferenceMock,
  aiChatSelectionState,
  useWorkspaceMock,
  toggleFileManagementEditorExpandedMock,
} = vi.hoisted(() => ({
  selectCodeReferenceMock: vi.fn(),
  aiChatSelectionState: {
    canSelectCodeReference: true,
  },
  useWorkspaceMock: vi.fn(),
  toggleFileManagementEditorExpandedMock: vi.fn(),
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

vi.mock('../../../integrations/ai-chat/WorkspaceAiChatSelectionContext', () => ({
  useWorkspaceAiChatSelection: () => ({
    canSelectCodeReference: aiChatSelectionState.canSelectCodeReference,
    selectCodeReference: selectCodeReferenceMock,
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

vi.mock('@/shared/components/file-workbench/viewer-entry', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/file-workbench/viewer-entry')>();
  return {
    ...actual,
    FileViewerWorkbenchSplitView: ({
      panes,
      sizes,
      onPanesChange,
      onSizesChange,
      onTextSelectionChange,
      ...props
    }: {
      panes?: CapturedPane[];
      sizes?: number[];
      onPanesChange?: (panes: CapturedPane[]) => void;
      onSizesChange?: (sizes: number[]) => void;
    } & React.ComponentProps<typeof actual.FileViewerWorkbench>) => {
      capturedPanes = panes;
      capturedSizes = sizes;
      capturedOnPanesChange = onPanesChange;
      capturedOnSizesChange = onSizesChange;
      capturedOnTextSelectionChange = onTextSelectionChange;
      return (
        <actual.FileViewerWorkbench
          {...props}
          onTextSelectionChange={onTextSelectionChange}
        />
      );
    },
  };
});

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
  permissions: {
    canWrite: true,
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
    } as Record<string, string>,
    revisions: {
      '/src/App.tsx': 'version-1',
    } as Record<string, string | null | undefined>,
    updateTabContent: vi.fn(),
    setOriginalContent: vi.fn(),
    setFileRevision: vi.fn(),
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
    capturedOnPanesChange = undefined;
    capturedOnSizesChange = undefined;
    capturedPanes = undefined;
    capturedSizes = undefined;
    capturedOnTextSelectionChange = undefined;
    selectCodeReferenceMock.mockReset();
    aiChatSelectionState.canSelectCodeReference = true;
    localStorage.clear();
    useWorkspaceMock.mockReturnValue(createWorkspaceValue(false));
  });

  it('renders a localized expand control in the shared tab bar actions', () => {
    render(<FileEditor />);

    expect(screen.getByLabelText('shared.fileViewer.toolbar.expand')).toBeInTheDocument();
  });

  it('uses the shared empty state when no file is open', () => {
    useWorkspaceMock.mockReturnValue({
      ...createWorkspaceValue(false),
      workspace: {
        openTabs: [],
        activeTabId: null,
      },
    });

    render(<FileEditor />);

    const title = screen.getByText('workspace.fileManagement.editor.emptyState.title');
    expect(title).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
  });

  it('toggles editor expansion through the toolbar more menu', async () => {
    const user = userEvent.setup();
    const view = render(<FileEditor />);

    await user.click(screen.getByLabelText('shared.fileViewer.toolbar.expand'));

    expect(toggleFileManagementEditorExpandedMock).toHaveBeenCalledTimes(1);

    useWorkspaceMock.mockReturnValue(createWorkspaceValue(true));
    view.rerender(<FileEditor />);

    expect(screen.getByLabelText('shared.fileViewer.toolbar.collapse')).toBeInTheDocument();
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
    const user = userEvent.setup();
    const workspaceValue = createWorkspaceValue(false);
    useWorkspaceMock.mockReturnValue(workspaceValue);

    render(<FileEditor />);

    await user.click(screen.getByLabelText('shared.fileViewer.toolbar.save'));

    await waitFor(() => {
      expect(workspaceValue.fileTreeActions.saveFileContent).toHaveBeenCalledWith(
        '/src/App.tsx',
        'const value = 1;',
        'version-1',
      );
    });
    expect(workspaceValue.fileEditor.updateTabContent).toHaveBeenCalledWith('/src/App.tsx', 'const value = 1;');
    expect(workspaceValue.fileEditor.setOriginalContent).toHaveBeenCalledWith('/src/App.tsx', 'const value = 1;');
    expect(workspaceValue.fileEditor.setFileRevision).toHaveBeenCalledWith('/src/App.tsx', undefined);
    expect(workspaceValue.fileEditor.setTabModified).toHaveBeenCalledWith('/src/App.tsx', false);
  });

  it('saves content entered into an empty workspace file without reverting the edit', async () => {
    const workspaceValue = createWorkspaceValue(false);
    workspaceValue.workspace.openTabs[0].content = '';
    workspaceValue.fileEditor.originalContents['/src/App.tsx'] = '';
    workspaceValue.fileEditor.modifiedTabs = [];
    workspaceValue.fileEditor.updateTabContent.mockImplementation((path: string, content: string) => {
      const tab = workspaceValue.workspace.openTabs.find((item) => item.id === path);
      if (tab) {
        tab.content = content;
      }
    });
    workspaceValue.fileEditor.setTabModified.mockImplementation((path: string, isModified: boolean) => {
      workspaceValue.fileEditor.modifiedTabs = isModified
        ? Array.from(new Set([...workspaceValue.fileEditor.modifiedTabs, path]))
        : workspaceValue.fileEditor.modifiedTabs.filter((item) => item !== path);
    });
    useWorkspaceMock.mockReturnValue(workspaceValue);

    const view = render(<FileEditor />);
    fireEvent.change(screen.getByLabelText('code-editor'), {
      target: { value: 'name: workspace-agent' },
    });
    view.rerender(<FileEditor />);

    expect(screen.getByLabelText('code-editor')).toHaveValue('name: workspace-agent');
    fireEvent.click(screen.getByLabelText('shared.fileViewer.toolbar.save'));

    await waitFor(() => {
      expect(workspaceValue.fileTreeActions.saveFileContent).toHaveBeenCalledWith(
        '/src/App.tsx',
        'name: workspace-agent',
        'version-1',
      );
    });
  });

  it('syncs tab switching and reveal-in-tree through workspace selection', async () => {
    const user = userEvent.setup();
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

    await user.click(screen.getByLabelText('shared.fileViewer.toolbar.more'));
    await user.click(await screen.findByRole('menuitem', {
      name: 'shared.fileViewer.toolbar.revealInTree',
    }));

    expect(workspaceValue.fileTreeActions.selectFile).toHaveBeenCalledWith('/src/App.tsx');
  });

  it('opens AI Chat and forwards the selected file line range', () => {
    render(<FileEditor />);

    act(() => {
      capturedOnTextSelectionChange?.({
        filePath: '/src/App.tsx',
        fileName: 'App.tsx',
        startLine: 12,
        endLine: 18,
      });
    });

    expect(selectCodeReferenceMock).toHaveBeenCalledWith({
      filePath: '/src/App.tsx',
      fileName: 'App.tsx',
      startLine: 12,
      endLine: 18,
    });
  });

  it('does not attach a selection handler without AI Chat access', () => {
    aiChatSelectionState.canSelectCodeReference = false;

    render(<FileEditor />);

    expect(capturedOnTextSelectionChange).toBeUndefined();
    expect(selectCodeReferenceMock).not.toHaveBeenCalled();
  });

  it('persists split-view state to fileWorkbenchSplitStorage and restores it on remount', async () => {
    vi.useFakeTimers();

    try {
      const { unmount } = render(<FileEditor />);
      const panes = [
        { id: 'pane-a', tabIds: ['/src/App.tsx'], activeTabId: '/src/App.tsx' },
        { id: 'pane-b', tabIds: ['/src/Other.ts'], activeTabId: '/src/Other.ts' },
      ];

      await act(async () => {
        capturedOnPanesChange?.(panes);
        capturedOnSizesChange?.([50, 50]);
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(600);
      });
      expect(localStorage.getItem('file_workbench_split_ws-1')).not.toBeNull();

      unmount();
      render(<FileEditor />);
      await act(async () => {});

      expect(capturedPanes).toEqual(panes.map((pane, index) => ({
        ...pane,
        id: `restored-pane-${index}`,
      })));
      expect(capturedSizes).toEqual([50, 50]);
    } finally {
      vi.useRealTimers();
    }
  });
});
