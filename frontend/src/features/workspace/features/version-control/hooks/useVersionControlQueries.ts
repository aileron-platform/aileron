/**
 * 版本控制 React Query Hooks
 *
 * 提供所有版本控制相關的 query 和 mutation hooks
 */

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { ApiClient, ApiError } from '@/shared/api/apiClient';
import { versionControlKeys, refreshVersionControlQueries } from '../lib/queryClient';
import type {
  VersionControlChangesResponse,
  VersionControlBranch,
  VersionControlStatus,
  VersionControlCommitListResponse,
  VersionControlCommitSummary,
  VersionControlFileChange,
  VersionControlCommitFilesResponse,
} from '../types';

interface UseVersionControlOptions {
  workspaceId: string;
  runtimeBaseUrl: string;
}

/**
 * 建立帶認證的 API Client
 */
function createVersionControlClient(runtimeBaseUrl: string) {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
}

/**
 * 建立 fetch 函數（使用 ApiClient）
 */
function createFetchFn(runtimeBaseUrl: string, workspaceId: string) {
  const client = createVersionControlClient(runtimeBaseUrl);

  return async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const fullPath = `/api/v1/workspaces/${workspaceId}/version-control/${path}`;

    // 根據 HTTP 方法選擇對應的 client 方法
    if (!init || !init.method || init.method === 'GET') {
      return await client.get<T>(fullPath);
    }

    const body = init.body ? JSON.parse(init.body as string) : undefined;

    switch (init.method) {
      case 'POST':
        return await client.post<T>(fullPath, body);
      case 'PUT':
        return await client.put<T>(fullPath, body);
      case 'PATCH':
        return await client.patch<T>(fullPath, body);
      case 'DELETE':
        return await client.delete<T>(fullPath);
      default:
        throw new Error(`Unsupported HTTP method: ${init.method}`);
    }
  };
}

function shouldRetryVersionControlQuery(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false;
  }

  return failureCount < 2;
}

/**
 * 使用 Changes Query
 */
export function useChangesQuery({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions, page: number = 1) {
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);

  return useQuery({
    queryKey: versionControlKeys.changesWithPage(workspaceId, page),
    queryFn: () => fetchVersionControl<VersionControlChangesResponse>(`changes?page=${page}&pageSize=100`),
    enabled: !!workspaceId && !!runtimeBaseUrl,
    retry: shouldRetryVersionControlQuery,
    staleTime: 0, // 確保每次 invalidate 都會立即 refetch
    refetchOnMount: true, // 確保組件掛載時會 refetch
    refetchOnWindowFocus: false, // 禁用窗口聚焦時的 refetch，避免不必要的請求
    placeholderData: (previousData) => previousData, // 保留上一次的數據，避免快速滾動時數據消失
  });
}

/**
 * 使用 Branches Query
 */
export function useBranchesQuery(
  { workspaceId, runtimeBaseUrl }: UseVersionControlOptions,
  includeRemote: boolean = true,
  search?: string
) {
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);
  
  return useQuery({
    queryKey: versionControlKeys.branchesWithFilter(workspaceId, includeRemote, search),
    queryFn: () => {
      const params = new URLSearchParams();
      params.set('includeRemote', String(includeRemote));
      if (search) params.set('search', search);
      return fetchVersionControl<{ branches: VersionControlBranch[] }>(`branches?${params}`);
    },
    enabled: !!workspaceId && !!runtimeBaseUrl,
    retry: shouldRetryVersionControlQuery,
    select: (data) => data.branches ?? [],
  });
}

/**
 * 使用 Status Query
 */
export function useStatusQuery({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions) {
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);
  
  return useQuery({
    queryKey: versionControlKeys.status(workspaceId),
    queryFn: () => fetchVersionControl<VersionControlStatus>('status'),
    enabled: !!workspaceId && !!runtimeBaseUrl,
    retry: shouldRetryVersionControlQuery,
  });
}

/**
 * 使用 Commits Infinite Query（無限滾動）
 */
