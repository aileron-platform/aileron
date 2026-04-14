import { QueryClient } from "@tanstack/react-query";

export const versionControlKeys = {
  all: ["version-control"] as const,
  lists: () => [...versionControlKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...versionControlKeys.lists(), filters] as const,
  details: () => [...versionControlKeys.all, "detail"] as const,
  detail: (id: string) => [...versionControlKeys.details(), id] as const,

  // Changes
  changes: (workspaceId: string) => [...versionControlKeys.all, "changes", workspaceId] as const,
  changesWithPage: (workspaceId: string, page: number) => [...versionControlKeys.changes(workspaceId), "page", page] as const,

  // Branches
  branches: (workspaceId: string) => [...versionControlKeys.all, "branches", workspaceId] as const,
  branchesWithFilter: (workspaceId: string, includeRemote: boolean, search?: string) =>
    [...versionControlKeys.branches(workspaceId), { includeRemote, search }] as const,

  // Status
  status: (workspaceId: string) => [...versionControlKeys.all, "status", workspaceId] as const,

  // Commits
  commits: (workspaceId: string) => [...versionControlKeys.all, "commits", workspaceId] as const,
  commitsList: (workspaceId: string, page: number, pageSize: number, branch?: string, search?: string) =>
    [...versionControlKeys.commits(workspaceId), { page, pageSize, branch, search }] as const,

  // Commit Files
  commitFiles: (workspaceId: string, commitId: string) =>
    [...versionControlKeys.all, "commits", workspaceId, "files", commitId] as const,
};

export function invalidateVersionControl(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: versionControlKeys.all });
}

export function prefetchVersionControl(queryClient: QueryClient, id: string) {
  return queryClient.prefetchQuery({ queryKey: versionControlKeys.detail(id), queryFn: () => null });
}

interface RefreshVersionControlOptions {
  includeBranches?: boolean;
  includeCommits?: boolean;
}

type VersionControlQueryCategory = "changes" | "status" | "branches" | "commits";

const getWorkspaceQueryPrefixes = (
  workspaceId: string,
  options: RefreshVersionControlOptions,
): ReadonlyArray<readonly unknown[]> => {
  const prefixes: Array<readonly unknown[]> = [
    versionControlKeys.changes(workspaceId),
    versionControlKeys.status(workspaceId),
  ];

  if (options.includeBranches) {
    prefixes.push(versionControlKeys.branches(workspaceId));
  }

  if (options.includeCommits) {
    prefixes.push(versionControlKeys.commits(workspaceId));
  }

  return prefixes;
};

const categorizeQueryKey = (
  queryKey: readonly unknown[],
  workspaceId: string,
): VersionControlQueryCategory | null => {
  if (queryKey[0] !== "version-control" || queryKey[2] !== workspaceId) {
    return null;
  }

  switch (queryKey[1]) {
    case "changes":
    case "status":
    case "branches":
    case "commits":
      return queryKey[1];
    default:
      return null;
  }
};

export async function refreshVersionControlQueries(
  queryClient: QueryClient,
  workspaceId: string,
  options: RefreshVersionControlOptions = {},
) {
  const allowedPrefixes = getWorkspaceQueryPrefixes(workspaceId, options);
  const matchingQueries = queryClient
    .getQueryCache()
    .findAll({
      predicate: (query) => {
        const category = categorizeQueryKey(query.queryKey, workspaceId);
        if (!category) return false;
        return allowedPrefixes.some((prefix) =>
          prefix.every((part, index) => query.queryKey[index] === part),
        );
      },
    });

  if (matchingQueries.length === 0) {
    return;
  }

  await Promise.all(
    matchingQueries.map((query) =>
      queryClient.invalidateQueries({
        queryKey: query.queryKey,
        exact: true,
        refetchType: "none",
      }),
    ),
  );

  const results = await Promise.allSettled(
    matchingQueries.map((query) =>
      queryClient.refetchQueries({
        queryKey: query.queryKey,
        exact: true,
        type: "active",
      }),
    ),
  );

  const failures = results.flatMap((result, index) =>
    result.status === "rejected"
      ? [{ queryKey: matchingQueries[index]?.queryKey, reason: result.reason }]
      : [],
  );

  const blockingFailures = failures.filter(({ queryKey }) => {
    const category = queryKey ? categorizeQueryKey(queryKey, workspaceId) : null;
    return category === "changes" || category === "status";
  });

  if (blockingFailures.length > 0) {
    throw blockingFailures[0]?.reason;
  }
}
