import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { OutgoingMessage, Thread, ThreadMutation, ThreadSummary } from '../model/threadModel';
import { ThreadApiError } from '../api/threadApi';
import { aiChatThreadQueryKey } from '../api/threadQueryKeys';
import { requireThreadApi, useThreadApi } from './useThreadApi';
import { mergeThreadTimelineSnapshot } from './useThreadTimeline';

export const questionAnswerErrorKey = (error: unknown): string | null => {
  if (error == null) return null;
  if (!(error instanceof ThreadApiError)) return 'aiChat.questionForm.submitFailed';
  if (
    error.status === 409 &&
    error.code === 'question_expired' &&
    typeof error.info.reason === 'string'
  ) {
    return 'aiChat.questionForm.expired';
  }
  return 'aiChat.questionForm.submitFailed';
};

export const useThread = (
  threadId: string | null | undefined,
  workspaceId: string,
) => {
  const queryClient = useQueryClient();
  const api = useThreadApi();

  const invalidateThread = async (nextThreadId: string): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: aiChatThreadQueryKey(workspaceId, nextThreadId) }),
      queryClient.invalidateQueries({ queryKey: ['ai-chat', 'threads', workspaceId] }),
    ]);
  };

  const removeThreadFromLists = (targetThreadId: string): void => {
    queryClient.setQueriesData<ThreadSummary[]>(
      { queryKey: ['ai-chat', 'threads', workspaceId] },
      (current) => current?.filter((thread) => thread.id !== targetThreadId) ?? current,
    );
  };

  const applyMutation = async (response: ThreadMutation): Promise<void> => {
    const { createdItemIds, changedItemIds, turns, executions, ...thread } = response;
    queryClient.setQueryData<Thread>(
      aiChatThreadQueryKey(workspaceId, response.id),
      thread,
    );
    const itemIds = [...new Set([...createdItemIds, ...changedItemIds])];
    if (itemIds.length > 0) {
      const snapshot = await requireThreadApi(api).getTimelineItems(response.id, itemIds);
      mergeThreadTimelineSnapshot(queryClient, workspaceId, response.id, snapshot);
    } else if (turns.length > 0 || executions.length > 0) {
      mergeThreadTimelineSnapshot(queryClient, workspaceId, response.id, {
        items: [],
        turns,
        executions,
      });
    }
    await queryClient.invalidateQueries({
      queryKey: ['ai-chat', 'threads', workspaceId],
    });
  };

  return {
    query: useQuery({
      queryKey: aiChatThreadQueryKey(workspaceId, threadId),
      queryFn: () => requireThreadApi(api).getThread(threadId ?? ''),
      enabled: Boolean(threadId) && api !== null,
    }),
    submit: useMutation({
      mutationFn: ({ targetThreadId, message }: { targetThreadId: string; message: OutgoingMessage }) =>
        requireThreadApi(api).submit(targetThreadId, message),
      onSuccess: applyMutation,
    }),
    postMessage: useMutation({
      mutationFn: ({ targetThreadId, message }: { targetThreadId: string; message: OutgoingMessage }) =>
        requireThreadApi(api).postMessage(targetThreadId, message),
      onSuccess: applyMutation,
    }),
    removeQueuedMessage: useMutation({
      mutationFn: ({
        targetThreadId,
        queuedMessageId,
      }: {
        targetThreadId: string;
        queuedMessageId: string;
      }) =>
        requireThreadApi(api).removeQueuedMessage(targetThreadId, queuedMessageId),
      onSuccess: (thread) => invalidateThread(thread.id),
      onError: (_error, variables) => invalidateThread(variables.targetThreadId),
    }),
    answerQuestion: useMutation({
      mutationFn: ({
        targetThreadId,
        messageId,
        answers,
        text,
      }: {
        targetThreadId: string;
        messageId: string;
        answers: Record<string, string | string[]>;
        text: string;
      }) =>
        requireThreadApi(api).answerQuestion(targetThreadId, messageId, {
          answers,
          text,
        }),
      onSuccess: applyMutation,
      onError: (_error, variables) => invalidateThread(variables.targetThreadId),
    }),
    cancel: useMutation({
      mutationFn: (targetThreadId: string) => requireThreadApi(api).cancel(targetThreadId),
      onSuccess: (thread) => invalidateThread(thread.id),
    }),
    retry: useMutation({
      mutationFn: (targetThreadId: string) => requireThreadApi(api).retry(targetThreadId),
      onSuccess: (thread) => invalidateThread(thread.id),
    }),
    archive: useMutation({
      mutationFn: (targetThreadId: string) => requireThreadApi(api).archive(targetThreadId),
      onSuccess: (thread) => {
        removeThreadFromLists(thread.id);
        return invalidateThread(thread.id);
      },
    }),
    deleteThread: useMutation({
      mutationFn: (targetThreadId: string) => requireThreadApi(api).deleteThread(targetThreadId),
      onMutate: (targetThreadId) => {
        removeThreadFromLists(targetThreadId);
      },
      onSuccess: (_result, targetThreadId) => {
        queryClient.removeQueries({ queryKey: aiChatThreadQueryKey(workspaceId, targetThreadId) });
      },
      onError: (_error, targetThreadId) => invalidateThread(targetThreadId),
    }),
  };
};
