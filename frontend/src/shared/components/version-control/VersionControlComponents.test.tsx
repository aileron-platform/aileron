import { fireEvent, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import {
  VersionControlCommitForm,
  VersionControlChangesSidebar,
  VersionControlCreateBranchDialog,
  VersionControlDiffContent,
  VersionControlFileChangeItem,
  VersionControlRemoteSettingsDialog,
  VersionControlRepositorySetup,
  VersionControlResizablePanels,
} from './index';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      const values: Record<string, string> = {
        'shared.versionControl.commitForm.placeholder': 'Commit message',
        'shared.versionControl.commitForm.submit': 'Commit',
        'shared.versionControl.commitForm.submitting': 'Committing...',
        'shared.versionControl.fileChanges.stagedTitle': 'Staged changes',
        'shared.versionControl.fileChanges.unstagedTitle': 'Unstaged changes',
        'shared.versionControl.fileChanges.stageAllTooltip': 'Stage all files',
        'shared.versionControl.fileChanges.unstageAllTooltip': 'Unstage all files',
        'shared.versionControl.fileChanges.empty': 'No file changes',
        'shared.versionControl.branchDialog.title': 'Create branch',
        'shared.versionControl.branchDialog.description': 'Create a branch.',
        'shared.versionControl.branchDialog.namePlaceholder': 'Branch name',
        'shared.versionControl.branchDialog.nameLabel': 'Branch name',
        'shared.versionControl.branchDialog.startPointPlaceholder': 'Start point',
        'shared.versionControl.branchDialog.startPointLabel': 'Start point',
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
        'shared.versionControl.repositorySetup.title': 'Version control is not set up',
        'shared.versionControl.repositorySetup.description': 'Initialize a repository or clone an existing one.',
        'shared.versionControl.repositorySetup.actions.init': 'Initialize Git',
        'shared.versionControl.repositorySetup.actions.initializing': 'Initializing...',
        'shared.versionControl.repositorySetup.actions.clone': 'Clone repository',
        'shared.versionControl.repositorySetup.dialog.title': 'Clone repository',
        'shared.versionControl.repositorySetup.dialog.description': 'Select a remote repository and branch.',
        'shared.versionControl.repositorySetup.localContentWarning': 'Local content exists.',
        'shared.versionControl.repositorySetup.clone.urlLabel': 'Repository URL',
        'shared.versionControl.repositorySetup.clone.urlPlaceholder': 'git@example.com:repo.git',
        'shared.versionControl.repositorySetup.clone.branchLabel': 'Branch',
        'shared.versionControl.repositorySetup.clone.branchPlaceholder': 'Select a branch',
        'shared.versionControl.repositorySetup.clone.branchHelper': 'Default branch selected.',
        'shared.versionControl.repositorySetup.clone.branchesEmpty': 'No branches.',
        'shared.versionControl.repositorySetup.clone.helper': 'Clone repository.',
        'shared.versionControl.repositorySetup.clone.disabledHelper': 'Clone disabled.',
        'shared.versionControl.repositorySetup.clone.actions.loadBranches': 'Load branches',
        'shared.versionControl.repositorySetup.clone.actions.loadingBranches': 'Loading...',
        'shared.versionControl.repositorySetup.clone.actions.cloning': 'Cloning...',
        'shared.versionControl.repositorySetup.errors.init': 'Unable to initialize repository.',
        'shared.versionControl.repositorySetup.errors.clone': 'Unable to clone repository.',
        'shared.versionControl.repositorySetup.errors.discovery': 'Unable to load branches.',
        'shared.versionControl.repositorySetup.errors.title': 'Setup failed',
        'shared.versionControl.repositorySetup.sshKeyRequired.title': 'SSH key required',
        'shared.versionControl.repositorySetup.sshKeyRequired.description': 'Configure an SSH key before cloning this repository.',
        'shared.versionControl.repositorySetup.sshKeyRequired.action': 'Open system settings',
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
        'shared.versionControl.conflict.title': 'Git lock conflict',
        'shared.versionControl.conflict.staleDescription': 'A stuck Git lock was detected.',
        'shared.versionControl.conflict.collisionDescription': 'Another Git operation is in progress.',
        'shared.versionControl.conflict.forceUnlock': 'Force unlock',
        'shared.versionControl.conflict.forceUnlockDialog.title': 'Force unlock Git?',
        'shared.versionControl.conflict.forceUnlockDialog.description': 'Only continue for a stale lock.',
        'shared.versionControl.conflict.forceUnlockDialog.cancel': 'Cancel',
        'shared.versionControl.conflict.forceUnlockDialog.confirm': 'Force unlock',
        'shared.versionControl.conflict.forceUnlockDialog.pending': 'Unlocking...',
      };
      return values[key] ?? key;
    },
  }),
}));

