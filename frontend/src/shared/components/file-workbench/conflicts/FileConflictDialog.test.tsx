import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FileConflictDialog } from './FileConflictDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values ? `${key}:${JSON.stringify(values)}` : key
    ),
  }),
}));

const conflicts = [
  {
    sourcePath: 'draft.md',
    targetPath: '/docs/draft.md',
    sourceType: 'file' as const,
    targetType: 'file' as const,
    canReplace: true,
  },
  {
    sourcePath: 'assets',
    targetPath: '/docs/assets',
    sourceType: 'directory' as const,
    targetType: 'file' as const,
    canReplace: false,
  },
];

const renderDialog = (overrides: Partial<React.ComponentProps<typeof FileConflictDialog>> = {}) => {
  const props: React.ComponentProps<typeof FileConflictDialog> = {
    open: true,
    operation: 'upload',
    conflicts,
    defaultStrategy: 'keep-both',
    itemStrategies: {},
    pending: false,
    error: null,
    onDefaultStrategyChange: vi.fn(),
    onItemStrategyChange: vi.fn(),
    onCancel: vi.fn(),
    onConfirm: vi.fn(),
    ...overrides,
  };
  render(<FileConflictDialog {...props} />);
  return props;
};

describe('FileConflictDialog', () => {
  it('uses the bounded setup-dialog shell and one scrollable conflict list', () => {
    renderDialog();

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-w-2xl', 'grid-rows-[auto_minmax(0,1fr)_auto]', 'p-0');
    expect(dialog).toHaveClass('max-h-[calc(100vh-2rem)]', 'w-[calc(100vw-2rem)]');
    expect(screen.getByTestId('file-conflict-list')).toHaveClass('min-h-0', 'overflow-y-auto');
    expect(screen.getByText('/docs/draft.md')).toBeInTheDocument();
    expect(screen.getByText('/docs/assets')).toBeInTheDocument();
  });

  it('disables Replace globally and per item when a type conflict cannot be replaced', () => {
    renderDialog();

    expect(screen.getByRole('radio', {
      name: 'shared.fileWorkbench.conflict.strategy.replace.label',
    })).toBeDisabled();

    const assetsRow = screen.getByText('/docs/assets').closest('[data-conflict-row]');
    expect(assetsRow).not.toBeNull();
    const itemSelect = within(assetsRow!).getByRole('combobox');
    fireEvent.click(itemSelect);
    expect(screen.getByRole('option', {
      name: 'shared.fileWorkbench.conflict.strategy.replace.label',
    })).toHaveAttribute('data-disabled');
    expect(within(assetsRow!).getByText(
      /shared.fileWorkbench.conflict.replaceUnavailable.typeMismatch/,
    )).toHaveAttribute('id');
    expect(itemSelect).toHaveAttribute('aria-describedby');
  });

  it('reports apply-all and per-item changes through controlled callbacks', () => {
    const props = renderDialog({ conflicts: [conflicts[0]] });

    fireEvent.click(screen.getByRole('radio', {
      name: 'shared.fileWorkbench.conflict.strategy.skip.label',
    }));
    expect(props.onDefaultStrategyChange).toHaveBeenCalledWith('skip');

    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.click(screen.getByRole('option', {
      name: 'shared.fileWorkbench.conflict.strategy.replace.label',
    }));
    expect(props.onItemStrategyChange).toHaveBeenCalledWith('draft.md', 'replace');
  });

  it('cancels the whole batch and preserves pending or failed execution state', () => {
    const props = renderDialog({ pending: true, error: new Error('offline') });

    expect(screen.getByText('shared.fileWorkbench.conflict.error.execute')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'shared.fileWorkbench.conflict.actions.cancelBatch',
    })).toBeDisabled();
    expect(screen.getByRole('button', {
      name: 'shared.fileWorkbench.conflict.actions.processing',
    })).toBeDisabled();

    const readyProps = renderDialog();
    const cancelButtons = screen.getAllByRole('button', {
      name: 'shared.fileWorkbench.conflict.actions.cancelBatch',
    });
    fireEvent.click(cancelButtons.at(-1)!);
    expect(props.onCancel).not.toHaveBeenCalled();
    expect(readyProps.onCancel).toHaveBeenCalledTimes(1);
  });
});
