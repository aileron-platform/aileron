import { useEffect, useRef } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from '@tanstack/react-query';
import {
  applyStageAllToChangesResponse,
  applyStagePathsToChangesResponse,
  applyUnstageAllToChangesResponse,
  applyUnstagePathsToChangesResponse,
} from './versionControlOptimisticUpdates';
import {
  isFirstVersionControlLoad,
  shouldRetryVersionControlQuery,
  type VersionControlCore,
} from './versionControlSessionCore';
import type {
  VersionControlChangesResponse,
  VersionControlDiffResponse,
  VersionControlNumstatParams,
  VersionControlNumstatResponse,
  VersionControlOperationStatus,
  VersionControlStagePayload,
  VersionControlStatus,
} from './types';

interface VersionControlChangesQueryParams {
  group?: 'all' | 'staged' | 'unstaged' | 'untracked' | 'conflicts';
  cursor?: string;
  limit?: number;
  enabled?: boolean;
}

interface VersionControlDiffQueryParams {
  path: string | null;
  head: 'INDEX' | 'WORKTREE';
  enabled?: boolean;
}

const toStageBody = (
  request: VersionControlStagePayload,
): Record<string, unknown> => (
  Array.isArray(request)
    ? { paths: request }
    : { all: true }
);

const toUnstageBody = (
  request: VersionControlStagePayload,
): Record<string, unknown> => (
  Array.isArray(request) ? { paths: request } : { all: true }
);

