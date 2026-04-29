import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@/__tests__/utils/render';
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
  checkoutMutationMock,
  toastMock,
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
  checkoutMutationMock: { mutateAsync: vi.fn(), isPending: false },
  toastMock: vi.fn(),
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
        'workspace.versionControl.branchDialog.title': 'Create branch',
        'workspace.versionControl.branchDialog.description': 'Create a branch.',
        'workspace.versionControl.branchDialog.namePlaceholder': 'Branch name',
        'workspace.versionControl.branchDialog.nameLabel': 'Branch name',
        'workspace.versionControl.branchDialog.startPointPlaceholder': 'Start point',
        'workspace.versionControl.branchDialog.startPointLabel': 'Start point',
        'workspace.versionControl.branchDialog.stashChanges': 'Stash local changes',
        'workspace.versionControl.branchDialog.cancel': 'Cancel',
        'workspace.versionControl.branchDialog.create': 'Create branch',
        'workspace.versionControl.branchDialog.creating': 'Creating...',
        'workspace.versionControl.toasts.fetchSuccess.title': 'Fetch completed',
        'workspace.versionControl.toasts.pullSuccess.title': 'Pull completed',
        'workspace.versionControl.toasts.pushSuccess.title': 'Push completed',
        'workspace.versionControl.toasts.createBranchSuccess.title': 'Branch created',
        'workspace.versionControl.toasts.createBranchSuccess.description': `Created ${params?.branch}.`,
      }[key] ?? key),
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
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
  useStageMutation: () => ({ mutateAsync: vi.fn() }),
  useUnstageMutation: () => ({ mutateAsync: vi.fn() }),
  useCommitMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDiscardMutation: () => ({ mutateAsync: vi.fn() }),
  useFetchMutation: () => fetchMutationMock,
  usePullMutation: () => pullMutationMock,
  usePushMutation: () => pushMutationMock,
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
    checkoutMutationMock.mutateAsync.mockResolvedValue({ branch: 'feature/new', created: true });
    toastMock.mockClear();
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
