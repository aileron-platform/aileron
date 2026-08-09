import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/shared/api/apiClient';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FileChangesPanel } from './FileChangesPanel';

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
  cloneRepositoryMutationMock,
  remoteBranchesMutationMock,
  initializeRepositoryMutationMock,
  branchMutationMock,
  stageMutationMock,
  unstageMutationMock,
  discardMutationMock,
  forceUnlockMutationMock,
  toastMock,
  worktreeSettingsDialogMock,
  operationStatusQueryMock,
  useChangesNumstatQueryMock,
  refreshMock,
  workspacePermissions,
} = vi.hoisted(() => ({
  onFileSelectMock: vi.fn(),
  changesQueryMock: {
    data: {
      staged: { items: [], total: 0, nextCursor: null, hasMore: false },
      unstaged: { items: [{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }], total: 1, nextCursor: null, hasMore: false },
      untracked: { items: [{ name: 'draft.txt', path: 'draft.txt', status: '?', additions: 0, deletions: 0 }], total: 1, nextCursor: null, hasMore: false },
      conflicts: { items: [{ name: 'conflict.txt', path: 'conflict.txt', status: 'UU', type: 'unmerged' }], total: 1, nextCursor: null, hasMore: false },
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
    data: {
      isInitialized: true,
      currentBranch: 'main',
      upstream: 'origin/main',
      stagedTotal: undefined as number | undefined,
      unstagedTotal: undefined as number | undefined,
      untrackedTotal: undefined as number | undefined,
    },
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
  cloneRepositoryMutationMock: { mutateAsync: vi.fn(), isPending: false },
  remoteBranchesMutationMock: { mutateAsync: vi.fn(), isPending: false },
  initializeRepositoryMutationMock: { mutateAsync: vi.fn(), isPending: false },
  branchMutationMock: { mutateAsync: vi.fn(), isPending: false },
  stageMutationMock: { mutateAsync: vi.fn(), isPending: false },
  unstageMutationMock: { mutateAsync: vi.fn(), isPending: false },
  discardMutationMock: { mutateAsync: vi.fn(), isPending: false },
  forceUnlockMutationMock: { mutateAsync: vi.fn(), isPending: false },
  toastMock: vi.fn(),
  worktreeSettingsDialogMock: vi.fn(),
  operationStatusQueryMock: {
    data: { isActive: false },
  },
  useChangesNumstatQueryMock: vi.fn(),
  refreshMock: vi.fn().mockResolvedValue(undefined),
  workspacePermissions: {
    canWrite: true,
    canManageSettings: true,
  },
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
        'shared.versionControl.fileChanges.conflictsTitle': 'Conflicts',
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
        'shared.versionControl.branchDialog.cancel': 'Cancel',
        'shared.versionControl.branchDialog.create': 'Create branch',
        'shared.versionControl.branchDialog.creating': 'Creating...',
        'workspace.versionControl.toasts.fetchSuccess.title': 'Fetch completed',
        'workspace.versionControl.toasts.pullSuccess.title': 'Pull completed',
        'workspace.versionControl.toasts.pushSuccess.title': 'Push completed',
        'workspace.versionControl.toasts.remoteUrlSuccess.title': 'Remote URL saved',
        'workspace.versionControl.toasts.createBranchSuccess.title': 'Branch created',
        'workspace.versionControl.toasts.createBranchSuccess.description': `Created ${params?.branch}.`,
        'shared.versionControl.repositorySetup.title': 'Version control is not set up',
        'shared.versionControl.repositorySetup.description': 'Initialize a repository or clone an existing one.',
        'shared.versionControl.repositorySetup.actions.init': 'Initialize Git',
        'shared.versionControl.repositorySetup.actions.initializing': 'Initializing...',
        'shared.versionControl.repositorySetup.actions.clone': 'Clone Repository',
        'shared.versionControl.repositorySetup.initializeDialog.title': 'Initialize Git repository',
        'shared.versionControl.repositorySetup.initializeDialog.description': 'Choose the default branch.',
        'shared.versionControl.repositorySetup.initializeDialog.defaultBranchLabel': 'Default branch',
        'shared.versionControl.repositorySetup.initializeDialog.cancel': 'Cancel',
        'shared.versionControl.repositorySetup.errors.title': 'Setup failed',
        'shared.versionControl.repositorySetup.errors.init': 'Unable to initialize repository.',
        'shared.versionControl.repositorySetup.errors.clone': 'Unable to clone repository.',
        'workspace.versionControl.toasts.initializeSuccess.title': 'Git repository initialized',
        'workspace.versionControl.toasts.operationInProgress.title': 'Git operation in progress',
        'workspace.versionControl.toasts.operationInProgress.description': 'Wait for the current Git operation to finish.',
        'shared.versionControl.conflict.title': 'Git lock conflict',
        'shared.versionControl.conflict.staleDescription': 'A stuck Git lock was detected.',
        'shared.versionControl.conflict.collisionDescription': 'Another Git operation is in progress. Please try again shortly.',
        'shared.versionControl.conflict.forceUnlock': 'Force unlock',
        'shared.versionControl.conflict.forceUnlockSuccess.title': 'Git lock cleared',
        'shared.versionControl.conflict.forceUnlockFailed.title': 'Unable to clear Git lock',
        'shared.versionControl.conflict.forceUnlockFailed.description': 'Try force unlocking again.',
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
    permissions: workspacePermissions,
  }),
}));

