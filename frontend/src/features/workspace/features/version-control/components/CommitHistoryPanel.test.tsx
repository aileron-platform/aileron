import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@/__tests__/utils/render';
import { ApiError } from '@/shared/api/apiClient';
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
    t: (key: string) => key,
  }),
}));

vi.mock('../hooks/useVersionControlQueries', () => ({
  useCommitsInfiniteQuery: () => commitsQueryMock,
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
});
