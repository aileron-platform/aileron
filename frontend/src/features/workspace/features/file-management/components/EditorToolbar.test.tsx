import { beforeEach, describe, expect, it, vi } from 'vitest';
import type React from 'react';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { EditorToolbar } from './EditorToolbar';
import type { CodeEditorRef } from './CodeEditor';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  AlertDialogAction: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
  AlertDialogCancel: ({ children }: { children: React.ReactNode }) => <button>{children}</button>,
  AlertDialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const undoMock = vi.fn();
const redoMock = vi.fn();
const editorRef = {
  current: {
    undo: undoMock,
    redo: redoMock,
  } as Pick<CodeEditorRef, 'undo' | 'redo'> as CodeEditorRef,
};

const renderToolbar = () => render(
  <EditorToolbar
    activeTabId="/src/App.tsx"
    modifiedTabs={[]}
    editorRef={editorRef}
    onSave={vi.fn()}
    onSaveAll={vi.fn()}
    onRevert={vi.fn()}
    onRevertAll={vi.fn()}
    onCopyPath={vi.fn()}
    onRevealInTree={vi.fn()}
    onCloseAll={vi.fn()}
    onSaveAndCloseAll={vi.fn()}
    editorExpansionControl={<button aria-label="expand-slot" type="button" />}
  />,
);

describe('EditorToolbar', () => {
  beforeEach(() => {
    undoMock.mockReset();
    redoMock.mockReset();
  });

  it('places the editor expansion control immediately before the action menu', () => {
    renderToolbar();

    const expansionControl = screen.getByLabelText('expand-slot');
    const actionMenu = screen.getByTitle('workspace.fileManagement.editor.toolbar.more');

    expect(expansionControl.nextElementSibling).toBe(actionMenu);
  });

  it('keeps undo and redo inside the action menu', () => {
    renderToolbar();

    expect(screen.queryByText('workspace.fileManagement.editor.toolbar.undo')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.fileManagement.editor.toolbar.redo')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTitle('workspace.fileManagement.editor.toolbar.more'));

    fireEvent.click(screen.getByText('workspace.fileManagement.editor.toolbar.undo'));
    fireEvent.click(screen.getByTitle('workspace.fileManagement.editor.toolbar.more'));
    fireEvent.click(screen.getByText('workspace.fileManagement.editor.toolbar.redo'));

    expect(undoMock).toHaveBeenCalledTimes(1);
    expect(redoMock).toHaveBeenCalledTimes(1);
  });
});