beforeAll(() => {
  HTMLElement.prototype.hasPointerCapture = () => false;
  HTMLElement.prototype.setPointerCapture = () => {};
  HTMLElement.prototype.releasePointerCapture = () => {};
});

describe('version-control components', () => {
  it('renders a non-interactive branch label when checkout is unsupported', () => {
    render(
      <VersionControlChangesSidebar
        branches={[{ name: 'main', displayName: 'main', kind: 'local', isCurrent: true }]}
        currentBranch="main"
        actions={[]}
        stagedFiles={[]}
        unstagedFiles={[]}
        onCommit={vi.fn()}
        onFileSelect={vi.fn()}
        onStageToggle={vi.fn()}
        onStageAll={vi.fn()}
        onUnstageAll={vi.fn()}
      />,
    );

    expect(screen.getByText('main')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /main/i })).not.toBeInTheDocument();
  });

  it('uses the shared empty state in the second-column change lists', () => {
    render(
      <VersionControlChangesSidebar
        branches={[]}
        currentBranch="main"
        actions={[]}
        stagedFiles={[]}
        unstagedFiles={[]}
        onBranchChange={vi.fn()}
        onCommit={vi.fn()}
        onFileSelect={vi.fn()}
        onStageToggle={vi.fn()}
        onStageAll={vi.fn()}
        onUnstageAll={vi.fn()}
      />,
    );

    const titles = screen.getAllByText('No file changes');
    expect(titles).toHaveLength(2);
    titles.forEach((title) => {
      expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
      expect(title.parentElement?.parentElement).toHaveClass('h-full');
    });
  });

  it('uses the shared empty state in the file changes diff panel', () => {
    render(
      <VersionControlDiffContent selectedPath={null} diffContent="" />,
    );

    const title = screen.getByText('Select a file');
    expect(title).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
  });

  it('submits commit messages through the neutral commit form', async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();

    render(<VersionControlCommitForm onCommit={onCommit} stagedCount={1} />);

    await user.type(screen.getByPlaceholderText('Commit message'), 'Update registry');
    await user.click(screen.getByRole('button', { name: 'Commit' }));

    expect(onCommit).toHaveBeenCalledWith({ message: 'Update registry' });
  });

  it('keeps read-only commit forms out of the submitting state', () => {
    render(<VersionControlCommitForm onCommit={vi.fn()} stagedCount={1} disabled />);

    expect(screen.getByPlaceholderText('Commit message')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Commit' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Committing...' })).not.toBeInTheDocument();
  });

  it('keeps commit form out of submitting state while header stage all is pending', () => {
    render(
      <VersionControlChangesSidebar
        branches={[]}
        currentBranch="main"
        actions={[]}
        stagedFiles={[{ name: 'README.md', path: 'README.md', status: 'M' }]}
        unstagedFiles={[{ name: 'notes.md', path: 'notes.md', status: 'M' }]}
        onBranchChange={vi.fn()}
        onCommit={vi.fn()}
        onFileSelect={vi.fn()}
        onStageToggle={vi.fn()}
        onStageAll={vi.fn()}
        onUnstageAll={vi.fn()}
        isStageAllPending
      />,
    );

    expect(screen.getByRole('button', { name: 'Commit' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Committing...' })).not.toBeInTheDocument();
    expect(screen.getByTitle('Stage all files')).toBeDisabled();
  });

  it('renders header counts from total counts instead of loaded rows', () => {
    render(
      <VersionControlChangesSidebar
        branches={[]}
        currentBranch="main"
        actions={[]}
        stagedFiles={[{ name: 'README.md', path: 'README.md', status: 'M' }]}
        unstagedFiles={[{ name: 'notes.md', path: 'notes.md', status: 'M' }]}
        stagedCount={1200}
        unstagedCount={3400}
        onBranchChange={vi.fn()}
        onCommit={vi.fn()}
        onFileSelect={vi.fn()}
        onStageToggle={vi.fn()}
        onStageAll={vi.fn()}
        onUnstageAll={vi.fn()}
      />,
    );

    expect(screen.getByText('1200')).toBeInTheDocument();
    expect(screen.getByText('3400')).toBeInTheDocument();
  });

  it('opens the formal force-unlock dialog only from stale operation status', async () => {
    const user = userEvent.setup();
    const onForceUnlock = vi.fn().mockResolvedValue(undefined);

    render(
      <VersionControlChangesSidebar
        branches={[]}
        currentBranch="main"
        actions={[]}
        stagedFiles={[]}
        unstagedFiles={[]}
        operationStatus={{ isActive: false, stale: true, retryable: true }}
        onForceUnlock={onForceUnlock}
        onCommit={vi.fn()}
        onFileSelect={vi.fn()}
        onStageToggle={vi.fn()}
        onStageAll={vi.fn()}
        onUnstageAll={vi.fn()}
      />,
    );

    await user.click(screen.getAllByRole('button', { name: 'Force unlock' }).at(-1)!);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Force unlock' }));
    expect(onForceUnlock).toHaveBeenCalledTimes(1);
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

  it('shows row-level pending state while a file stage action is running', () => {
    render(
      <VersionControlFileChangeItem
        file={{ name: 'README.md', path: 'templates/demo/README.md', status: 'M' }}
        isSelected={false}
        isMultiSelected={false}
        type="unstaged"
        onSelect={vi.fn()}
        onStageToggle={vi.fn()}
        selectedCount={1}
        actionPending
      />,
    );

    const button = screen.getByTitle('Stage file');
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
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
    await user.click(screen.getByRole('menuitem', { name: 'Stage 2 files' }));

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
    expect(screen.getByRole('menuitem', { name: 'Unstage' })).toBeInTheDocument();
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
      />,
    );

    await user.type(screen.getByLabelText('Branch name'), 'feature/shared');
    await user.type(screen.getByLabelText('Start point'), 'origin/main');
    await user.click(screen.getByRole('button', { name: 'Create branch' }));

    expect(onCreate).toHaveBeenCalledWith({
      branch: 'feature/shared',
      startPoint: 'origin/main',
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
          currentBranch: 'main',
          remoteUrl: '',
          hasOrigin: false,
        }}
        onSaveRemoteUrl={onSaveRemoteUrl}
      />,
    );

    await user.type(screen.getByLabelText('Remote URL'), 'git@example.com:repo.git');
    await user.click(screen.getByRole('button', { name: 'Save remote' }));

    expect(onSaveRemoteUrl).toHaveBeenCalledWith('git@example.com:repo.git');
  });

  it('prevents remote settings dismissal while saving', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <VersionControlRemoteSettingsDialog
        open
        onOpenChange={onOpenChange}
        repository={{ currentBranch: 'main', remoteUrl: '', hasOrigin: false }}
        onSaveRemoteUrl={vi.fn()}
        isSavingRemoteUrl
      />,
    );

    await user.click(screen.getByRole('button', { name: 'common.close' }));
    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('uses one repository setup flow with secondary init and primary clone actions', async () => {
    const user = userEvent.setup();
    const onInitializeRepository = vi.fn().mockResolvedValue(undefined);
    const onCloneRepository = vi.fn().mockResolvedValue(undefined);
    const onListRemoteBranches = vi.fn().mockResolvedValue({
      branches: ['main', 'develop'],
      defaultBranch: 'main',
    });

    render(
      <VersionControlRepositorySetup
        target={{
          scopeKey: 'test:repository-setup',
          repository: {
            isGitRepo: false,
            hasOrigin: false,
            hasLocalContent: false,
            canCloneSafely: true,
            canInitSafely: true,
          },
        }}
        capability={{ canMutate: true }}
        remoteEffects={{
          initialize: onInitializeRepository,
          clone: onCloneRepository,
          discoverBranches: onListRemoteBranches,
        }}
      />,
    );

    const initButton = screen.getByRole('button', { name: 'Initialize Git' });
    const cloneButton = screen.getByRole('button', { name: 'Clone repository' });
    expect(initButton).toHaveAttribute('data-variant', 'outline');
    expect(cloneButton).not.toHaveAttribute('data-variant', 'outline');

    await user.click(cloneButton);
    await user.type(screen.getByLabelText('Repository URL'), 'git@example.com:team/repo.git');
    await user.click(screen.getByRole('button', { name: 'Load branches' }));
    await user.click(await screen.findByRole('combobox', { name: 'Branch' }));
    await user.click(screen.getByRole('option', { name: 'develop' }));
    await user.click(screen.getByRole('button', { name: 'Clone repository' }));

    expect(onCloneRepository).toHaveBeenCalledWith(
      'git@example.com:team/repo.git',
      'develop',
    );
  });

  it('guides SSH clone failures to system settings inside the shared dialog', async () => {
    const user = userEvent.setup();
    const onCloneRepository = vi.fn().mockRejectedValue({
      status: 409,
      errorCode: 'VC_SSH_KEY_REQUIRED',
    });

    render(
      <VersionControlRepositorySetup
        target={{
          scopeKey: 'test:repository-setup',
          repository: {
            isGitRepo: false,
            hasOrigin: false,
            hasLocalContent: false,
            canCloneSafely: true,
            canInitSafely: true,
          },
        }}
        capability={{ canMutate: true }}
        remoteEffects={{
          initialize: vi.fn().mockResolvedValue(undefined),
          clone: onCloneRepository,
          discoverBranches: vi.fn().mockResolvedValue({
            branches: ['main'],
            defaultBranch: 'main',
          }),
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Clone repository' }));
    await user.type(screen.getByLabelText('Repository URL'), 'git@example.com:team/repo.git');
    await user.click(screen.getByRole('button', { name: 'Load branches' }));
    await user.click(screen.getByRole('button', { name: 'Clone repository' }));

    expect(await screen.findByText('SSH key required')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open system settings' }))
      .toHaveAttribute('href', '/settings');
  });

  it('guides SSH branch discovery failures to system settings', async () => {
    const user = userEvent.setup();

    render(
      <VersionControlRepositorySetup
        target={{
          scopeKey: 'test:repository-setup',
          repository: {
            isGitRepo: false,
            hasOrigin: false,
            hasLocalContent: false,
            canCloneSafely: true,
            canInitSafely: true,
          },
        }}
        capability={{ canMutate: true }}
        remoteEffects={{
          initialize: vi.fn().mockResolvedValue(undefined),
          clone: vi.fn().mockResolvedValue(undefined),
          discoverBranches: vi.fn().mockRejectedValue({
            status: 409,
            errorCode: 'VC_SSH_KEY_REQUIRED',
          }),
        }}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Clone repository' }));
    await user.type(screen.getByLabelText('Repository URL'), 'git@example.com:team/repo.git');
    await user.click(screen.getByRole('button', { name: 'Load branches' }));

    expect(await screen.findByText('SSH key required')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open system settings' }))
      .toHaveAttribute('href', '/settings');
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
