import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { FileTreeToolbar } from './FileTreeToolbar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('FileTreeToolbar', () => {
  it('does not render the toolbar row in read-only mode', () => {
    const { container } = render(
      <FileTreeToolbar
        isReadOnly
        leftContent={<div>scope-content</div>}
        rightContent={<button type="button">right-action</button>}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders primary and custom actions on the left with the action menu on the far right', () => {
    render(
      <FileTreeToolbar
        onCreateFile={vi.fn()}
        onCreateFolder={vi.fn()}
        onUpload={vi.fn()}
        rightContent={<button type="button">right-action</button>}
      />,
    );

    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFile' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.createFolder' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.contextMenu.upload' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.fileTree.contextMenu.refresh' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.fileTree.toolbar.moreActions' })).toBeInTheDocument();

    expect(
      screen.getByRole('button', { name: 'common.fileTree.contextMenu.upload' })
        .compareDocumentPosition(screen.getByRole('button', { name: 'right-action' })),
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(
      screen.getByRole('button', { name: 'right-action' })
        .compareDocumentPosition(screen.getByRole('button', { name: 'common.fileTree.toolbar.moreActions' })),
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
