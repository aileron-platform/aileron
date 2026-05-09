import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/shared/api/apiClient';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { applyStagePathsToChangesResponse, FileChangesPanel } from './FileChangesPanel';

const {
  onFileSelectMock,
  changesQueryMock,
  branchesQueryMock,
  statusQueryMock,
  useBranchesQueryMock,
  fetchMutationMock,
  pullMutationMock,
  pushMutationMock,
  remoteSettingsQueryMock,
  setRemoteUrlMutationMock,
  checkoutMutationMock,
  stageMutationMock,
  unstageMutationMock,
  discardMutationMock,
  toastMock,
  worktreeSettingsDialogMock,
  remoteSettingsDialogMock,
} = vi.hoisted(() => ({
  onFileSelectMock: vi.fn(),
  changesQueryMock: {
    data: {
      staged: [],
      unstaged: [{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }],
      untracked: [{ name: 'draft.txt', path: 'draft.txt', status: '?', additions: 0, deletions: 0 }],
      untrackedHasMore: false,
    },
    isLoading: false,
    isFetching: false,
    error: null,
  },
  branchesQueryMock: {
    data: [{ name: 'main', displayName: 'main', isActive: true }],
    isLoading: false,
    error: null,
  },
  statusQueryMock: {
    data: { branch: 'main' },
  },
  useBranchesQueryMock: vi.fn(),
  fetchMutationMock: { mutateAsync: vi.fn(), isPending: false },
  pullMutationMock: { mutateAsync: vi.fn(), isPending: false },
  pushMutationMock: { mutateAsync: vi.fn(), isPending: false },
  remoteSettingsQueryMock: {
    data: {
      isInitialized: true,
      currentBranch: 'main',
      remoteUrl: 'git@example.com:team/project.git',
      hasOrigin: true,
    },
  },
  setRemoteUrlMutationMock: { mutateAsync: vi.fn(), isPending: false },
  checkoutMutationMock: { mutateAsync: vi.fn(), isPending: false },
  stageMutationMock: { mutateAsync: vi.fn(), isPending: false },
  unstageMutationMock: { mutateAsync: vi.fn(), isPending: false },
  discardMutationMock: { mutateAsync: vi.fn(), isPending: false },
  toastMock: vi.fn(),
  worktreeSettingsDialogMock: vi.fn(),
  remoteSettingsDialogMock: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) =>
      ({
        'workspace.versionControl.actions.refresh.label': 'Refresh',
        'workspace.versionControl.actions.refresh.tooltip': 'Refresh version control status',
        'shared.versionControl.actions.menu.label': 'More actions',
        'shared.versionControl.actions.branch.label': 'Branch',
        'shared.versionControl.actions.branch.create': 'Create branch',
        'shared.versionControl.actions.refresh.label': 'Refresh',
        'shared.versionControl.actions.fetch.label': 'Fetch',
        'shared.versionControl.actions.pull.label': 'Pull',
        'shared.versionControl.actions.push.label': 'Push',
        'shared.versionControl.actions.remoteSettings.label': 'Remote settings',
        'workspace.versionControl.worktree.menu.settings': 'Worktree settings...',
        'shared.versionControl.fileChanges.stagedTitle': 'Staged changes',
        'shared.versionControl.fileChanges.unstagedTitle': 'Unstaged changes',
        'shared.versionControl.fileChanges.empty': 'No file changes',
        'shared.versionControl.fileChanges.unstageAllTooltip': 'Unstage all files',
        'shared.versionControl.fileChanges.stageAllTooltip': 'Stage all files',
        'shared.versionControl.fileChanges.loadingMore': 'Loading...',
        'shared.versionControl.commitForm.placeholder': 'Commit message',
        'shared.versionControl.commitForm.submit': 'Commit',
        'shared.versionControl.commitForm.submitting': 'Committing...',
        'shared.versionControl.commitFiles.status.modified': 'Modified',
        'shared.versionControl.commitFiles.status.unknown': 'Unknown',
        'shared.versionControl.fileItem.stageTooltip': 'Stage file',
        'shared.versionControl.fileItem.unstageTooltip': 'Unstage file',
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
        'workspace.versionControl.toasts.fetchSuccess.title': 'Fetch completed',
        'workspace.versionControl.toasts.pullSuccess.title': 'Pull completed',
        'workspace.versionControl.toasts.pushSuccess.title': 'Push completed',
        'workspace.versionControl.toasts.remoteUrlSuccess.title': 'Remote URL saved',
        'workspace.versionControl.toasts.createBranchSuccess.title': 'Branch created',
        'workspace.versionControl.toasts.createBranchSuccess.description': `Created ${params?.branch}.`,
      }[key] ?? key),
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('./WorktreeSettingsDialog', () => ({
  WorktreeSettingsDialog: (props: { open: boolean }) => {
    worktreeSettingsDialogMock(props);
    return props.open ? <div role="dialog">Worktree settings dialog</div> : null;
  },
}));

vi.mock('@/shared/components/version-control', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/version-control')>();
  return {
    ...actual,
    VersionControlRemoteSettingsDialog: (props: {
      open: boolean;
      repository: { isRepositoryInitialized: boolean; remoteUrl?: string | null };
      onSaveRemoteUrl: (remoteUrl: string) => void;
    }) => {
      remoteSettingsDialogMock(props);
      return props.open ? (
        <div role="dialog">
          <div>Remote settings dialog</div>
          <div>{props.repository.remoteUrl}</div>
          <button type="button" onClick={() => props.onSaveRemoteUrl('git@example.com:team/updated.git')}>
            save remote
          </button>
        </div>
      ) : null;
    },
  };
});

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: {
      versionControl: {
        selectedGitContextId: 'primary',
      },
    },
    dispatch: vi.fn(),
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-refresh',
      reload: vi.fn(),
    },
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useGitContextsQuery: () => ({
    data: {
      activeContextId: 'primary',
      contexts: [{ id: 'primary', kind: 'primary', displayName: 'main', repoPath: '/workspace', detached: false, locked: false, prunable: false }],
    },
    isLoading: false,
  }),
  useChangesQuery: () => changesQueryMock,
  useBranchesQuery: (...args: unknown[]) => useBranchesQueryMock(...args),
  useStatusQuery: () => statusQueryMock,
  useStageMutation: () => stageMutationMock,
  useUnstageMutation: () => unstageMutationMock,
  useCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDiscardMutation: () => discardMutationMock,
  useFetchMutation: () => fetchMutationMock,
  usePullMutation: () => pullMutationMock,
  usePushMutation: () => pushMutationMock,
  useRemoteSettingsQuery: () => remoteSettingsQueryMock,
  useSetRemoteUrlMutation: () => setRemoteUrlMutationMock,
  useCheckoutMutation: () => checkoutMutationMock,
}));

