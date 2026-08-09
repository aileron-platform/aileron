import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ArchiveProgressOverlays, type ExtractProgressState } from './ArchiveProgressOverlays';
import type { ArchiveProgressState } from './archiveOperationModel';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => `${key}${params ? `:${JSON.stringify(params)}` : ''}`,
  }),
}));

const runningExtract: ExtractProgressState = {
  operationId: 'extract-1',
  archivePath: '/src/archive.zip',
  archiveName: 'archive.zip',
  status: 'running',
  progress: 0.42,
  message: 'Extracting files',
};

const completedArchive: ArchiveProgressState = {
  operationId: 'archive-1',
  archiveName: 'selection.zip',
  paths: ['/src'],
  status: 'completed',
  progress: 1,
  message: 'Ready',
  downloadUrl: '/download/archive-1',
};

describe('ArchiveProgressOverlays', () => {
  it('renders running extract progress with localized labels', () => {
    render(
      <ArchiveProgressOverlays
        extractProgress={runningExtract}
        archiveProgress={null}
        onArchiveDownload={vi.fn()}
      />,
    );

    expect(screen.getByText('shared.fileWorkbench.archive.extracting:{"name":"archive.zip"}')).toBeInTheDocument();
    expect(screen.getByText('shared.fileWorkbench.archive.progress:{"value":42}')).toBeInTheDocument();
    expect(screen.getByText('Extracting files')).toBeInTheDocument();
  });

  it('renders completed archive progress and dispatches download requests', () => {
    const onArchiveDownload = vi.fn();
    render(
      <ArchiveProgressOverlays
        extractProgress={null}
        archiveProgress={completedArchive}
        onArchiveDownload={onArchiveDownload}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'common.fileTree.contextMenu.download' }));

    expect(screen.getByText('shared.fileWorkbench.archive.ready')).toBeInTheDocument();
    expect(onArchiveDownload).toHaveBeenCalledWith({
      downloadUrl: '/download/archive-1',
      operationId: 'archive-1',
      archiveName: 'selection.zip',
    });
  });

  it('does not render extract progress for terminal states', () => {
    render(
      <ArchiveProgressOverlays
        extractProgress={{ ...runningExtract, status: 'completed' }}
        archiveProgress={null}
        onArchiveDownload={vi.fn()}
      />,
    );

    expect(screen.queryByText('Extracting files')).not.toBeInTheDocument();
  });
});
