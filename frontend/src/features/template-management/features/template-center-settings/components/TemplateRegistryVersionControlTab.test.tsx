import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TemplateRegistryVersionControlTab } from './TemplateRegistryVersionControlTab';

const templateVersionControlApiMock = vi.hoisted(() => ({
  getStatus: vi.fn(async () => ({
    branch: 'main',
    ahead: 1,
    behind: 0,
    detached: false,
    hasConflicts: false,
    stagedCount: 1,
    unstagedCount: 1,
    untrackedCount: 0,
  })),
  getChanges: vi.fn(async () => ({
    staged: [
      { name: 'staged.md', path: 'templates/demo/staged.md', status: 'M', additions: 2, deletions: 0 },
    ],
    unstaged: [
      { name: 'README.md', path: 'templates/demo/README.md', status: 'M', additions: 1, deletions: 1 },
    ],
    untracked: [],
  })),
  getBranches: vi.fn(async () => [
    { name: 'main', displayName: 'main', isActive: true, isRemote: false, ahead: 1, behind: 0 },
  ]),
  getCommits: vi.fn(async () => ({
    items: [
      {
        id: 'abcdef1234567890',
        message: 'Initial registry',
        author: 'Owner',
        email: 'owner@example.com',
        timestamp: 1710000000000,
        branch: 'main',
        files: 1,
      },
    ],
    page: 1,
    pageSize: 20,
    total: 1,
  })),
  getCommitFiles: vi.fn(async () => ({
    commitId: 'abcdef1234567890',
    files: [
      { name: 'template.yaml', path: 'templates/demo/template.yaml', status: 'M', additions: 3, deletions: 0 },
    ],
  })),
  getDiff: vi.fn(async () => ({
    path: 'templates/demo/README.md',
    patch: '@@ -1 +1 @@\n-old\n+new',
    diff: '@@ -1 +1 @@\n-old\n+new',
    binary: false,
  })),
  stage: vi.fn(async () => ({ staged: ['templates/demo/README.md'], unstaged: [] })),
  unstage: vi.fn(async () => ({ unstaged: ['templates/demo/staged.md'], remainingStaged: 0 })),
  discard: vi.fn(async () => ({ discarded: ['templates/demo/README.md'], warnings: [] })),
  commit: vi.fn(async () => ({ commit: { id: 'fedcba9876543210', message: 'Update registry' } })),
  fetch: vi.fn(async () => ({ remote: 'origin', branch: 'main', message: 'ok' })),
  pull: vi.fn(async () => ({ remote: 'origin', branch: 'main', message: 'ok' })),
  push: vi.fn(async () => ({ remote: 'origin', branch: 'main', message: 'ok' })),
  checkoutBranch: vi.fn(async () => ({ branch: 'main', created: false })),
}));