const createCommonChangesCapability = (
  core: VersionControlCore,
) => {
  const changesCacheFilter = {
    queryKey: core.key('changes', 'files'),
  } as const;

  const useChangesQuery = (params: VersionControlChangesQueryParams = {}) => {
    const { group = 'all', cursor, limit = 100, enabled = true } = params;
    const query = new URLSearchParams({
      group,
      limit: String(limit),
      includeStats: 'false',
    });
    if (cursor) query.set('cursor', cursor);

    return useQuery({
      queryKey: core.key('changes', 'files', group, cursor ?? '', limit),
      queryFn: () => core.request<VersionControlChangesResponse>(`changes?${query}`),
      enabled: core.gitQueriesEnabled && enabled,
      retry: shouldRetryVersionControlQuery,
      staleTime: 0,
      refetchOnMount: true,
      refetchOnWindowFocus: false,
      placeholderData: previousData => previousData,
    });
  };

  const useChangesNumstatQuery = (params: VersionControlNumstatParams) => {
    const queryClient = useQueryClient();
    const hasPaths = params.stagedPaths.length > 0 || params.unstagedPaths.length > 0;

    return useQuery({
      queryKey: core.key('changes', 'numstat', params),
      queryFn: async () => {
        const result = await core.request<VersionControlNumstatResponse>(
          'changes/numstat',
          {
            method: 'POST',
            body: {
              stagedPaths: params.stagedPaths,
              unstagedPaths: params.unstagedPaths,
            },
          },
        );
        const statsMap = result.stats ?? {};

        if (Object.keys(statsMap).length > 0) {
          queryClient.setQueriesData<VersionControlChangesResponse>(
            changesCacheFilter,
            current => {
              if (!current) {
                return current;
              }
              const fillStats = (page: VersionControlChangesResponse['staged']) => ({
                ...page,
                items: page.items.map(file => {
                  const stat = statsMap[file.path];
                  return stat
                    ? { ...file, additions: stat.additions, deletions: stat.deletions }
                    : file;
                }),
              });
              return {
                ...current,
                staged: fillStats(current.staged),
                unstaged: fillStats(current.unstaged),
              };
            },
          );
        }

        return result;
      },
      enabled: core.gitQueriesEnabled && hasPaths,
      retry: shouldRetryVersionControlQuery,
      staleTime: 0,
    });
  };

  const useStatusQuery = () => useQuery({
    queryKey: core.key('changes', 'status'),
    queryFn: () => core.request<VersionControlStatus>('status'),
    enabled: core.gitQueriesEnabled,
    retry: shouldRetryVersionControlQuery,
  });

  const useOperationStatusQuery = () => {
    const queryClient = useQueryClient();
    const identity = core.identity;
    const refresh = core.refresh;
    const previousOperationRef = useRef({
      identity,
      isActive: false,
    });
    const result = useQuery({
      queryKey: core.key('changes', 'operation-status'),
      queryFn: () => core.request<VersionControlOperationStatus>('operation-status'),
      enabled: core.gitQueriesEnabled,
      retry: shouldRetryVersionControlQuery,
      staleTime: 0,
      refetchInterval: query => query.state.data?.isActive ? 1000 : false,
    });
    const isActive = result.data?.isActive === true;

    useEffect(() => {
      const previousOperation = previousOperationRef.current;
      const wasActive = previousOperation.identity === identity
        && previousOperation.isActive;
      previousOperationRef.current = {
        identity,
        isActive,
      };
      if (wasActive && !isActive) {
        void refresh(queryClient, ['changes']).catch(() => {
          // The regular query error state remains the observable error surface.
        });
      }
    }, [identity, isActive, queryClient, refresh]);

    return result;
  };

  const useDiffQuery = ({
    path,
    head,
    enabled = true,
  }: VersionControlDiffQueryParams) => {
    const params = new URLSearchParams({
      path: path ?? '',
      head,
    });
    return useQuery({
      queryKey: core.key('changes', 'diff', head, path ?? ''),
      queryFn: () => core.request<VersionControlDiffResponse>(`diff?${params}`),
      enabled: core.gitQueriesEnabled && enabled && Boolean(path),
      retry: shouldRetryVersionControlQuery,
    });
  };

  const snapshotChanges = async (queryClient: QueryClient) => {
    await queryClient.cancelQueries(changesCacheFilter);
    return queryClient.getQueriesData<VersionControlChangesResponse>(changesCacheFilter);
  };

  const restoreChanges = (
    queryClient: QueryClient,
    previous: Array<[QueryKey, VersionControlChangesResponse | undefined]> | undefined,
  ) => {
    previous?.forEach(([queryKey, data]) => {
      queryClient.setQueryData(queryKey, data);
    });
  };

  const useStageMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlStagePayload) =>
        core.request('stage', {
          method: 'POST',
          body: toStageBody(payload),
        }),
      onMutate: async payload => {
        const previous = await snapshotChanges(queryClient);
        queryClient.setQueriesData<VersionControlChangesResponse>(
          changesCacheFilter,
          current => Array.isArray(payload)
            ? applyStagePathsToChangesResponse(current, payload)
            : applyStageAllToChangesResponse(current),
        );
        return { previous };
      },
      onError: (_error, _payload, context) => {
        restoreChanges(queryClient, context?.previous);
      },
      onSuccess: () => core.invalidate(queryClient, ['changes']),
    });
  };

  const useUnstageMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (payload: VersionControlStagePayload) =>
        core.request('unstage', {
          method: 'POST',
          body: toUnstageBody(payload),
        }),
      onMutate: async payload => {
        const previous = await snapshotChanges(queryClient);
        queryClient.setQueriesData<VersionControlChangesResponse>(
          changesCacheFilter,
          current => Array.isArray(payload)
            ? applyUnstagePathsToChangesResponse(current, payload)
            : applyUnstageAllToChangesResponse(current),
        );
        return { previous };
      },
      onError: (_error, _payload, context) => {
        restoreChanges(queryClient, context?.previous);
      },
      onSuccess: () => core.invalidate(queryClient, ['changes']),
    });
  };

  const useCommitMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (message: string) =>
        core.request('commit', { method: 'POST', body: { message } }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'history']),
    });
  };

  const useForceUnlockMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: () => core.request('force-unlock', { method: 'POST' }),
      onSuccess: () => core.invalidate(queryClient, ['changes']),
    });
  };

  const useMarkResolvedMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (paths: string[]) => core.request('conflicts/mark-resolved', {
        method: 'POST',
        body: { paths },
      }),
      onSuccess: () => core.invalidate(queryClient, ['changes']),
    });
  };

  const useAbortConflictMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: () => core.request('conflicts/abort', { method: 'POST' }),
      onSuccess: () => core.invalidate(queryClient, ['changes', 'history']),
    });
  };

  return {
    useChangesQuery,
    useChangesNumstatQuery,
    useStatusQuery,
    useOperationStatusQuery,
    useDiffQuery,
    useStageMutation,
    useUnstageMutation,
    useCommitMutation,
    useForceUnlockMutation,
    useMarkResolvedMutation,
    useAbortConflictMutation,
    isFirstLoad: isFirstVersionControlLoad,
  };
};

const createDiscardCapability = (core: VersionControlCore) => {
  const useDiscardMutation = () => {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (paths: string[]) =>
        core.request('discard', {
          method: 'POST',
          body: { paths },
        }),
      onSuccess: () => core.invalidate(queryClient, ['changes']),
    });
  };

  return { useDiscardMutation };
};

export const createWorkspaceChangesCapability = (core: VersionControlCore) => ({
  ...createCommonChangesCapability(core),
  ...createDiscardCapability(core),
});

export const createKnowledgeBaseChangesCapability = (core: VersionControlCore) => ({
  ...createCommonChangesCapability(core),
  ...createDiscardCapability(core),
});

export const createMarketplaceChangesCapability = (core: VersionControlCore) => {
  const common = createCommonChangesCapability(core);
  return {
    ...common,
    ...createDiscardCapability(core),
    useChangesQuery: () => common.useChangesQuery(),
  };
};