vi.mock('../../../integrations/version-control/workspaceVersionControlSession', () => {
  return {
    useWorkspaceVersionControlSession: () => ({
      changes: {
        useChangesQuery: () => changesQueryMock,
        useChangesNumstatQuery: (...args: unknown[]) => {
          useChangesNumstatQueryMock(...args);
          return { data: undefined, isLoading: false };
        },
        useStatusQuery: () => statusQueryMock,
        useOperationStatusQuery: () => operationStatusQueryMock,
        useStageMutation: () => stageMutationMock,
        useUnstageMutation: () => unstageMutationMock,
        useCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useDiscardMutation: () => discardMutationMock,
        useMarkResolvedMutation: () => stageMutationMock,
        useAbortConflictMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useForceUnlockMutation: () => forceUnlockMutationMock,
        isFirstLoad: (query: typeof changesQueryMock) => query.isLoading && !query.data,
      },
      history: {
        useContextsQuery: () => ({
          data: {
            activeContextId: 'primary',
            contexts: [{
              id: 'primary',
              kind: 'primary',
              displayName: 'Primary',
              repoPath: '/workspace',
              branch: 'main',
              detached: false,
              locked: false,
              prunable: false,
            }],
          },
          isLoading: false,
          error: null,
        }),
        useBranchesQuery: (...args: unknown[]) => useBranchesQueryMock(...args),
        useCreateBranchMutation: () => branchMutationMock,
        useSwitchBranchMutation: () => branchMutationMock,
        useRenameBranchMutation: () => branchMutationMock,
        useDeleteBranchMutation: () => branchMutationMock,
        usePublishBranchMutation: () => branchMutationMock,
      },
      remote: {
        useRemoteSettingsQuery: () => remoteSettingsQueryMock,
        useSetRemoteUrlMutation: () => setRemoteUrlMutationMock,
        useLfsPatternsQuery: () => ({
          data: { patterns: [] },
          isLoading: false,
          error: null,
          refetch: vi.fn().mockResolvedValue({ data: { patterns: [] } }),
        }),
        useUpdateLfsPatternsMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        usePreviewLfsSnapshotMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useConvertLfsSnapshotMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useCancelOperationMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
        useCloneRepositoryMutation: () => cloneRepositoryMutationMock,
        useRemoteBranchesMutation: () => remoteBranchesMutationMock,
        useInitializeRepositoryMutation: () => initializeRepositoryMutationMock,
        useRepositoryQuery: () => ({
          data: {
            isGitRepo: false,
            hasOrigin: false,
            hasLocalContent: false,
            canCloneSafely: true,
            canInitSafely: true,
          },
        }),
        useFetchMutation: () => fetchMutationMock,
        usePullMutation: () => pullMutationMock,
        usePushMutation: () => pushMutationMock,
      },
      refresh: refreshMock,
    }),
  };
});