const tMock = vi.hoisted(() => (key: string, params?: Record<string, unknown>) => {
  const values: Record<string, string> = {
    'template.center.settings.versionControl.status.aheadBehind': `Ahead ${params?.ahead ?? 0}, behind ${params?.behind ?? 0}`,
    'template.center.settings.versionControl.status.changeCounts': `Staged ${params?.staged ?? 0}, unstaged ${params?.unstaged ?? 0}, untracked ${params?.untracked ?? 0}`,
    'template.center.settings.versionControl.status.hasConflicts': 'Has conflicts',
    'template.center.settings.versionControl.status.noConflicts': 'No conflicts',
    'template.center.settings.versionControl.mode.title': 'Version Control',
    'shared.versionControl.mode.fileChanges': 'File Changes',
    'shared.versionControl.mode.commitHistory': 'History',
    'template.center.settings.versionControl.actions.rebuild': 'Rebuild',
    'template.center.settings.versionControl.setupRequired.title': 'Git repository setup required',
    'template.center.settings.versionControl.setupRequired.description': 'Set up repository first',
    'template.center.settings.versionControl.setupRequired.action': 'Open repository setup',
    'template.center.settings.versionControl.remoteMissing.inline': 'Remote sync actions disabled',
    'shared.versionControl.actions.menu.label': 'Git actions',
    'shared.versionControl.actions.branch.label': 'Branch',
    'shared.versionControl.actions.refresh.label': 'Refresh',
    'shared.versionControl.actions.fetch.label': 'Fetch',
    'shared.versionControl.actions.pull.label': 'Pull',
    'shared.versionControl.actions.push.label': 'Push',
    'shared.versionControl.actions.remoteSettings.label': 'Remote settings',
    'shared.versionControl.main.selectFile': 'Select a file to view changes',
    'shared.versionControl.main.selectCommitFile': 'Select a commit file to view changes',
    'shared.versionControl.fileChanges.stagedTitle': 'Staged',
    'shared.versionControl.fileChanges.unstagedTitle': 'Changes',
    'shared.versionControl.fileChanges.empty': 'No files',
    'shared.versionControl.fileChanges.unstageAllTooltip': 'Unstage all files',
    'shared.versionControl.fileChanges.stageAllTooltip': 'Stage all files',
    'shared.versionControl.commitForm.placeholder': 'Commit message',
    'shared.versionControl.commitForm.submit': 'Commit',
    'shared.versionControl.commitForm.submitting': 'Committing...',
    'shared.versionControl.commitFiles.status.modified': 'Modified',
    'shared.versionControl.commitFiles.status.added': 'Added',
    'shared.versionControl.commitFiles.status.deleted': 'Deleted',
    'shared.versionControl.commitFiles.status.renamed': 'Renamed',
    'shared.versionControl.commitFiles.status.unknown': 'Unknown',
    'shared.versionControl.fileItem.stageTooltip': 'Stage file',
    'shared.versionControl.fileItem.unstageTooltip': 'Unstage file',
    'shared.versionControl.fileItem.stage': 'Stage',
    'shared.versionControl.fileItem.unstage': 'Unstage',
    'shared.versionControl.fileItem.discard': 'Discard',
    'shared.versionControl.diff.empty': 'Select a file',
    'shared.versionControl.diff.noDifference': 'No differences',
    'shared.versionControl.diff.loading': 'Loading diff',
    'shared.versionControl.diff.loadFailed': 'Failed to load diff',
    'shared.versionControl.diff.binaryOrLarge': 'Unable to display file content',
    'shared.versionControl.diff.filePath': `File path: ${params?.path ?? ''}`,
    'shared.versionControl.commitHistory.title': 'Commit history',
    'shared.versionControl.commitHistory.empty': 'No commits',
    'shared.versionControl.commitHistory.selectPrompt': 'Select commit',
    'shared.versionControl.commitHistory.commitCount': `${params?.count ?? 0} commits`,
    'shared.versionControl.commitHistory.time.daysAgo': `${params?.count ?? 0} days ago`,
    'shared.versionControl.commitHistory.time.hoursAgo': `${params?.count ?? 0} hours ago`,
    'shared.versionControl.commitHistory.time.minutesAgo': `${params?.count ?? 0} minutes ago`,
    'shared.versionControl.commitHistory.time.justNow': 'Just now',
    'shared.versionControl.commitFiles.title': 'Commit files',
    'shared.versionControl.commitFiles.empty': 'No files',
    'shared.versionControl.commitFiles.fileCount': `${params?.count ?? 0} files`,
    'template.center.settings.versionControl.toasts.commitSuccess.title': 'Committed',
    'template.center.settings.versionControl.toasts.loadFailed.title': 'Load failed',
    'template.center.settings.versionControl.toasts.loadFailed.description': 'Load failed',
    'template.center.settings.versionControl.toasts.operationFailed.title': 'Operation failed',
    'template.center.settings.versionControl.toasts.operationFailed.description': 'Operation failed',
    'template.center.settings.versionControl.rebuildProgressTitle': 'Rebuild progress',
  };
  return values[key] ?? key;
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/features/template-management/api/templateGitApi', () => ({
  templateVersionControlApi: templateVersionControlApiMock,
  getRebuildProgress: vi.fn(),
  rebuildTemplates: vi.fn(async () => ({ success: true, task_id: 'task-1' })),
}));