export function useCommitsInfiniteQuery(
  { workspaceId, runtimeBaseUrl }: UseVersionControlOptions,
  pageSize: number = 20,
  branch?: string,
  search?: string
) {
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);
  
  return useInfiniteQuery({
    queryKey: versionControlKeys.commitsList(workspaceId, 1, pageSize, branch, search),
    queryFn: ({ pageParam = 1 }) => {
      const params = new URLSearchParams();
      params.set('page', String(pageParam));
      params.set('pageSize', String(pageSize));
      if (branch) params.set('branch', branch);
      if (search) params.set('search', search);
      return fetchVersionControl<VersionControlCommitListResponse>(`commits?${params}`);
    },
    getNextPageParam: (lastPage) => {
      const currentPage = lastPage.page ?? 1;
      const totalPages = Math.ceil((lastPage.total ?? 0) / (lastPage.pageSize ?? pageSize));
      return currentPage < totalPages ? currentPage + 1 : undefined;
    },
    initialPageParam: 1,
    enabled: !!workspaceId && !!runtimeBaseUrl,
    retry: shouldRetryVersionControlQuery,
  });
}

/**
 * 使用 Commit Files Query
 */
export function useCommitFilesQuery(
  { workspaceId, runtimeBaseUrl }: UseVersionControlOptions,
  commitId: string | null
) {
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);
  
  return useQuery({
    queryKey: versionControlKeys.commitFiles(workspaceId, commitId ?? ''),
    queryFn: () => fetchVersionControl<VersionControlCommitFilesResponse>(`commits/${commitId}/files`),
    enabled: !!workspaceId && !!runtimeBaseUrl && !!commitId,
    select: (data) => data.files ?? [],
  });
}

/**
 * 使用 Stage Mutation（樂觀更新）
 */
export function useStageMutation({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions) {
  const queryClient = useQueryClient();
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);

  return useMutation({
    mutationKey: ['versionControl', 'stage', workspaceId],
    mutationFn: async (paths: string[]) => {
      return fetchVersionControl('stage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, includeUntracked: true }),
      });
    },
    onSuccess: async () => {
      // 等待 100ms 確保 Git 索引更新完成
      await new Promise(resolve => setTimeout(resolve, 100));
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: false,
      });
    },
  });
}

/**
 * 使用 Unstage Mutation（樂觀更新）
 */
export function useUnstageMutation({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions) {
  const queryClient = useQueryClient();
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);

  return useMutation({
    mutationKey: ['versionControl', 'unstage', workspaceId],
    mutationFn: async (paths: string[]) => {
      return fetchVersionControl('unstage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths }),
      });
    },
    onSuccess: async () => {
      // 等待 100ms 確保 Git 索引更新完成
      await new Promise(resolve => setTimeout(resolve, 100));
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: false,
      });
    },
  });
}

/**
 * 使用 Commit Mutation
 */
export function useCommitMutation({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions) {
  const queryClient = useQueryClient();
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);

  return useMutation({
    mutationFn: async (message: string) => {
      return fetchVersionControl('commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
    },
    onSuccess: async () => {
      // 等待 100ms 確保 Git 提交完成並清除快取
      await new Promise(resolve => setTimeout(resolve, 100));
      await refreshVersionControlQueries(queryClient, workspaceId, {
        includeCommits: true,
      });
    },
  });
}

/**
 * 使用 Discard Mutation
 */
export function useDiscardMutation({ workspaceId, runtimeBaseUrl }: UseVersionControlOptions) {
  const queryClient = useQueryClient();
  const fetchVersionControl = createFetchFn(runtimeBaseUrl, workspaceId);
  
  return useMutation({
    mutationFn: async (paths: string[]) => {
      return fetchVersionControl('discard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths, resetMode: 'mixed' }),
      });
    },
    onSuccess: () => {
      return refreshVersionControlQueries(queryClient, workspaceId, {
        includeBranches: false,
      });
    },
  });
}
