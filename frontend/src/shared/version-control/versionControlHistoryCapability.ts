import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  shouldRetryVersionControlQuery,
  type VersionControlCore,
} from './versionControlSessionCore';
import type {
  VersionControlBlobResponse,
  VersionControlBranchListResponse,
  VersionControlCommitListResponse,
  VersionControlDiffResponse,
  VersionControlFileChange,
} from './types';

interface VersionControlBranchesQueryParams {
  includeRemote: boolean;
  search?: string;
  includeMetadata: boolean;
}

interface VersionControlCommitsQueryParams {
  cursor?: string;
  limit: number;
  queryScope?: 'current' | 'all' | 'local' | 'remote';
  branch?: string;
  search?: string;
}

interface VersionControlCommitBlobQueryParams {
  path: string | null;
  revision: string | null;
}

interface VersionControlCommitDiffQueryParams {
  path: string | null;
  commitId: string | null;
}

export interface VersionControlCreateBranchPayload {
  name: string;
  startPoint?: string;
  upstream?: string;
}

export interface VersionControlRenameBranchPayload {
  oldName: string;
  newName: string;
}

export interface VersionControlPublishBranchPayload {
  remote?: string;
  remoteName?: string;
}

const createCommonHistoryCapability = (core: VersionControlCore) => {
  const useCommitFilesQuery = (commitId: string | null) => useQuery({
    queryKey: core.key('history', 'commit-files', commitId ?? ''),
    queryFn: async () => {
      const response = await core.request<{
        commitId: string;
        files: VersionControlFileChange[];
      }>(`commits/${encodeURIComponent(commitId ?? '')}/files`);
      return response.files;
    },
    enabled: core.gitQueriesEnabled && Boolean(commitId),
    retry: shouldRetryVersionControlQuery,
  });

  const useRevertCommitMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (sha: string) => core.request('commits/revert', {
        method: 'POST',
        body: { sha },
      }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'history']),
    });
  };

  return { useCommitFilesQuery, useRevertCommitMutation };
};

const createSharedBranchCapability = (core: VersionControlCore) => {
  const useBranchesQuery = (
    params: Partial<VersionControlBranchesQueryParams> = {},
  ) => {
    const query = new URLSearchParams();
    if (params.includeRemote != null) {
      query.set('includeRemote', String(params.includeRemote));
    }
    if (params.includeMetadata != null) {
      query.set('includeMetadata', String(params.includeMetadata));
    }
    if (params.search) {
      query.set('search', params.search);
    }
    const suffix = query.size > 0 ? `?${query}` : '';

    return useQuery({
      queryKey: core.key('history', 'branches', params),
      queryFn: () => core.request<VersionControlBranchListResponse>(`branches${suffix}`),
      enabled: core.gitQueriesEnabled,
      retry: shouldRetryVersionControlQuery,
      select: response => response.branches ?? [],
    });
  };

  const createMutation = <TPayload, TResult = VersionControlBranchListResponse>(
    operation: 'create' | 'switch' | 'rename' | 'delete' | 'publish',
  ) => () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: TPayload) => core.request<TResult>(`branches/${operation}`, {
        method: 'POST',
        body: payload,
      }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'history', 'remote']),
    });
  };

  return {
    useBranchesQuery,
    useCreateBranchMutation: createMutation<VersionControlCreateBranchPayload>('create'),
    useSwitchBranchMutation: createMutation<{ name: string }>('switch'),
    useRenameBranchMutation: createMutation<VersionControlRenameBranchPayload>('rename'),
    useDeleteBranchMutation: createMutation<{ name: string }>('delete'),
    usePublishBranchMutation: createMutation<VersionControlPublishBranchPayload>('publish'),
  };
};

const useCommitsQueryForCore = (
  core: VersionControlCore,
  params: VersionControlCommitsQueryParams,
) => {
  const query = new URLSearchParams({
    limit: String(params.limit),
    queryScope: params.queryScope ?? 'current',
  });
  if (params.cursor) query.set('cursor', params.cursor);
  if (params.branch) query.set('branch', params.branch);
  if (params.search) query.set('search', params.search);

  return useQuery({
    queryKey: core.key('history', 'commits', params),
    queryFn: () => core.request<VersionControlCommitListResponse>(`commits?${query}`),
    enabled: core.gitQueriesEnabled,
    retry: shouldRetryVersionControlQuery,
  });
};

export const createWorkspaceHistoryCapability = (core: VersionControlCore) => {
  const common = createCommonHistoryCapability(core);
  const branches = createSharedBranchCapability(core);

  const useCommitsInfiniteQuery = (
    params: Omit<VersionControlCommitsQueryParams, 'cursor'>,
  ) => useInfiniteQuery({
    queryKey: core.key('history', 'commits', params),
    queryFn: ({ pageParam }) => {
      const query = new URLSearchParams({
        limit: String(params.limit),
        queryScope: params.queryScope ?? 'current',
      });
      if (pageParam) query.set('cursor', pageParam);
      if (params.branch) {
        query.set('branch', params.branch);
      }
      if (params.search) {
        query.set('search', params.search);
      }
      return core.request<VersionControlCommitListResponse>(`commits?${query}`);
    },
    getNextPageParam: lastPage => lastPage.hasMore
      ? lastPage.nextCursor ?? undefined
      : undefined,
    initialPageParam: undefined as string | undefined,
    enabled: core.gitQueriesEnabled,
    retry: shouldRetryVersionControlQuery,
  });

  return {
    ...common,
    ...branches,
    useCommitsInfiniteQuery,
  };
};

export const createKnowledgeBaseHistoryCapability = (
  core: VersionControlCore,
) => {
  const common = createCommonHistoryCapability(core);
  const branches = createSharedBranchCapability(core);

  const useCommitsQuery = (
    params: VersionControlCommitsQueryParams = {
      limit: 20,
    },
  ) => useCommitsQueryForCore(core, params);

  const useCommitBlobQuery = ({
    path,
    revision,
  }: VersionControlCommitBlobQueryParams) => {
    const query = new URLSearchParams({ path: path ?? '' });
    if (revision) {
      query.set('revision', revision);
    }
    return useQuery({
      queryKey: core.key('history', 'blob', revision ?? '', path ?? ''),
      queryFn: () => core.request<VersionControlBlobResponse>(`blob?${query}`),
      enabled: core.gitQueriesEnabled && Boolean(path && revision),
      retry: shouldRetryVersionControlQuery,
    });
  };

  return {
    ...common,
    ...branches,
    useCommitsQuery,
    useCommitBlobQuery,
  };
};

export const createMarketplaceHistoryCapability = (
  core: VersionControlCore,
) => {
  const common = createCommonHistoryCapability(core);
  const branches = createSharedBranchCapability(core);

  const useCommitsQuery = (
    params: VersionControlCommitsQueryParams = {
      limit: 20,
    },
  ) => useCommitsQueryForCore(core, params);

  const useCommitDiffQuery = ({
    path,
    commitId,
  }: VersionControlCommitDiffQueryParams) => {
    const query = new URLSearchParams({ path: path ?? '' });
    return useQuery({
      queryKey: core.key('history', 'commit-diff', commitId ?? '', path ?? ''),
      queryFn: () => core.request<VersionControlDiffResponse>(
        `commits/${encodeURIComponent(commitId ?? '')}/diff?${query}`,
      ),
      enabled: core.gitQueriesEnabled && Boolean(path && commitId),
      retry: shouldRetryVersionControlQuery,
    });
  };

  return {
    ...common,
    ...branches,
    useCommitsQuery,
    useCommitDiffQuery,
  };
};