vi.mock('@/shared/hooks/useTaskProgress', () => ({
  useTaskProgress: () => ({
    progress: null,
    startPolling: vi.fn(),
    resetProgress: vi.fn(),
  }),
}));

const initializedRepositoryStatus = {
  isGitRepo: true,
  currentBranch: 'main',
  remoteUrl: 'git@example.com:repo.git',
  hasOrigin: true,
  hasLocalContent: true,
  canCloneSafely: false,
  canInitSafely: false,
};

describe('TemplateRegistryVersionControlTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads registry version-control data and runs file and commit actions', async () => {
    const user = userEvent.setup();

    render(
      <TemplateRegistryVersionControlTab
        repositoryStatus={initializedRepositoryStatus}
        onOpenRemoteSettings={vi.fn()}
      />,
    );

    await waitFor(() => expect(screen.getByText('README.md')).toBeInTheDocument());
    expect(screen.getByTestId('version-control-layout')).toBeInTheDocument();
    expect(screen.getByTestId('version-control-mode-rail')).toBeInTheDocument();
    expect(screen.getByTestId('version-control-sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('version-control-main')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /File Changes/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /History/ })).toBeInTheDocument();
    expect(screen.getAllByText('main').length).toBeGreaterThan(0);

    await user.click(screen.getByText('README.md'));
    await waitFor(() => expect(templateVersionControlApiMock.getDiff).toHaveBeenCalledWith('templates/demo/README.md', 'WORKTREE'));
    expect(await screen.findByText('old')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Git actions'));
    await user.click(screen.getByRole('button', { name: 'Fetch' }));
    await waitFor(() => expect(templateVersionControlApiMock.fetch).toHaveBeenCalledWith({ branch: 'main' }));

    await user.click(screen.getByTitle('Stage file'));
    await waitFor(() => expect(templateVersionControlApiMock.stage).toHaveBeenCalledWith(['templates/demo/README.md']));

    await user.type(screen.getByPlaceholderText('Commit message'), 'Update registry');
    await user.click(screen.getByRole('button', { name: 'Commit' }));
    await waitFor(() => expect(templateVersionControlApiMock.commit).toHaveBeenCalledWith('Update registry'));

    await user.click(screen.getByRole('button', { name: /History/ }));
    expect(screen.getByText('Initial registry')).toBeInTheDocument();
    await user.click(screen.getByText('Initial registry'));
    await waitFor(() => expect(templateVersionControlApiMock.getCommitFiles).toHaveBeenCalledWith('abcdef1234567890'));
  });

  it('shows repository setup state before Git is initialized', async () => {
    const onOpenRemoteSettings = vi.fn();

    render(
      <TemplateRegistryVersionControlTab
        repositoryStatus={{
          isGitRepo: false,
          currentBranch: null,
          remoteUrl: null,
          hasOrigin: false,
          hasLocalContent: true,
          canCloneSafely: false,
          canInitSafely: true,
          cloneBlockedReason: 'GIT_CLONE_TARGET_NOT_EMPTY',
        }}
        onOpenRemoteSettings={onOpenRemoteSettings}
      />,
    );

    expect(await screen.findByText('Git repository setup required')).toBeInTheDocument();
    expect(templateVersionControlApiMock.getStatus).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: 'Open repository setup' }));
    expect(onOpenRemoteSettings).toHaveBeenCalled();
  });

  it('keeps local workflows available and disables remote actions without origin', async () => {
    const user = userEvent.setup();

    render(
      <TemplateRegistryVersionControlTab
        repositoryStatus={{
          ...initializedRepositoryStatus,
          remoteUrl: null,
          hasOrigin: false,
        }}
        onOpenRemoteSettings={vi.fn()}
      />,
    );

    expect(await screen.findByText('README.md')).toBeInTheDocument();
    expect(screen.getByText('Remote sync actions disabled')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Git actions'));
    expect(screen.getByRole('button', { name: 'Fetch' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Pull' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Push' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Remote settings' })).toBeEnabled();
  });
});
