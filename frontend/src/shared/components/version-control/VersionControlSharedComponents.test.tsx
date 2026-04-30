import { fireEvent, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  VersionControlCommitForm,
  VersionControlCreateBranchDialog,
  VersionControlDiffContent,
  VersionControlFileChangeItem,
  VersionControlLayout,
  VersionControlRemoteSettingsDialog,
  VersionControlResizablePanels,
} from './index';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const values: Record<string, string> = {
        'shared.versionControl.commitForm.placeholder': 'Commit message',
        'shared.versionControl.commitForm.submit': 'Commit',
        'shared.versionControl.commitForm.submitting': 'Committing...',
        'shared.versionControl.branchDialog.title': 'Create branch',
        'shared.versionControl.branchDialog.description': 'Create a branch.',
        'shared.versionControl.branchDialog.namePlaceholder': 'Branch name',
        'shared.versionControl.branchDialog.nameLabel': 'Branch name',
        'shared.versionControl.branchDialog.startPointPlaceholder': 'Start point',
        'shared.versionControl.branchDialog.startPointLabel': 'Start point',
        'shared.versionControl.branchDialog.stashChanges': 'Stash local changes',
        'shared.versionControl.branchDialog.cancel': 'Cancel',
        'shared.versionControl.branchDialog.create': 'Create branch',
        'shared.versionControl.branchDialog.creating': 'Creating...',
        'shared.versionControl.remoteDialog.title': 'Remote settings',
        'shared.versionControl.remoteDialog.description': 'Configure remote settings.',
        'shared.versionControl.remoteDialog.initialized.title': 'Repository initialized',
        'shared.versionControl.remoteDialog.initialized.branch': `Branch: ${params?.branch ?? ''}`,
        'shared.versionControl.remoteDialog.initialized.noBranch': 'No branch',
        'shared.versionControl.remoteDialog.remote.missingOrigin': 'No origin remote',
        'shared.versionControl.remoteDialog.remote.urlLabel': 'Remote URL',
        'shared.versionControl.remoteDialog.remote.urlPlaceholder': 'git@example.com:repo.git',
        'shared.versionControl.remoteDialog.remote.helper': 'Saved as origin.',
        'shared.versionControl.remoteDialog.remote.actions.save': 'Save remote',
        'shared.versionControl.remoteDialog.remote.actions.saving': 'Saving...',
        'shared.versionControl.remoteDialog.setup.localContentWarning': 'Local content exists.',
        'shared.versionControl.remoteDialog.setup.actions.init': 'Initialize repository',
        'shared.versionControl.remoteDialog.setup.actions.initializing': 'Initializing...',
        'shared.versionControl.remoteDialog.clone.urlLabel': 'Repository URL',
        'shared.versionControl.remoteDialog.clone.branchLabel': 'Branch',
        'shared.versionControl.remoteDialog.clone.branchPlaceholder': 'main',
        'shared.versionControl.remoteDialog.clone.branchHelper': 'Leave blank.',
        'shared.versionControl.remoteDialog.clone.helper': 'Clone repository.',
        'shared.versionControl.remoteDialog.clone.disabledHelper': 'Clone disabled.',
        'shared.versionControl.remoteDialog.clone.actions.clone': 'Clone repository',
        'shared.versionControl.remoteDialog.clone.actions.cloning': 'Cloning...',
        'shared.versionControl.commitFiles.status.modified': 'Modified',
        'shared.versionControl.fileItem.stageTooltip': 'Stage file',
        'shared.versionControl.fileItem.unstageTooltip': 'Unstage file',
        'shared.versionControl.fileItem.stage': 'Stage',
        'shared.versionControl.fileItem.unstage': 'Unstage',
        'shared.versionControl.fileItem.discard': 'Discard changes',
        'shared.versionControl.fileItem.selectedCount': `${params?.count ?? 0} files selected`,
        'shared.versionControl.fileItem.stageMultiple': `Stage ${params?.count ?? 0} files`,
        'shared.versionControl.fileItem.unstageMultiple': `Unstage ${params?.count ?? 0} files`,
        'shared.versionControl.fileItem.discardMultiple': `Discard changes for ${params?.count ?? 0} files`,
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

  it('opens multi-file context actions for selected rows', async () => {
    const user = userEvent.setup();
    const onStageToggle = vi.fn();

    render(
      <VersionControlFileChangeItem
        file={{ name: 'README.md', path: 'templates/demo/README.md', status: 'M' }}
        isSelected
        isMultiSelected
        type="unstaged"
        onSelect={vi.fn()}
        onStageToggle={onStageToggle}
        selectedCount={2}
      />,
    );

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('README.md') });
    expect(screen.getByText('2 files selected')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Stage 2 files' }));

    expect(onStageToggle).toHaveBeenCalledWith(expect.objectContaining({ path: 'templates/demo/README.md' }));
  });

  it('selects an unselected row before opening its context menu', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <VersionControlFileChangeItem
        file={{ name: 'staged.md', path: 'templates/demo/staged.md', status: 'M' }}
        isSelected={false}
        isMultiSelected={false}
        type="staged"
        onSelect={onSelect}
        onStageToggle={vi.fn()}
        selectedCount={1}
      />,
    );

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('staged.md') });

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ path: 'templates/demo/staged.md' }),
      'staged',
    );
    expect(screen.getByRole('button', { name: 'Unstage' })).toBeInTheDocument();
  });

  it('submits branch creation payloads through the shared dialog', async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();

    render(
      <VersionControlCreateBranchDialog
        open
        onOpenChange={vi.fn()}
        onCreate={onCreate}
        supportsStartPoint
        supportsStashBeforeCheckout
      />,
    );

    await user.type(screen.getByLabelText('Branch name'), 'feature/shared');
    await user.type(screen.getByLabelText('Start point'), 'origin/main');
    await user.click(screen.getByText('Stash local changes'));
    await user.click(screen.getByRole('button', { name: 'Create branch' }));

    expect(onCreate).toHaveBeenCalledWith({
      branch: 'feature/shared',
      startPoint: 'origin/main',
      stashChanges: true,
    });
  });

  it('submits remote settings through capability-driven controls', async () => {
    const user = userEvent.setup();
    const onSaveRemoteUrl = vi.fn();

    render(
      <VersionControlRemoteSettingsDialog
        open
        onOpenChange={vi.fn()}
        repository={{
          isRepositoryInitialized: true,
          currentBranch: 'main',
          remoteUrl: '',
          hasOrigin: false,
        }}
        capabilities={{ canConfigureRemote: true }}
        onSaveRemoteUrl={onSaveRemoteUrl}
      />,
    );

    await user.type(screen.getByLabelText('Remote URL'), 'git@example.com:repo.git');
    await user.click(screen.getByRole('button', { name: 'Save remote' }));

    expect(onSaveRemoteUrl).toHaveBeenCalledWith('git@example.com:repo.git');
  });

  it('submits clone setup only when clone capability is enabled', async () => {
    const user = userEvent.setup();
    const onCloneRepository = vi.fn();
    const onInitRepository = vi.fn();

    render(
      <VersionControlRemoteSettingsDialog
        open
        onOpenChange={vi.fn()}
        repository={{
          isRepositoryInitialized: false,
          hasLocalContent: false,
          canCloneSafely: true,
          canInitSafely: true,
        }}
        capabilities={{ supportsRemoteClone: true, supportsRemoteInit: true }}
        onCloneRepository={onCloneRepository}
        onInitRepository={onInitRepository}
      />,
    );

    await user.type(screen.getByLabelText('Repository URL'), 'git@example.com:repo.git');
    await user.type(screen.getByLabelText('Branch'), 'main');
    await user.click(screen.getByRole('button', { name: 'Clone repository' }));

    expect(onCloneRepository).toHaveBeenCalledWith('git@example.com:repo.git', 'main');

    await user.click(screen.getByRole('button', { name: 'Initialize repository' }));
    expect(onInitRepository).toHaveBeenCalled();
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
