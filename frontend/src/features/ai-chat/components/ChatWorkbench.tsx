import { useCallback, useState } from 'react';
import type { OutgoingMessage, Thread } from '../model/threadModel';
import { useCapabilities } from '../hooks/useCapabilities';
import { questionAnswerErrorKey, useThread } from '../hooks/useThread';
import { useThreads } from '../hooks/useThreads';
import { useMarkThreadRead } from '../hooks/useMarkThreadRead';
import type { ThreadSettings } from '../model/threadSettingsModel';
import { ChatView } from './ChatView';
import { NewTaskPromptBox, type NewTaskSubmitPayload } from './NewTaskPromptBox';

interface ChatWorkbenchProps {
  workspaceId: string;
  userId: string;
  selectedThreadId: string | null;
  onThreadSelected: (threadId: string) => void;
}

export const ChatWorkbench = ({
  workspaceId,
  userId,
  selectedThreadId,
  onThreadSelected,
}: ChatWorkbenchProps) => {
  const capabilities = useCapabilities(workspaceId);
  const threads = useThreads(workspaceId, { archived: false });
  const thread = useThread(selectedThreadId, workspaceId);
  const selectedThread = thread.query.data ?? null;
  const [newTaskDraft, setNewTaskDraft] = useState<Thread | null>(null);
  const workspaceCapabilities = capabilities.data;
  const showNewTask = !selectedThread || selectedThread.status === 'draft';
  const activeDraft = selectedThread?.status === 'draft' ? selectedThread : newTaskDraft;

  useMarkThreadRead({
    thread: showNewTask ? null : selectedThread,
    workspaceId,
    userId,
  });

  const handleNewTaskSubmit = useCallback(
    async ({ settings, message }: NewTaskSubmitPayload) => {
      const draft = activeDraft ?? await threads.createDraft.mutateAsync(settings);
      const submitted = await thread.submit.mutateAsync({
        targetThreadId: draft.id,
        message,
      });
      setNewTaskDraft(null);
      onThreadSelected(submitted.id);
    },
    [activeDraft, onThreadSelected, thread.submit, threads.createDraft],
  );

  const ensureNewTaskDraft = useCallback(
    async (settings: NewTaskSubmitPayload['settings']): Promise<Thread> => {
      if (activeDraft) return activeDraft;
      const draft = await threads.createDraft.mutateAsync(settings);
      setNewTaskDraft(draft);
      onThreadSelected(draft.id);
      return draft;
    },
    [activeDraft, onThreadSelected, threads.createDraft],
  );

  const handlePatchDraft = useCallback(
    (patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => {
      const targetThreadId = selectedThreadId ?? activeDraft?.id;
      if (!targetThreadId) return;
      threads.patchDraft.mutate({ threadId: targetThreadId, input: patch });
    },
    [activeDraft?.id, selectedThreadId, threads.patchDraft],
  );

  if (!workspaceCapabilities) {
    return null;
  }

  if (selectedThreadId && !selectedThread && thread.query.isLoading) {
    return null;
  }

  if (showNewTask) {
    return (
      <NewTaskPromptBox
        capabilities={workspaceCapabilities}
        draftThread={activeDraft}
        onEnsureDraft={ensureNewTaskDraft}
        onSubmit={handleNewTaskSubmit}
        onPatchDraft={handlePatchDraft}
      />
    );
  }

  return (
    <ChatView
      thread={selectedThread}
      capabilities={workspaceCapabilities}
      variant="workbench"
      showHeader={false}
      onSubmitDraft={(message) => {
        if (!selectedThreadId) return;
        thread.submit.mutate({ targetThreadId: selectedThreadId, message });
      }}
      onPostMessage={(message) => {
        if (!selectedThreadId) return;
        thread.postMessage.mutate({ targetThreadId: selectedThreadId, message });
      }}
      onAnswerQuestion={(messageId, answers, text) => {
        if (!selectedThreadId) return;
        thread.answerQuestion.mutate({
          targetThreadId: selectedThreadId,
          messageId,
          answers,
          text,
        });
      }}
      questionAnswerState={{
        messageId: thread.answerQuestion?.variables?.messageId ?? null,
        isPending: thread.answerQuestion?.isPending ?? false,
        errorKey: questionAnswerErrorKey(thread.answerQuestion?.error),
      }}
      onPatchDraft={handlePatchDraft}
      onRemoveQueuedMessage={(queuedMessageId) => {
        if (!selectedThreadId) return;
        thread.removeQueuedMessage.mutate({ targetThreadId: selectedThreadId, queuedMessageId });
      }}
      onCancel={() => {
        if (selectedThreadId) thread.cancel.mutate(selectedThreadId);
      }}
      onRetry={() => {
        if (selectedThreadId) thread.retry.mutate(selectedThreadId);
      }}
    />
  );
};
