import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@/__tests__/utils/render';
import { ApiError } from '@/shared/api/apiClient';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CommitHistoryPanel } from './CommitHistoryPanel';

const { commitsQueryMock, filesQueryMock } = vi.hoisted(() => ({
  commitsQueryMock: {
    data: { pages: [{ items: [] }] },
    isLoading: false,
    isFetchingNextPage: false,
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    error: null as unknown,
    lastBranch: undefined as string | undefined,
    lastSearch: undefined as string | undefined,
  },
  filesQueryMock: {
    data: [],
    isLoading: false,
    error: null as unknown,
  },
}));

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    state: {
      versionControl: {
        selectedGitContextId: null,
      },
    },
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime',
      workspaceId: 'ws-history',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => ({
      'shared.versionControl.commitHistory.filters.allBranches': 'All branches',
      'shared.versionControl.commitHistory.filters.searchPlaceholder': 'Search commits',
      'shared.versionControl.commitHistory.filters.searchAriaLabel': 'Search commits',
      'shared.versionControl.actions.branch.label': 'Branch',
    }[key] ?? key),
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useBranchesQuery: () => ({
    data: [{ name: 'main', displayName: 'main', isActive: true }],
  }),
  useStatusQuery: () => ({
    data: { branch: 'main' },
  }),
  useCommitsInfiniteQuery: vi.fn((_options, _pageSize, branch, search) => {
    commitsQueryMock.lastBranch = branch;
    commitsQueryMock.lastSearch = search;
    return commitsQueryMock;
  }),
  useCommitFilesQuery: () => filesQueryMock,
}));

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getVirtualItems: () => [],
    getTotalSize: () => 0,
    measureElement: vi.fn(),
  }),
}));

vi.mock('./GitContextSelector', () => ({
  GitContextSelector: () => null,
}));

describe('CommitHistoryPanel', () => {
  beforeEach(() => {
    commitsQueryMock.error = null;
    commitsQueryMock.lastBranch = undefined;
    commitsQueryMock.lastSearch = undefined;
    filesQueryMock.error = null;
  });

  it('renders a non-git empty state when the repository is not initialized', () => {
    commitsQueryMock.error = new ApiError(
      'Workspace is not a git repository',
      400,
      'VC_REPOSITORY_NOT_INITIALIZED',
    );

    render(
      <QueryClientProvider client={new QueryClient()}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    expect(screen.getByText('workspace.versionControl.errors.notInitialized.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.versionControl.errors.notInitialized.description')).toBeInTheDocument();
  });

  it('passes search and branch filters to the commit history query', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <CommitHistoryPanel />
      </QueryClientProvider>,
    );

    await user.type(screen.getByLabelText('Search commits'), 'fix');
    await user.click(screen.getByRole('button', { name: 'All branches' }));
    await user.click(screen.getByText('main'));

    expect(commitsQueryMock.lastSearch).toBe('fix');
    expect(commitsQueryMock.lastBranch).toBe('main');
  });
});
