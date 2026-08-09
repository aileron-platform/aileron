import { useCallback, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { QueryClientContext, type Query, type QueryClient } from '@tanstack/react-query';
import { ROUTES } from '@/shared/constants/routes';
import { fetchWorkspaceList } from '../api/workspaceListApi';
import type { WorkspaceListResponse } from '../model/workspaceTypes';
import { useWorkspaceSelection } from '../selection/WorkspaceSelectionContext';

const doesQueryContainWorkspaceIdentity = (
  query: Query,
  deletedWorkspaceId: string,
  deletedRuntimeBaseUrl?: string | null,
): boolean => {
  const serializedKey = JSON.stringify(query.queryKey);
  if (serializedKey.includes(deletedWorkspaceId)) {
    return true;
  }

  return Boolean(deletedRuntimeBaseUrl && serializedKey.includes(deletedRuntimeBaseUrl));
};

const cleanupDeletedWorkspaceQueries = async (
  queryClient: QueryClient,
  deletedWorkspaceId: string,
  deletedRuntimeBaseUrl?: string | null,
): Promise<void> => {
  const predicate = (query: Query) =>
    doesQueryContainWorkspaceIdentity(query, deletedWorkspaceId, deletedRuntimeBaseUrl);

  await queryClient.cancelQueries({ predicate });
  queryClient.removeQueries({ predicate });
};

const selectFallbackWorkspaceId = (
  workspaceList: WorkspaceListResponse,
  deletedWorkspaceId: string,
  currentSelectedWorkspaceId?: string | null,
): string | null => {
  const items = Array.isArray(workspaceList.items) ? workspaceList.items : [];

  if (
    currentSelectedWorkspaceId &&
    currentSelectedWorkspaceId !== deletedWorkspaceId &&
    items.some((workspace) => workspace.id === currentSelectedWorkspaceId)
  ) {
    return currentSelectedWorkspaceId;
  }

  return items.find((workspace) => workspace.id !== deletedWorkspaceId)?.id ?? null;
};

interface ResolveWorkspaceDeleteFallbackOptions {
  deletedWorkspaceId: string;
  deletedRuntimeBaseUrl?: string | null;
}

export const useWorkspaceDeleteFallback = () => {
  const navigate = useNavigate();
  const queryClient = useContext(QueryClientContext);
  const { selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspaceSelection();

  return useCallback(
    async ({ deletedWorkspaceId, deletedRuntimeBaseUrl }: ResolveWorkspaceDeleteFallbackOptions) => {
      if (queryClient) {
        await cleanupDeletedWorkspaceQueries(queryClient, deletedWorkspaceId, deletedRuntimeBaseUrl);
      }

      let workspaceList: WorkspaceListResponse;
      try {
        workspaceList = await fetchWorkspaceList();
      } catch {
        setSelectedWorkspaceId(null);
        navigate(ROUTES.workspace.root, { replace: true });
        return { fallbackWorkspaceId: null, workspaceList: null };
      }
      const fallbackWorkspaceId = selectFallbackWorkspaceId(
        workspaceList,
        deletedWorkspaceId,
        selectedWorkspaceId,
      );

      setSelectedWorkspaceId(fallbackWorkspaceId);
      navigate(
        fallbackWorkspaceId
          ? ROUTES.workspace.home(fallbackWorkspaceId)
          : ROUTES.workspace.root,
        { replace: true },
      );

      return { fallbackWorkspaceId, workspaceList };
    },
    [navigate, queryClient, selectedWorkspaceId, setSelectedWorkspaceId],
  );
};
