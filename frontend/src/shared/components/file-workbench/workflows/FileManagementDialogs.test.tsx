import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import type { FileTreeNode } from '../types';
import { FileManagementDialogs } from './FileManagementDialogs';

vi.mock('../tree/FileOperationDialogs', () => ({
  FileCreateDialog: ({
    open,
    type,
  }: {
    open: boolean;
    type: string;
  }) => (open ? <div>{`create:${type}`}</div> : null),
  FileRenameDialog: ({
    open,
    currentName,
  }: {
    open: boolean;
    currentName: string;
  }) => (open ? <div>{`rename:${currentName}`}</div> : null),
  FileDeleteDialog: ({
    open,
    fileName,
    fileType,
  }: {
    open: boolean;
    fileName: string;
    fileType: string;
  }) => (open ? <div>{`delete:${fileName}:${fileType}`}</div> : null),
  BatchDeleteDialog: ({
    open,
    files,
  }: {
    open: boolean;
    files: Array<{ path: string }>;
  }) => (open ? <div>{`batch-delete:${files.map((file) => file.path).join(',')}`}</div> : null),
}));

const testNode: FileTreeNode = {
  id: '/docs/readme.md',
  name: 'readme.md',
  path: '/docs/readme.md',
  type: 'file',
};

describe('FileManagementDialogs', () => {
  it('renders the matching dialog for each shared dialog state', () => {
    const noop = vi.fn();

    const { rerender } = render(
      <FileManagementDialogs
        dialogState={{ type: 'create-folder', parentPath: '/docs' }}
        onClose={noop}
        onCreateFile={noop}
        onCreateFolder={noop}
        onRename={noop}
        onDelete={noop}
      />,
    );

    expect(screen.getByText('create:folder')).toBeInTheDocument();

    rerender(
      <FileManagementDialogs
        dialogState={{ type: 'rename', node: testNode }}
        onClose={noop}
        onCreateFile={noop}
        onCreateFolder={noop}
        onRename={noop}
        onDelete={noop}
      />,
    );

    expect(screen.getByText('rename:readme.md')).toBeInTheDocument();

    rerender(
      <FileManagementDialogs
        dialogState={{ type: 'delete', node: testNode }}
        onClose={noop}
        onCreateFile={noop}
        onCreateFolder={noop}
        onRename={noop}
        onDelete={noop}
      />,
    );

    expect(screen.getByText('delete:readme.md:file')).toBeInTheDocument();

    rerender(
      <FileManagementDialogs
        dialogState={{ type: 'batch-delete', nodes: [testNode] }}
        onClose={noop}
        onCreateFile={noop}
        onCreateFolder={noop}
        onRename={noop}
        onDelete={noop}
        onBatchDelete={noop}
      />,
    );

    expect(screen.getByText('batch-delete:/docs/readme.md')).toBeInTheDocument();
  });
});
