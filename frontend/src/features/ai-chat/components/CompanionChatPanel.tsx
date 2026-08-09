import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare } from 'lucide-react';
import { useToast } from '@/shared/components/ui/use-toast';
import { collapsedSidebarActionClass } from '@/shared/components/layout/CollapsedSidebarControls';
import { useI18n } from '@/shared/hooks/useI18n';
import { getLastThreadId, setLastThreadId } from '../storage/aiChatStorage';
import type { OutgoingMessage } from '../model/threadModel';
import { sortThreadSummaries } from '../model/threadListModel';
import { resolveThreadSelection } from '../model/threadSelectionModel';
import { useCapabilities } from '../hooks/useCapabilities';
import { useMarkThreadRead } from '../hooks/useMarkThreadRead';
import { questionAnswerErrorKey, useThread } from '../hooks/useThread';
import { useThreads } from '../hooks/useThreads';
import type { ThreadSettings } from '../model/threadSettingsModel';
import { useAiChatIntegration } from '../contexts/AiChatIntegrationContext';
import { applyAiChatHandoff } from '../model/chatHandoffModel';
import { ChatView } from './ChatView';
import { ThreadActionMenu } from './ThreadActionMenu';
import { ThreadSwitcher } from './ThreadSwitcher';

interface CompanionChatPanelProps {
  workspaceId: string;
  userId: string;
}

