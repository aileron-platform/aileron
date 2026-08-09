import type { Query, QueryClient } from '@tanstack/react-query';

export const WORKSPACE_AVAILABILITY_QUERY_KEY = 'workspace-availability';

export const workspaceAvailabilityQueryKey = (workspaceId: string) => [
  WORKSPACE_AVAILABILITY_QUERY_KEY,
  workspaceId,
] as const;

const returnTargetStorageKey = (workspaceId: string) =>
  `workspace-availability-return:${workspaceId}`;

export const readWorkspaceAvailabilityReturnTarget = (
  workspaceId: string,
): string | null => {
  try {
    return window.sessionStorage.getItem(returnTargetStorageKey(workspaceId));
  } catch {
    return null;
  }
};

export const persistWorkspaceAvailabilityReturnTarget = (
  workspaceId: string,
  target: string,
): void => {
  try {
    window.sessionStorage.setItem(returnTargetStorageKey(workspaceId), target);
  } catch {
    // Session storage is optional; the machine state remains authoritative.
  }
};

export const clearWorkspaceAvailabilityReturnTarget = (
  workspaceId: string,
): void => {
  try {
    window.sessionStorage.removeItem(returnTargetStorageKey(workspaceId));
  } catch {
    // Session storage is optional.
  }
};

const containsBoundedPath = (value: string, path: string): boolean => {
  let searchFrom = 0;
  while (searchFrom < value.length) {
    const index = value.indexOf(path, searchFrom);
    if (index < 0) return false;
    const nextCharacter = value[index + path.length];
    if (!nextCharacter || '/?#&'.includes(nextCharacter)) return true;
    searchFrom = index + path.length;
  }
  return false;
};

const queryBelongsToWorkspaceExecutionPlane = (
  query: Pick<Query, 'queryKey'>,
  workspaceId: string,
): boolean => {
  if (query.queryKey[0] === WORKSPACE_AVAILABILITY_QUERY_KEY) return false;

  const encodedWorkspaceId = encodeURIComponent(workspaceId);
  const workspacePaths = [
    `/workspaces/${workspaceId}`,
    `/workspaces/${encodedWorkspaceId}`,
  ];
  return query.queryKey.some((part) => (
    typeof part === 'string'
    && (
      part === workspaceId
      || workspacePaths.some(path => containsBoundedPath(part, path))
      || part.includes(`-${workspaceId}.`)
    )
  ));
};

export const clearWorkspaceExecutionQueries = async (
  queryClient: QueryClient,
  workspaceId: string,
): Promise<void> => {
  const predicate = (query: Query) =>
    queryBelongsToWorkspaceExecutionPlane(query, workspaceId);
  const cancellation = queryClient.cancelQueries({ predicate });
  queryClient.removeQueries({ predicate });
  await cancellation;
};

export const clearRevokedWorkspaceAvailabilitySession = async (
  queryClient: QueryClient,
  workspaceId: string,
): Promise<void> => {
  clearWorkspaceAvailabilityReturnTarget(workspaceId);
  const predicate = (query: Query) => (
    (
      query.queryKey[0] === WORKSPACE_AVAILABILITY_QUERY_KEY
      && query.queryKey[1] === workspaceId
    )
    || queryBelongsToWorkspaceExecutionPlane(query, workspaceId)
  );
  const cancellation = queryClient.cancelQueries({ predicate });
  queryClient.removeQueries({ predicate });
  await cancellation;
};
