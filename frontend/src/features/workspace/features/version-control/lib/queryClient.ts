import { QueryClient } from "@tanstack/react-query";

export const versionControlKeys = {
  all: ["version-control"] as const,
  lists: () => [...versionControlKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...versionControlKeys.lists(), filters] as const,
  details: () => [...versionControlKeys.all, "detail"] as const,
  detail: (id: string) => [...versionControlKeys.details(), id] as const,

  // Changes
  changes: (workspaceId: string, contextId?: string | null) =>
    [...versionControlKeys.all, "changes", workspaceId, contextId ?? "primary"] as const,
  changesWithPage: (workspaceId: string, page: number, contextId?: string | null) =>
    [...versionControlKeys.changes(workspaceId, contextId), "page", page] as const,

  // Branches
  branches: (workspaceId: string, contextId?: string | null) =>
    [...versionControlKeys.all, "branches", workspaceId, contextId ?? "primary"] as const,
  branchesWithFilter: (workspaceId: string, includeRemote: boolean, search?: string, contextId?: string | null) =>
    [...versionControlKeys.branches(workspaceId, contextId), { includeRemote, search }] as const,

  // Status
  status: (workspaceId: string, contextId?: string | null) =>
    [...versionControlKeys.all, "status", workspaceId, contextId ?? "primary"] as const,

  contexts: (workspaceId: string) => [...versionControlKeys.all, "contexts", workspaceId] as const,

  // Commits
  commits: (workspaceId: string, contextId?: string | null) =>
    [...versionControlKeys.all, "commits", workspaceId, contextId ?? "primary"] as const,
  commitsList: (
    workspaceId: string,
    page: number,
    pageSize: number,
    branch?: string,
    search?: string,
    contextId?: string | null,
  ) => [...versionControlKeys.commits(workspaceId, contextId), { page, pageSize, branch, search }] as const,

  // Commit Files
  commitFiles: (workspaceId: string, commitId: string, contextId?: string | null) =>
    [...versionControlKeys.all, "commits", workspaceId, contextId ?? "primary", "files", commitId] as const,
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
  includeContexts?: boolean;
  contextId?: string | null;
}

type VersionControlQueryCategory = "changes" | "status" | "branches" | "commits";

const getWorkspaceQueryPrefixes = (
  workspaceId: string,
  options: RefreshVersionControlOptions,
): ReadonlyArray<readonly unknown[]> => {
  const contextId = options.contextId ?? "primary";
  const prefixes: Array<readonly unknown[]> = [
    versionControlKeys.changes(workspaceId, contextId),
    versionControlKeys.status(workspaceId, contextId),
  ];

  if (options.includeBranches) {
    prefixes.push(versionControlKeys.branches(workspaceId, contextId));
  }

  if (options.includeCommits) {
    prefixes.push(versionControlKeys.commits(workspaceId, contextId));
  }

  if (options.includeContexts) {
    prefixes.push(versionControlKeys.contexts(workspaceId));
  }

  return prefixes;
};

const categorizeQueryKey = (
  queryKey: readonly unknown[],
  workspaceId: string,
): VersionControlQueryCategory | null => {
  if (queryKey[0] !== "version-control") {
    return null;
  }

  if (queryKey[1] === "contexts") {
    return null;
  }

  if (queryKey[2] !== workspaceId) {
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
        if (query.queryKey[0] !== "version-control") {
          return false;
        }

        if (query.queryKey[1] === "contexts") {
          return options.includeContexts === true && query.queryKey[2] === workspaceId;
        }

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