export const CompanionChatPanel = ({
  workspaceId,
  userId,
}: CompanionChatPanelProps) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const {
    pendingHandoff,
    completeHandoff,
    failHandoff,
  } = useAiChatIntegration();
  const threads = useThreads(workspaceId, { archived: false });
  const capabilities = useCapabilities(workspaceId);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const creatingHandoffThreadIdsRef = useRef(new Set<string>());
  const submittingHandoffIdsRef = useRef(new Set<string>());
  const activeThreads = useMemo(
    () => sortThreadSummaries(threads.query.data ?? [], 'activity', t),
    [threads.query.data, t],
  );
  const thread = useThread(selectedThreadId, workspaceId);
  const selectedThread = thread.query.data ?? null;
  const selectedThreadSummary = activeThreads.find((item) => item.id === selectedThreadId) ?? null;
  const selectedThreadActionTarget = selectedThreadSummary
    ? { id: selectedThreadSummary.id, archived: selectedThreadSummary.archived }
    : selectedThread
      ? { id: selectedThread.id, archived: selectedThread.archived }
      : null;

  useEffect(() => {
    const resolvedThreadId = resolveThreadSelection({
      threads: activeThreads.filter((thread) => !thread.archived),
      getSavedThreadId: () => getLastThreadId(userId, workspaceId),
    });
    setSelectedThreadId(resolvedThreadId);
    if (resolvedThreadId) setLastThreadId(userId, workspaceId, resolvedThreadId);
  }, [activeThreads, userId, workspaceId]);

  useMarkThreadRead({
    thread: selectedThread,
    workspaceId,
    userId,
  });

  const handleSelect = useCallback((threadId: string) => {
    setLastThreadId(userId, workspaceId, threadId);
    setSelectedThreadId(threadId);
  }, [userId, workspaceId]);

  const createDefaultDraft = useCallback(async () => {
    const workspaceCapabilities = capabilities.data;
    const tool = workspaceCapabilities?.tools.find((item) => item.id === workspaceCapabilities.defaultTool)
      ?? workspaceCapabilities?.tools[0];
    if (!tool) return null;

    const draft = await threads.createDraft.mutateAsync({
      agenticTool: tool.id,
      model: tool.defaultModel,
      claudeMode: tool.defaultMode,
    });
    handleSelect(draft.id);
    return draft;
  }, [capabilities.data, handleSelect, threads.createDraft]);

  const handleNewThread = () => {
    void createDefaultDraft();
  };

  const handlePatchDraft = useCallback(
    (patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => {
      if (!selectedThreadId) return;
      threads.patchDraft.mutate({ threadId: selectedThreadId, input: patch });
    },
    [selectedThreadId, threads.patchDraft],
  );

  const selectFallbackAfterRemoval = useCallback((removedThreadId: string) => {
    const fallbackThreadId = activeThreads.find((item) => item.id !== removedThreadId)?.id ?? null;
    setSelectedThreadId(fallbackThreadId);
    if (fallbackThreadId) setLastThreadId(userId, workspaceId, fallbackThreadId);
  }, [activeThreads, userId, workspaceId]);

  const handleArchiveThread = (threadId: string) => {
    thread.archive.mutate(threadId, {
      onSuccess: () => selectFallbackAfterRemoval(threadId),
    });
  };

  const handleDeleteThread = (threadId: string) => {
    thread.deleteThread.mutate(threadId, {
      onSuccess: () => selectFallbackAfterRemoval(threadId),
    });
  };

  const handleCopyThreadId = (threadId: string) => {
    void navigator.clipboard?.writeText(threadId).then(() => {
      toast({
        title: t('aiChat.threadActions.copyThreadIdSuccess.title'),
        description: t('aiChat.threadActions.copyThreadIdSuccess.description'),
        variant: 'success',
      });
    });
  };

  useEffect(() => {
    if (!pendingHandoff || pendingHandoff.workspaceId !== workspaceId) return;
    if (selectedThreadId) return;
    if (creatingHandoffThreadIdsRef.current.has(pendingHandoff.id)) return;
    creatingHandoffThreadIdsRef.current.add(pendingHandoff.id);
    void createDefaultDraft()
      .then((draft) => {
        if (!draft) {
          failHandoff?.(pendingHandoff.id, new Error('No AI Chat agent is available'));
        }
      })
      .catch((error) => failHandoff?.(pendingHandoff.id, error))
      .finally(() => creatingHandoffThreadIdsRef.current.delete(pendingHandoff.id));
  }, [
    createDefaultDraft,
    failHandoff,
    pendingHandoff,
    selectedThreadId,
    workspaceId,
  ]);

  useEffect(() => {
    if (!pendingHandoff || pendingHandoff.delivery !== 'submit') return;
    if (pendingHandoff.workspaceId !== workspaceId || !selectedThreadId || !selectedThread) return;
    if (submittingHandoffIdsRef.current.has(pendingHandoff.id)) return;
    submittingHandoffIdsRef.current.add(pendingHandoff.id);
    const message: OutgoingMessage = {
      text: applyAiChatHandoff('', pendingHandoff, selectedThread.agenticTool),
      attachments: [],
    };
    const mutation = selectedThread.status === 'draft'
      ? thread.submit
      : thread.postMessage;
    void mutation.mutateAsync({
      targetThreadId: selectedThreadId,
      message,
    })
      .then(() => completeHandoff?.(pendingHandoff.id))
      .catch((error) => failHandoff?.(pendingHandoff.id, error))
      .finally(() => submittingHandoffIdsRef.current.delete(pendingHandoff.id));
  }, [
    completeHandoff,
    failHandoff,
    pendingHandoff,
    selectedThread,
    selectedThreadId,
    thread.postMessage,
    thread.submit,
    workspaceId,
  ]);

  return (
    <>
      <div data-testid="ai-chat-companion-switcher-row" className="flex h-10 shrink-0 items-center gap-1 border-b border-border/70 bg-card px-3">
        <ThreadSwitcher
          workspaceId={workspaceId}
          userId={userId}
          threads={activeThreads}
          selectedThreadId={selectedThreadId}
          onSelect={handleSelect}
          onNewThread={handleNewThread}
        />
        <ThreadActionMenu
          thread={selectedThreadActionTarget}
          onArchive={handleArchiveThread}
          onDelete={handleDeleteThread}
          onCopyThreadId={handleCopyThreadId}
          includeCopyThreadId
          includeDisplaySettings
          triggerClassName={`${collapsedSidebarActionClass} shrink-0`}
        />
      </div>

      <div data-testid="ai-chat-companion-view-slot" className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {capabilities.data && selectedThreadId && selectedThread ? (
          <ChatView
            thread={selectedThread}
            capabilities={capabilities.data}
            variant="companion"
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
            draftHandoff={pendingHandoff?.delivery === 'draft' ? pendingHandoff : null}
            onDraftHandoffApplied={(handoffId) => completeHandoff?.(handoffId)}
          />
        ) : (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 bg-background px-4 text-center text-sm text-muted-foreground">
            <MessageSquare className="h-5 w-5" aria-hidden="true" />
            <span>{t('aiChat.companion.empty')}</span>
          </div>
        )}
      </div>
    </>
  );
};