describe('FileChangesPanel', () => {
  beforeEach(() => {
    onFileSelectMock.mockClear();
    changesQueryMock.error = null;
    branchesQueryMock.error = null;
    useBranchesQueryMock.mockReset();
    useBranchesQueryMock.mockReturnValue(branchesQueryMock);
    fetchMutationMock.mutateAsync.mockResolvedValue({});
    pullMutationMock.mutateAsync.mockResolvedValue({});
    pushMutationMock.mutateAsync.mockResolvedValue({});
    setRemoteUrlMutationMock.mutateAsync.mockResolvedValue({});
    checkoutMutationMock.mutateAsync.mockResolvedValue({ branch: 'feature/new', created: true });
    stageMutationMock.mutateAsync.mockClear();
    unstageMutationMock.mutateAsync.mockClear();
    discardMutationMock.mutateAsync.mockClear();
    stageMutationMock.mutateAsync.mockResolvedValue({});
    unstageMutationMock.mutateAsync.mockResolvedValue({});
    discardMutationMock.mutateAsync.mockResolvedValue({});
    toastMock.mockClear();
    remoteSettingsDialogMock.mockClear();
  });

  it('renders branch and action controls in the changes header', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('Branch')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'main' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument();
    expect(useBranchesQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceId: 'ws-refresh', contextId: 'primary' }),
      true,
      undefined,
      false,
    );
  });

  it('keeps unstaged files visible in the panel', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
    expect(screen.getAllByText('draft.txt').length).toBeGreaterThan(0);
  });

  it('stages selected workspace files as a batch', async () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getAllByText('notes.md')[0]);
    fireEvent.click(screen.getAllByText('draft.txt')[0], { ctrlKey: true });
    fireEvent.click(screen.getAllByTitle('Stage file')[1]);

    expect(stageMutationMock.mutateAsync).toHaveBeenCalledWith(['notes.md', 'draft.txt']);
  });

  it('applies staged paths to the visible changes cache immediately', () => {
    const next = applyStagePathsToChangesResponse(
      {
        staged: [{ name: 'README.md', path: 'README.md', status: 'M', type: 'modified' }],
        unstaged: [{ name: 'notes.md', path: 'notes.md', status: 'M', type: 'modified' }],
        untracked: [{ name: 'draft.txt', path: 'draft.txt', status: '??', type: 'untracked' }],
        untrackedTotal: 1,
        untrackedPage: 1,
        untrackedPageSize: 100,
        untrackedHasMore: false,
      },
      ['notes.md', 'draft.txt'],
    );

    expect(next?.staged.map(file => file.path)).toEqual(['README.md', 'notes.md', 'draft.txt']);
    expect(next?.staged.find(file => file.path === 'draft.txt')).toMatchObject({
      status: 'A',
      type: 'added',
      changeType: 'staged',
    });
    expect(next?.unstaged).toEqual([]);
    expect(next?.untracked).toEqual([]);
    expect(next?.untrackedTotal).toBe(0);
  });

  it('wires refresh, fetch, pull, and push actions', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Fetch'));
    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Pull'));
    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Push'));

    expect(fetchMutationMock.mutateAsync).toHaveBeenCalledWith({ remote: 'origin' });
    expect(pullMutationMock.mutateAsync).toHaveBeenCalledWith({
      remote: 'origin',
      branch: 'main',
      rebase: true,
      autostash: true,
    });
    expect(pushMutationMock.mutateAsync).toHaveBeenCalledWith({
      remote: 'origin',
      branch: 'main',
      force: false,
    });
  });

  it('opens worktree settings from the action menu', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Worktree settings...'));

    expect(screen.getByRole('dialog')).toHaveTextContent('Worktree settings dialog');
    expect(worktreeSettingsDialogMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ open: true }),
    );
  });

  it('opens remote settings from the action menu and saves the remote URL', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'More actions' }));
    await user.click(screen.getByText('Remote settings'));

    expect(screen.getByRole('dialog')).toHaveTextContent('Remote settings dialog');
    expect(screen.getByRole('dialog')).toHaveTextContent('git@example.com:team/project.git');
    expect(remoteSettingsDialogMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        open: true,
        repository: expect.objectContaining({
          isRepositoryInitialized: true,
          remoteUrl: 'git@example.com:team/project.git',
        }),
      }),
    );

    await user.click(screen.getByText('save remote'));

    expect(setRemoteUrlMutationMock.mutateAsync).toHaveBeenCalledWith('git@example.com:team/updated.git');
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Remote URL saved' }));
  });

  it('creates a branch with start point and stash option', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'main' }));
    await user.click(screen.getByText('Create branch'));
    await user.type(screen.getByLabelText('Branch name'), 'feature/new');
    await user.type(screen.getByLabelText('Start point'), 'origin/main');
    await user.click(screen.getByText('Stash local changes'));
    await user.click(screen.getByRole('button', { name: 'Create branch' }));

    expect(checkoutMutationMock.mutateAsync).toHaveBeenCalledWith({
      branch: 'feature/new',
      create: true,
      startPoint: 'origin/main',
      stashChanges: true,
    });
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Branch created' }));
  });

  it('clears selected file state when the branch changes', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    const view = render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByText('notes.md')[0]);

    expect(onFileSelectMock).toHaveBeenCalledWith(
      expect.objectContaining({ path: 'notes.md' }),
    );

    branchesQueryMock.data = [{ name: 'feature-auth', displayName: 'feature-auth', isActive: true }];
    statusQueryMock.data = { branch: 'feature-auth' };

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(onFileSelectMock).toHaveBeenLastCalledWith(null);
  });

  it('renders a non-git empty state when the repository is not initialized', () => {
    const queryClient = new QueryClient();
    changesQueryMock.error = new ApiError(
      'Workspace is not a git repository',
      400,
      'VC_REPOSITORY_NOT_INITIALIZED',
    );

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('workspace.versionControl.errors.notInitialized.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.versionControl.errors.notInitialized.description')).toBeInTheDocument();
  });
});
