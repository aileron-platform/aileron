import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BatchDeleteDialog } from './FileOperationDialogs';

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

      return key;
    },
  }),
}));

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
    expect(dialog).toHaveClass('max-h-[min(90vh,640px)]', 'overflow-hidden');

    const pathText = within(dialog).getByText(longPath);
    expect(pathText).toHaveClass('whitespace-nowrap');
    expect(pathText).toHaveAttribute('title', longPath);

    const scrollContainer = pathText.closest('.overflow-auto');
    expect(scrollContainer).toHaveClass('overflow-auto');
    expect(pathText.closest('.min-w-max')).toHaveClass('min-w-max');
  });
});
