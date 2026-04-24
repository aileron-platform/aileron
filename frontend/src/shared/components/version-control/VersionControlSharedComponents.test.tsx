import { fireEvent, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  VersionControlCommitForm,
  VersionControlDiffContent,
  VersionControlFileChangeItem,
  VersionControlLayout,
  VersionControlResizablePanels,
} from './index';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const values: Record<string, string> = {
        'shared.versionControl.commitForm.placeholder': 'Commit message',
        'shared.versionControl.commitForm.submit': 'Commit',
        'shared.versionControl.commitForm.submitting': 'Committing...',
        'shared.versionControl.commitFiles.status.modified': 'Modified',
        'shared.versionControl.fileItem.stageTooltip': 'Stage file',
        'shared.versionControl.fileItem.unstageTooltip': 'Unstage file',
        'shared.versionControl.diff.empty': 'Select a file',
        'shared.versionControl.diff.noDifference': 'No differences',
        'shared.versionControl.diff.loading': 'Loading diff',
        'shared.versionControl.diff.loadFailed': 'Failed to load diff',
        'shared.versionControl.diff.binaryOrLarge': 'Unable to display file content',
        'shared.versionControl.diff.filePath': `File path: ${params?.path ?? ''}`,
      };
      return values[key] ?? key;
    },
  }),
}));

describe('shared version-control components', () => {
  it('submits commit messages through the neutral commit form', async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();

    render(<VersionControlCommitForm onCommit={onCommit} stagedCount={1} />);

    await user.type(screen.getByPlaceholderText('Commit message'), 'Update registry');
    await user.click(screen.getByRole('button', { name: 'Commit' }));

    expect(onCommit).toHaveBeenCalledWith({ message: 'Update registry' });
  });

  it('renders file change rows and stage actions without workspace context', async () => {
    const user = userEvent.setup();
    const onStageToggle = vi.fn();
    const onSelect = vi.fn();

    render(
      <VersionControlFileChangeItem
        file={{ name: 'README.md', path: 'templates/demo/README.md', status: 'M', additions: 1, deletions: 0 }}
        isSelected={false}
        isMultiSelected={false}
        type="unstaged"
        onSelect={onSelect}
        onStageToggle={onStageToggle}
        selectedCount={1}
      />,
    );

    await user.click(screen.getByTitle('Stage file'));

    expect(screen.getByText('README.md')).toBeInTheDocument();
    expect(onStageToggle).toHaveBeenCalled();
  });

  it('renders parsed diff content', () => {
    render(
      <VersionControlDiffContent
        selectedPath="templates/demo/README.md"
        diffContent={'@@ -1 +1 @@\n-old\n+new'}
      />,
    );

    expect(screen.getByText('old')).toBeInTheDocument();
    expect(screen.getByText('new')).toBeInTheDocument();
  });

  it('resizes version-control columns with drag handles', () => {
    render(
      <VersionControlLayout
        modeRail={<div>Modes</div>}
        sidebar={<div>Files</div>}
        main={<div>Diff</div>}
      />,
    );

    const modeRail = screen.getByTestId('version-control-mode-rail');
    const sidebar = screen.getByTestId('version-control-sidebar');
    const modeRailHandle = modeRail.querySelector('.cursor-col-resize') as HTMLElement;
    const sidebarHandle = sidebar.querySelector('.cursor-col-resize') as HTMLElement;

    expect(modeRail).toHaveStyle({ width: '192px' });
    expect(sidebar).toHaveStyle({ width: '320px' });

    fireEvent.mouseDown(modeRailHandle, { clientX: 200 });
    fireEvent.mouseMove(window, { clientX: 240 });
    fireEvent.mouseUp(window);

    fireEvent.mouseDown(sidebarHandle, { clientX: 400 });
    fireEvent.mouseMove(window, { clientX: 360 });
    fireEvent.mouseUp(window);

    expect(modeRail).toHaveStyle({ width: '232px' });
    expect(sidebar).toHaveStyle({ width: '280px' });
  });

  it('resizes stacked file panels with the shared row handle', () => {
    render(
      <div style={{ height: 400 }}>
        <VersionControlResizablePanels top={<div>Staged</div>} bottom={<div>Unstaged</div>} />
      </div>,
    );

    const stagedPanel = screen.getByText('Staged').parentElement as HTMLElement;
    const container = stagedPanel.parentElement as HTMLElement;
    const resizeHandle = stagedPanel.nextElementSibling as HTMLElement;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({
      x: 0,
      y: 0,
      width: 300,
      height: 400,
      top: 0,
      right: 300,
      bottom: 400,
      left: 0,
      toJSON: () => ({}),
    });

    expect(stagedPanel).toHaveStyle({ height: '50%' });

    fireEvent.mouseDown(resizeHandle, { clientY: 200 });
    fireEvent.mouseMove(window, { clientY: 240 });
    fireEvent.mouseUp(window);

    expect(stagedPanel).toHaveStyle({ height: '60%' });
  });
});
