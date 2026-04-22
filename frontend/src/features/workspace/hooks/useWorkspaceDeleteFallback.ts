import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient, type Query, type QueryClient } from '@tanstack/react-query';
import { useNavigation } from '@/app/providers/NavigationProvider';
import { ROUTES } from '@/shared/constants/routes';
import type { WorkspaceListResponse } from '../providers/workspaceState.types';
import { fetchWorkspaceList } from '../services/workspaceRuntimeApi';

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

export const cleanupDeletedWorkspaceQueries = async (
  queryClient: QueryClient,
  deletedWorkspaceId: string,
  deletedRuntimeBaseUrl?: string | null,
): Promise<void> => {
  const predicate = (query: Query) =>
    doesQueryContainWorkspaceIdentity(query, deletedWorkspaceId, deletedRuntimeBaseUrl);

  await queryClient.cancelQueries({ predicate });
  queryClient.removeQueries({ predicate });
};

export const selectFallbackWorkspaceId = (
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
  const queryClient = useQueryClient();
  const { state, dispatch } = useNavigation();

  return useCallback(
    async ({ deletedWorkspaceId, deletedRuntimeBaseUrl }: ResolveWorkspaceDeleteFallbackOptions) => {
      await cleanupDeletedWorkspaceQueries(queryClient, deletedWorkspaceId, deletedRuntimeBaseUrl);

      const workspaceList = await fetchWorkspaceList();
      const fallbackWorkspaceId = selectFallbackWorkspaceId(
        workspaceList,
        deletedWorkspaceId,
        state.selectedWorkspaceId,
      );

      dispatch({ type: 'SET_SELECTED_WORKSPACE', payload: fallbackWorkspaceId });
      navigate(fallbackWorkspaceId ? ROUTES.WORKSPACES : ROUTES.WORKSPACE_WIZARD, { replace: true });

      return { fallbackWorkspaceId, workspaceList };
    },
    [dispatch, navigate, queryClient, state.selectedWorkspaceId],
  );
};