const changePage = <T,>(items: T[], total = items.length, hasMore = false) => ({
  items,
  total,
  nextCursor: hasMore ? 'next-page' : null,
  hasMore,
});

describe('FileChangesPanel', () => {
  beforeEach(() => {
    onFileSelectMock.mockClear();
    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }]),
      untracked: changePage([{ name: 'draft.txt', path: 'draft.txt', status: '?', additions: 0, deletions: 0 }]),
      conflicts: changePage([{ name: 'conflict.txt', path: 'conflict.txt', status: 'UU', type: 'unmerged' }]),
    };
    statusQueryMock.data = {
      isInitialized: true,
      currentBranch: 'main',
      upstream: 'origin/main',
      stagedTotal: undefined,
      unstagedTotal: undefined,
      untrackedTotal: undefined,
    };
    operationStatusQueryMock.data = { isActive: false };
    changesQueryMock.isLoading = false;
    changesQueryMock.isFetching = false;
    changesQueryMock.error = null;
    branchesQueryMock.error = null;
    useBranchesQueryMock.mockReset();
    useBranchesQueryMock.mockReturnValue(branchesQueryMock);
    fetchMutationMock.mutateAsync.mockResolvedValue({});
    pullMutationMock.mutateAsync.mockResolvedValue({});
    pushMutationMock.mutateAsync.mockResolvedValue({});
    setRemoteUrlMutationMock.mutateAsync.mockResolvedValue({});
    cloneRepositoryMutationMock.mutateAsync.mockReset();
    cloneRepositoryMutationMock.mutateAsync.mockResolvedValue({});
    cloneRepositoryMutationMock.isPending = false;
    initializeRepositoryMutationMock.mutateAsync.mockReset();
    initializeRepositoryMutationMock.mutateAsync.mockResolvedValue({});
    initializeRepositoryMutationMock.isPending = false;
    branchMutationMock.mutateAsync.mockResolvedValue({ branches: [] });
    stageMutationMock.mutateAsync.mockClear();
    unstageMutationMock.mutateAsync.mockClear();
    discardMutationMock.mutateAsync.mockClear();
    stageMutationMock.mutateAsync.mockResolvedValue({});
    unstageMutationMock.mutateAsync.mockResolvedValue({});
    discardMutationMock.mutateAsync.mockResolvedValue({});
    forceUnlockMutationMock.mutateAsync.mockClear();
    forceUnlockMutationMock.mutateAsync.mockResolvedValue({});
    useChangesNumstatQueryMock.mockReset();
    refreshMock.mockClear();
    toastMock.mockClear();
    workspacePermissions.canWrite = true;
  });

  it('renders branch and action controls in the changes header', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('Branch')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Branch: main' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'More actions' })).toBeInTheDocument();
    expect(useBranchesQueryMock).toHaveBeenCalledWith({
      includeRemote: true,
      includeMetadata: false,
    });
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

  it('preserves staged selection metadata for the diff viewer', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      ...changesQueryMock.data,
      staged: changePage([{
        name: 'new-report.md',
        path: 'new-report.md',
        status: 'A',
        type: 'added',
        additions: 10,
        deletions: 0,
      }]),
    };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByText('new-report.md')[0]);

    expect(onFileSelectMock).toHaveBeenCalledWith(expect.objectContaining({
      path: 'new-report.md',
      changeType: 'staged',
    }));
  });

  it('renders conflict files outside the unstaged action group', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('Conflicts')).toBeInTheDocument();
    expect(screen.getAllByText('conflict.txt').length).toBeGreaterThan(0);

    await user.click(screen.getByTitle('Stage all files'));

    expect(stageMutationMock.mutateAsync).toHaveBeenCalledWith({ all: true });
    expect(stageMutationMock.mutateAsync).not.toHaveBeenCalledWith(expect.arrayContaining(['conflict.txt']));
  });

  it('uses backend totals for header counts and header stage all availability', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([], 2),
      untracked: changePage([], 100, true),
      conflicts: changePage([]),
    };
    statusQueryMock.data = {
      isInitialized: true,
      currentBranch: 'main',
      stagedTotal: 0,
      unstagedTotal: 2,
      untrackedTotal: 100,
    };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByText('102')).toBeInTheDocument();

    await user.click(screen.getByTitle('Stage all files'));

    expect(stageMutationMock.mutateAsync).toHaveBeenCalledWith({ all: true });
  });

  it('keeps commit button out of submitting state while header stage all is pending', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    stageMutationMock.mutateAsync.mockImplementationOnce(() => new Promise(() => undefined));

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByTitle('Stage all files'));

    expect(screen.getByRole('button', { name: 'Commit' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Committing...' })).not.toBeInTheDocument();
    expect(screen.getByTitle('Stage all files')).toBeDisabled();
  });

  it('keeps header stage all busy from backend operation status after remount', () => {
    const queryClient = new QueryClient();
    operationStatusQueryMock.data = {
      isActive: true,
      operation: 'changes.stageAll',
      contextId: 'primary',
    };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole('button', { name: 'Commit' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Committing...' })).not.toBeInTheDocument();
    expect(screen.getByTitle('Stage all files')).toBeDisabled();
    expect(screen.getByTitle('Stage all files')).toHaveAttribute('aria-busy', 'true');
  });

  it('unstages all staged files from the header without using loaded paths', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      ...changesQueryMock.data,
      staged: changePage([{ name: 'README.md', path: 'README.md', status: 'M', additions: 1, deletions: 0 }]),
    };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByTitle('Unstage all files'));

    expect(unstageMutationMock.mutateAsync).toHaveBeenCalledWith({ all: true });
    expect(unstageMutationMock.mutateAsync).not.toHaveBeenCalledWith(['README.md']);
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

  it('shows row-level pending state while staging a single file', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    stageMutationMock.mutateAsync.mockImplementationOnce(() => new Promise(() => undefined));

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByTitle('Stage file')[0]);

    const button = screen.getAllByTitle('Stage file')[0];
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: 'Commit' })).toBeInTheDocument();
  });

  it('shows operation-in-progress toast without clearing workspace changes', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    stageMutationMock.mutateAsync.mockRejectedValueOnce(new ApiError(
      'Git operation already in progress',
      409,
      'operation_locked',
    ));

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByTitle('Stage file')[0]);

    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Git operation in progress',
      description: 'Wait for the current Git operation to finish.',
      variant: 'destructive',
    }));
    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
    expect(screen.getAllByText('draft.txt').length).toBeGreaterThan(0);
  });

  it('restores visible workspace changes when staging a file fails', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    stageMutationMock.mutateAsync.mockRejectedValueOnce(new Error('stage failed'));

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getAllByTitle('Stage file')[0]);

    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'workspace.versionControl.toasts.stageFailed.title',
      variant: 'destructive',
    }));
    expect(screen.queryAllByTitle('Unstage file')).toHaveLength(0);
    expect(screen.getAllByTitle('Stage file').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
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
    });
    expect(pushMutationMock.mutateAsync).toHaveBeenCalledWith({
      remote: 'origin',
      branch: 'main',
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

    expect(screen.getByRole('dialog')).toHaveTextContent('shared.versionControl.remoteDialog.title');
    const remoteUrlInput = screen.getByLabelText('shared.versionControl.remoteDialog.remote.urlLabel');
    expect(remoteUrlInput).toHaveValue('git@example.com:team/project.git');
    await user.clear(remoteUrlInput);
    await user.type(remoteUrlInput, 'git@example.com:team/updated.git');
    await user.click(screen.getByRole('button', {
      name: 'shared.versionControl.remoteDialog.remote.actions.save',
    }));

    expect(setRemoteUrlMutationMock.mutateAsync).toHaveBeenCalledWith('git@example.com:team/updated.git');
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ title: 'Remote URL saved' }));
  });

  it('creates a branch with an explicit start point', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Branch: main' }));
    await user.click(screen.getByText('Create branch'));
    await user.type(screen.getByLabelText('Branch name'), 'feature/new');
    await user.type(screen.getByLabelText('Start point'), 'origin/main');
    await user.click(screen.getByRole('button', { name: 'Create branch' }));

    expect(branchMutationMock.mutateAsync).toHaveBeenCalledWith({
      name: 'feature/new',
      startPoint: 'origin/main',
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

    branchesQueryMock.data = [{ name: 'feature-auth', displayName: 'feature-auth', kind: 'local', isCurrent: true }];
    statusQueryMock.data = { ...statusQueryMock.data, currentBranch: 'feature-auth' };

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(onFileSelectMock).toHaveBeenLastCalledWith(null);
  });

  it('initializes Git from the non-git empty state', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([]),
      untracked: changePage([]),
      conflicts: changePage([]),
    };
    statusQueryMock.data = { ...statusQueryMock.data, isInitialized: false };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    const title = screen.getByText('Version control is not set up');
    expect(title).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByText('Initialize a repository or clone an existing one.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Initialize Git' }));
    await user.click(screen.getAllByRole('button', { name: 'Initialize Git' }).at(-1)!);
    expect(initializeRepositoryMutationMock.mutateAsync).toHaveBeenCalledWith({ defaultBranch: 'main' });
    expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Git repository initialized',
      variant: 'success',
    }));
  });

  it('does not offer Git initialization in a read-only workspace', () => {
    const queryClient = new QueryClient();
    workspacePermissions.canWrite = false;
    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([]),
      untracked: changePage([]),
      conflicts: changePage([]),
    };
    statusQueryMock.data = { ...statusQueryMock.data, isInitialized: false };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.queryByRole('button', { name: 'Initialize Git' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Clone Repository' })).not.toBeInTheDocument();
  });

  it('renders a first-load skeleton while changes are loading and replaces it with content once data arrives', () => {
    const queryClient = new QueryClient();
    changesQueryMock.data = undefined;
    changesQueryMock.isLoading = true;

    const view = render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.getByTestId('vc-changes-skeleton')).toBeInTheDocument();
    expect(screen.queryAllByText('notes.md')).toHaveLength(0);

    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }]),
      untracked: changePage([]),
      conflicts: changePage([]),
    };
    changesQueryMock.isLoading = false;

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.queryByTestId('vc-changes-skeleton')).not.toBeInTheDocument();
    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
  });

  it('does not flash the skeleton on a refetch when previous data is present', () => {
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      staged: changePage([]),
      unstaged: changePage([{ name: 'notes.md', path: 'notes.md', status: 'M', additions: 1, deletions: 0 }]),
      untracked: changePage([]),
      conflicts: changePage([]),
    };
    changesQueryMock.isLoading = false;
    changesQueryMock.isFetching = true;

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(screen.queryByTestId('vc-changes-skeleton')).not.toBeInTheDocument();
    expect(screen.getAllByText('notes.md').length).toBeGreaterThan(0);
  });

  it('derives non-empty numstat params from a null-stats (real backend) response', () => {
    // Regression for C1: backend serializes deferred stats as JSON null, and
    // ApiClient returns the raw body without null->undefined coercion. The panel
    // must still derive numstat params so the deferred fill query fires.
    const queryClient = new QueryClient();
    changesQueryMock.data = {
      staged: changePage([{ name: 'staged.md', path: 'staged.md', status: 'M', additions: null, deletions: null }]),
      unstaged: changePage([{ name: 'unstaged.md', path: 'unstaged.md', status: 'M', additions: null, deletions: null }]),
      untracked: changePage([{ name: 'untracked.txt', path: 'untracked.txt', status: '?', additions: null, deletions: null }]),
      conflicts: changePage([]),
    };

    render(
      <QueryClientProvider client={queryClient}>
        <FileChangesPanel onFileSelect={onFileSelectMock} />
      </QueryClientProvider>,
    );

    expect(useChangesNumstatQueryMock).toHaveBeenCalled();
    const callArgs = useChangesNumstatQueryMock.mock.calls[0];
    const params = callArgs?.[0] as { stagedPaths: string[]; unstagedPaths: string[] };
    expect(params.stagedPaths).toEqual(['staged.md']);
    expect(params.unstagedPaths).toEqual(['unstaged.md']);
  });
});
