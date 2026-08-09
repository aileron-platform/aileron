import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { CreateDraftPayload, ListThreadsQuery, PatchDraftPayload } from '../api/threadApi';
import { aiChatThreadQueryKey, aiChatThreadsQueryKey } from '../api/threadQueryKeys';
import { requireThreadApi, useThreadApi } from './useThreadApi';

export const useThreads = (
  workspaceId: string,
  filters: ListThreadsQuery = { archived: false },
) => {
  const queryClient = useQueryClient();
  const api = useThreadApi();

  const invalidateList = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: aiChatThreadsQueryKey(workspaceId, filters) });
  };

  return {
    query: useQuery({
      queryKey: aiChatThreadsQueryKey(workspaceId, filters),
      queryFn: () => requireThreadApi(api).listThreads(workspaceId, filters),
      enabled: workspaceId.length > 0 && api !== null,
    }),
    createDraft: useMutation({
      mutationFn: (input: CreateDraftPayload) => requireThreadApi(api).createDraft(workspaceId, input),
      onSuccess: async (thread) => {
        queryClient.setQueryData(aiChatThreadQueryKey(workspaceId, thread.id), thread);
        await invalidateList();
      },
    }),
    patchDraft: useMutation({
      mutationFn: ({ threadId, input }: { threadId: string; input: PatchDraftPayload }) =>
        requireThreadApi(api).patchDraft(threadId, input),
      onSuccess: async (thread) => {
        queryClient.setQueryData(aiChatThreadQueryKey(workspaceId, thread.id), thread);
      },
    }),
  };
};
