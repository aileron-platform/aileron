import type { QueryClient, QueryKey } from '@tanstack/react-query';
import {
  ApiClient,
  ApiError,
  type ApiClientUnauthorizedBehavior,
} from '@/shared/api/apiClient';

type VersionControlScope = 'workspaces' | 'knowledge-bases' | 'marketplace';
export type VersionControlCapabilityGroup = 'changes' | 'history' | 'remote';

interface VersionControlCoreOptions {
  baseUrl: string;
  executionAudience?: 'workspace-runtime';
  scope: VersionControlScope;
  id?: string;
  targetIdentity?: string;
  resolveOperation?: (operation: string) => string;
  gitQueriesEnabled: boolean;
  unauthorizedBehavior?: ApiClientUnauthorizedBehavior;
}

interface VersionControlRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
}

const SHARED_INSTANCE = 'shared';
const DEFAULT_TARGET = 'default';

export const shouldRetryVersionControlQuery = (
  failureCount: number,
  error: unknown,
): boolean => {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false;
  }
  return failureCount < 2;
};

export const isFirstVersionControlLoad = (
  result: { isLoading: boolean; data: unknown },
): boolean => result.isLoading && !result.data;

export const createVersionControlCore = (options: VersionControlCoreOptions) => {
  const client = new ApiClient({
    baseUrl: options.baseUrl,
    executionAudience: options.executionAudience,
    unauthorizedBehavior: options.unauthorizedBehavior,
  });
  const instanceToken = options.id ?? SHARED_INSTANCE;
  const targetToken = options.targetIdentity ?? DEFAULT_TARGET;
  const identity = JSON.stringify([
    options.scope,
    instanceToken,
    targetToken,
  ]);
  const identityEnabled = Boolean(options.baseUrl)
    && (options.scope === 'marketplace' || Boolean(options.id));
  const gitQueriesEnabled = identityEnabled && options.gitQueriesEnabled;

  const key = (
    group: VersionControlCapabilityGroup,
    operation: string,
    ...parts: unknown[]
  ): readonly unknown[] => [
    'version-control',
    options.scope,
    instanceToken,
    targetToken,
    group,
    operation,
    ...parts,
  ];

  const buildPath = (operation: string): string => {
    const scopePath = options.id
      ? `${options.scope}/${encodeURIComponent(options.id)}`
      : options.scope;
    return `/${scopePath}/version-control/${options.resolveOperation?.(operation) ?? operation}`;
  };

  const request = async <T>(
    operation: string,
    requestOptions: VersionControlRequestOptions = {},
  ): Promise<T> => {
    const path = buildPath(operation);

    switch (requestOptions.method ?? 'GET') {
      case 'GET':
        return client.get<T>(path);
      case 'POST':
        return client.post<T>(path, requestOptions.body);
      case 'PUT':
        return client.put<T>(path, requestOptions.body);
      case 'PATCH':
        return client.patch<T>(path, requestOptions.body);
      case 'DELETE':
        return client.delete<T>(path);
      default:
        throw new Error('Unsupported version control request method');
    }
  };

  const matchesGroups = (
    queryKey: QueryKey,
    groups: readonly VersionControlCapabilityGroup[],
  ): boolean => (
    queryKey[0] === 'version-control'
    && queryKey[1] === options.scope
    && queryKey[2] === instanceToken
    && queryKey[3] === targetToken
    && groups.includes(queryKey[4] as VersionControlCapabilityGroup)
  );

  const invalidate = (
    queryClient: QueryClient,
    groups: readonly VersionControlCapabilityGroup[],
  ) => queryClient.invalidateQueries({
    predicate: query => matchesGroups(query.queryKey, groups),
  });

  const refresh = async (
    queryClient: QueryClient,
    groups: readonly VersionControlCapabilityGroup[],
  ): Promise<void> => {
    const matchingQueries = queryClient.getQueryCache().findAll({
      predicate: query => matchesGroups(query.queryKey, groups),
    });

    if (matchingQueries.length === 0) {
      return;
    }

    await Promise.all(matchingQueries.map(query => queryClient.invalidateQueries({
      queryKey: query.queryKey,
      exact: true,
      refetchType: 'none',
    })));

    const results = await Promise.allSettled(matchingQueries.map(query =>
      queryClient.refetchQueries({
        queryKey: query.queryKey,
        exact: true,
        type: 'active',
      }, {
        throwOnError: true,
      }),
    ));

    const blockingFailure = results.find((result, index) =>
      result.status === 'rejected'
      && matchingQueries[index]?.queryKey[4] === 'changes',
    );
    if (blockingFailure?.status === 'rejected') {
      throw blockingFailure.reason;
    }
  };

  return {
    identity,
    identityEnabled,
    gitQueriesEnabled,
    key,
    request,
    invalidate,
    refresh,
  };
};

export type VersionControlCore = ReturnType<typeof createVersionControlCore>;
