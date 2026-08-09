import { act, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { VersionControlLfsDialog } from './VersionControlLfsDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params ? `${key}:${JSON.stringify(params)}` : key
    ),
  }),
}));

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  patterns: ['*.zip', '*.pdf'],
  onSavePatterns: vi.fn().mockResolvedValue(undefined),
  onPreview: vi.fn().mockResolvedValue({
    matchedTotal: 2,
    totalSize: 1536,
    pathSample: ['assets/demo.zip', 'docs/guide.pdf'],
  }),
  onConvert: vi.fn().mockResolvedValue(undefined),
  onCancel: vi.fn().mockResolvedValue(undefined),
};

describe('VersionControlLfsDialog', () => {
  it('normalizes pattern additions and saves one ordered, deduplicated list', async () => {
    const user = userEvent.setup();
    const onSavePatterns = vi.fn().mockResolvedValue(undefined);

    render(<VersionControlLfsDialog {...baseProps} onSavePatterns={onSavePatterns} />);

    const input = screen.getByLabelText('shared.versionControl.lfs.dialog.patterns.newLabel');
    await user.type(input, '  *.zip  ');
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.patterns.add',
    }));
    expect(screen.getAllByTestId('lfs-pattern-row')).toHaveLength(2);

    await user.clear(input);
    await user.type(input, '*.webp');
    await user.keyboard('{Enter}');
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.save',
    }));

    expect(onSavePatterns).toHaveBeenCalledWith(['*.zip', '*.pdf', '*.webp']);
  });

  it('previews impact without converting, then requires an explicit confirmation', async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn().mockResolvedValue({
      matchedTotal: 2,
      totalSize: 1536,
      pathSample: ['assets/demo.zip', 'docs/guide.pdf'],
    });
    const onConvert = vi.fn().mockResolvedValue(undefined);

    render(
      <VersionControlLfsDialog
        {...baseProps}
        onPreview={onPreview}
        onConvert={onConvert}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.preview',
    }));

    expect(await screen.findByText(
      'shared.versionControl.lfs.dialog.preview.matchedTotal:{"count":2}',
    )).toBeInTheDocument();
    expect(screen.getByText('assets/demo.zip')).toBeInTheDocument();
    expect(onConvert).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.prepareConversion',
    }));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(onConvert).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.confirm.confirm',
    }));
    expect(onConvert).toHaveBeenCalledWith(['assets/demo.zip', 'docs/guide.pdf']);
  });

  it('does not offer a partial conversion when the backend path sample is truncated', async () => {
    const user = userEvent.setup();
    render(
      <VersionControlLfsDialog
        {...baseProps}
        onPreview={vi.fn().mockResolvedValue({
          matchedTotal: 101,
          totalSize: 2048,
          pathSample: Array.from({ length: 100 }, (_, index) => `asset-${index}.zip`),
        })}
      />,
    );

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.preview',
    }));

    expect(await screen.findByText(
      'shared.versionControl.lfs.dialog.preview.truncated',
    )).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.prepareConversion',
    })).toBeDisabled();
  });

  it('shows shared operation progress and exposes cancellation state', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(
      <VersionControlLfsDialog
        {...baseProps}
        operationStatus={{
          isActive: true,
          operation: 'lfs_snapshot_convert',
          actorDisplayName: 'Developer',
          startedAt: '2026-08-01T00:00:00Z',
          blockingScope: 'working_tree_target',
          stale: false,
          retryable: false,
          progressCurrent: 3,
          progressTotal: 4,
          phase: 'renormalizing',
          cancellable: true,
          cancelRequested: false,
        }}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '75');
    expect(screen.getByText(
      'shared.versionControl.lfs.dialog.progress.count:{"current":3,"total":4}',
    )).toBeInTheDocument();

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.cancelOperation',
    }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    rerender(
      <VersionControlLfsDialog
        {...baseProps}
        operationStatus={{
          isActive: true,
          operation: 'lfs_snapshot_convert',
          actorDisplayName: 'Developer',
          startedAt: '2026-08-01T00:00:00Z',
          blockingScope: 'working_tree_target',
          stale: false,
          retryable: false,
          progressCurrent: 3,
          progressTotal: 4,
          phase: 'renormalizing',
          cancellable: true,
          cancelRequested: true,
        }}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByText(
      'shared.versionControl.lfs.dialog.progress.cancelRequested',
    )).toBeInTheDocument();
  });

  it('drops a stale preview response after the dialog identity changes', async () => {
    let resolvePreview: ((value: {
      matchedTotal: number;
      totalSize: number;
      pathSample: string[];
    }) => void) | undefined;
    const onPreview = vi.fn().mockImplementation(() => new Promise((resolve) => {
      resolvePreview = resolve;
    }));
    const user = userEvent.setup();
    const { rerender } = render(
      <VersionControlLfsDialog {...baseProps} requestIdentity="repo-a" onPreview={onPreview} />,
    );

    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.preview',
    }));
    rerender(
      <VersionControlLfsDialog {...baseProps} requestIdentity="repo-b" onPreview={onPreview} />,
    );
    await act(async () => {
      resolvePreview?.({ matchedTotal: 1, totalSize: 10, pathSample: ['stale.zip'] });
    });

    expect(screen.queryByText('stale.zip')).not.toBeInTheDocument();
  });

  it('keeps the dialog open during a request and shows a localized inline failure', async () => {
    let rejectSave: ((reason?: unknown) => void) | undefined;
    const onSavePatterns = vi.fn().mockImplementation(() => new Promise((_, reject) => {
      rejectSave = reject;
    }));
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <VersionControlLfsDialog
        {...baseProps}
        onOpenChange={onOpenChange}
        onSavePatterns={onSavePatterns}
      />,
    );

    const input = screen.getByLabelText('shared.versionControl.lfs.dialog.patterns.newLabel');
    await user.type(input, '*.webp');
    await user.keyboard('{Enter}');
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.lfs.dialog.actions.save',
    }));
    await user.click(screen.getByRole('button', { name: 'common.close' }));
    expect(onOpenChange).not.toHaveBeenCalledWith(false);

    await act(async () => rejectSave?.(new Error('SAVE_FAILED')));
    expect(screen.getByText(
      'shared.versionControl.lfs.dialog.errors.save',
    )).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('uses a viewport-safe setup dialog with fixed header and footer regions', () => {
    render(<VersionControlLfsDialog {...baseProps} />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-w-2xl', 'overflow-hidden');
    expect(dialog).toHaveClass('max-h-[calc(100vh-2rem)]', 'w-[calc(100vw-2rem)]');
    expect(screen.getByTestId('lfs-dialog-scroll-region')).toHaveClass('overflow-y-auto');
    expect(screen.getByTestId('lfs-dialog-footer')).toHaveClass('shrink-0');
  });
});
