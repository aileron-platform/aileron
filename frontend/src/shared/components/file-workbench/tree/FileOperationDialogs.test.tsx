import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
} from './FileOperationDialogs';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string | number>) => {
      if (key === 'common.fileOperations.batchDelete.summary') {
        return `delete ${values?.count} items`;
      }

      if (key === 'common.fileOperations.batchDelete.fileCount') {
        return `${values?.count} files`;
      }

      if (key === 'common.fileOperations.batchDelete.folderCount') {
        return `${values?.count} folders`;
      }

      if (key === 'common.fileOperations.delete.unsavedTabs') {
        return `${values?.count} unsaved tabs affected`;
      }

      if (key === 'common.fileOperations.validation.nameExists') {
        return `${values?.name} already exists`;
      }

      return key;
    },
  }),
}));

describe('File name conflict dialogs', () => {
  it('keeps create open with the original input and a localized conflict', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FileCreateDialog
        open
        type="file"
        onClose={onClose}
        onConfirm={vi.fn().mockRejectedValue({
          detail: { errorCode: 'FILE_ALREADY_EXISTS' },
        })}
      />,
    );

    const input = screen.getByRole('textbox');
    await user.type(input, 'notes.md');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    expect(input).toHaveValue('notes.md');
    expect(screen.getByText('notes.md already exists')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('keeps rename open with the proposed name and a localized conflict', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FileRenameDialog
        open
        currentName="draft.md"
        onClose={onClose}
        onConfirm={vi.fn().mockRejectedValue({
          errorCode: 'FILE_ALREADY_EXISTS',
        })}
      />,
    );

    const input = screen.getByRole('textbox');
    await user.clear(input);
    await user.type(input, 'notes.md');
    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.confirm' }));

    expect(input).toHaveValue('notes.md');
    expect(screen.getByText('notes.md already exists')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('BatchDeleteDialog', () => {
  it('keeps long file paths on one line inside a horizontally scrollable list', () => {
    const longPath =
      '/.aileron/canvases/2026-05-19-quarterly-product-roadmap/state/deeply-nested-output-folder-with-a-very-long-generated-name/state.json';

    render(
      <BatchDeleteDialog
        open
        files={[
          {
            name: 'state.json',
            path: longPath,
            type: 'file',
          },
          {
            name: 'generated-output',
            path: '/.aileron/canvases/2026-05-19-quarterly-product-roadmap/generated-output',
            type: 'directory',
          },
        ]}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-h-[min(90vh,640px)]', 'max-w-md', 'overflow-hidden');

    const pathText = within(dialog).getByText(longPath);
    expect(pathText).toHaveClass('whitespace-nowrap');
    expect(pathText).toHaveAttribute('title', longPath);

    const scrollContainer = pathText.closest('.overflow-auto');
    expect(scrollContainer).toHaveClass('overflow-auto');
    expect(pathText.closest('.min-w-max')).toHaveClass('min-w-max');
  });

  it('keeps batch delete open with inline failure details', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <BatchDeleteDialog
        open
        files={[{ name: 'broken.md', path: '/docs/broken.md', type: 'file' }]}
        affectedUnsavedTabsCount={2}
        onClose={onClose}
        onConfirm={vi.fn().mockRejectedValue(new Error('delete failed'))}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'common.fileOperations.batchDelete.deleteAll' }));

    expect(screen.getByText('delete failed')).toBeInTheDocument();
    expect(screen.getByText('2 unsaved tabs affected')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('keeps a single delete dialog open on failure and reports its path', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FileDeleteDialog
        open
        fileName="broken.md"
        filePath="/docs/broken.md"
        fileType="file"
        affectedUnsavedTabsCount={1}
        onClose={onClose}
        onConfirm={vi.fn().mockRejectedValue(new Error('delete failed'))}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'common.fileOperations.buttons.delete' }));

    expect(screen.getByText('/docs/broken.md')).toBeInTheDocument();
    expect(screen.getByText('delete failed')).toBeInTheDocument();
    expect(screen.getByText('1 unsaved tabs affected')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
