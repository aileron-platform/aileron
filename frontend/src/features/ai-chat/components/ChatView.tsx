import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDown, ListOrdered, MessageSquare, Trash2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import type { OutgoingMessage, QueuedMessage, Thread } from '../model/threadModel';
import type { WorkspaceCapabilities } from '../model/threadCapabilitiesModel';
import { isLocked, isRunning } from '../model/threadStatusModel';
import type { ThreadSettings } from '../model/threadSettingsModel';
import type { AiChatHandoffRequest } from '../model/chatHandoffModel';
import { WorkingMessage } from './WorkingMessage';
import { QuestionAnswerContext } from './messages/QuestionAnswerContext';
import { ThreadTimeline } from './messages/ThreadTimeline';
import { ChatInputArea } from './ChatInputArea';
import { ChatThreadFeatureHeader } from './ChatThreadFeatureHeader';
import { ThreadErrorNotice } from './ThreadErrorNotice';

interface QuestionAnswerUiState {
  messageId: string | null;
  isPending: boolean;
  errorKey: string | null;
}

interface ChatViewProps {
  thread: Thread | null;
  capabilities: WorkspaceCapabilities;
  variant: 'workbench' | 'companion';
  onSubmitDraft: (message: OutgoingMessage) => void;
  onPostMessage: (message: OutgoingMessage) => void;
  onAnswerQuestion?: (
    messageId: string,
    answers: Record<string, string | string[]>,
    text: string,
  ) => void;
  questionAnswerState?: QuestionAnswerUiState;
  onPatchDraft: (patch: Partial<ThreadSettings> & { draftMessage?: OutgoingMessage | null }) => void;
  onRemoveQueuedMessage?: (queuedMessageId: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  showHeader?: boolean;
  draftHandoff?: AiChatHandoffRequest | null;
  onDraftHandoffApplied?: (handoffId: string) => void;
}

const BOTTOM_THRESHOLD_PX = 10;
const PROGRAMMATIC_SCROLL_FALLBACK_MS = 400;

export const ChatView = ({
  thread,
  capabilities,
  variant,
  onSubmitDraft,
  onPostMessage,
  onAnswerQuestion,
  questionAnswerState,
  onPatchDraft,
  onCancel,
  onRetry,
  showHeader,
  onRemoveQueuedMessage,
  draftHandoff,
  onDraftHandoffApplied,
}: ChatViewProps) => {
  const { t } = useI18n();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const autoScrollEnabledRef = useRef(true);
  const programmaticScrollRef = useRef(false);
  const userScrollDuringProgrammaticRef = useRef(false);
  const lastThreadIdRef = useRef<string | null>(null);
  const scrollFallbackTimeoutRef = useRef<number | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [inputOverlayHeight, setInputOverlayHeight] = useState(132);
  const threadId = thread?.id ?? null;
  const threadQueuedMessages = thread?.queuedMessages;
  const threadStatus = thread?.status;

  const isScrollAtBottom = useCallback((container: HTMLDivElement) => (
    container.scrollTop + container.clientHeight >= container.scrollHeight - BOTTOM_THRESHOLD_PX
  ), []);

  const clearProgrammaticScrollFallback = useCallback(() => {
    if (scrollFallbackTimeoutRef.current === null) return;
    window.clearTimeout(scrollFallbackTimeoutRef.current);
    scrollFallbackTimeoutRef.current = null;
  }, []);

  const enableProgrammaticScrollGuard = useCallback(() => {
    programmaticScrollRef.current = true;
    userScrollDuringProgrammaticRef.current = false;
    clearProgrammaticScrollFallback();
    scrollFallbackTimeoutRef.current = window.setTimeout(() => {
      programmaticScrollRef.current = false;
      userScrollDuringProgrammaticRef.current = false;
      scrollFallbackTimeoutRef.current = null;
    }, PROGRAMMATIC_SCROLL_FALLBACK_MS);
  }, [clearProgrammaticScrollFallback]);

  const scrollToBottom = useCallback(() => {
    enableProgrammaticScrollGuard();
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [enableProgrammaticScrollGuard]);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const nextIsAtBottom = isScrollAtBottom(container);
    setIsAtBottom(nextIsAtBottom);

    if (nextIsAtBottom) {
      programmaticScrollRef.current = false;
      userScrollDuringProgrammaticRef.current = false;
      clearProgrammaticScrollFallback();
      autoScrollEnabledRef.current = true;
      setAutoScrollEnabled(true);
      return;
    }

    if (programmaticScrollRef.current) {
      if (!userScrollDuringProgrammaticRef.current) {
        return;
      }
      programmaticScrollRef.current = false;
      userScrollDuringProgrammaticRef.current = false;
      clearProgrammaticScrollFallback();
      autoScrollEnabledRef.current = false;
      setAutoScrollEnabled(false);
      return;
    }

    autoScrollEnabledRef.current = false;
    setAutoScrollEnabled(false);
  }, [clearProgrammaticScrollFallback, isScrollAtBottom]);

  const markUserScrollIntent = useCallback(() => {
    if (!programmaticScrollRef.current) return;
    userScrollDuringProgrammaticRef.current = true;
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => setShowScrollButton(true), 1000);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    return () => {
      clearProgrammaticScrollFallback();
    };
  }, [clearProgrammaticScrollFallback]);

  useEffect(() => {
    if (!threadId) return;
    if (lastThreadIdRef.current === threadId) return;
    lastThreadIdRef.current = threadId;
    autoScrollEnabledRef.current = true;
    setAutoScrollEnabled(true);
    setIsAtBottom(true);
    const frame = window.requestAnimationFrame(() => {
      scrollToBottom();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [scrollToBottom, threadId]);

  useEffect(() => {
    if (!threadId || !autoScrollEnabled) return;
    const frame = window.requestAnimationFrame(() => {
      const container = scrollContainerRef.current;
      if (!container || (!autoScrollEnabledRef.current && !isScrollAtBottom(container))) return;
      scrollToBottom();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [
    autoScrollEnabled,
    inputOverlayHeight,
    isScrollAtBottom,
    scrollToBottom,
    threadId,
    thread?.version,
    threadQueuedMessages,
    threadStatus,
  ]);

  if (!thread) {
    return null;
  }

  const compact = variant === 'companion';
  const shouldShowHeader = showHeader ?? !compact;
  const isEmptyThread = thread.status === 'draft' && thread.queuedMessages.length === 0;
  const renderMessageText = (text: string) => (text.startsWith('aiChat.') ? t(text, { defaultValue: text }) : text);
  const renderQueuedMessages = (messages: QueuedMessage[]) => {
    if (messages.length === 0) {
      return null;
    }
    return (
      <div className="rounded-md border border-border/70 bg-muted/30">
        <div className="flex items-center gap-2 border-b border-border/70 px-3 py-2 text-xs font-medium text-muted-foreground">
          <ListOrdered className="h-3.5 w-3.5" aria-hidden="true" />
          <span>{t('aiChat.queue.title', { count: messages.length })}</span>
        </div>
        <div className="divide-y divide-border/70">
          {messages.map((message) => (
            <div key={message.id} className="flex min-w-0 items-start gap-2 px-3 py-2">
              <div className="min-w-0 flex-1 whitespace-pre-wrap text-sm text-foreground">
                {renderMessageText(message.text)}
              </div>
              {onRemoveQueuedMessage && (
                <button
                  type="button"
                  aria-label={t('aiChat.queue.remove')}
                  className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => onRemoveQueuedMessage(message.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <section
      data-testid={compact ? 'chat-view-compact' : 'chat-view'}
      className="relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-background"
    >
      {shouldShowHeader && <ChatThreadFeatureHeader thread={thread} onRetry={onRetry} />}

      <QuestionAnswerContext.Provider
        value={{
          canAnswer: !isRunning(thread.status) && isLocked(thread.status),
          answerStatus: (messageId) => {
            if (questionAnswerState?.messageId !== messageId) {
              return { isPending: false, errorKey: null };
            }
            return {
              isPending: questionAnswerState.isPending,
              errorKey: questionAnswerState.errorKey,
            };
          },
          answerQuestion: onAnswerQuestion ?? null,
        }}
      >
        <div
          ref={scrollContainerRef}
          data-testid="ai-chat-scroll-container"
          className="min-h-0 flex-1 overflow-y-auto px-3 pt-4"
          style={{ marginBottom: inputOverlayHeight, paddingBottom: 16 }}
          onScroll={handleScroll}
          onWheel={markUserScrollIntent}
          onTouchMove={markUserScrollIntent}
          onPointerDown={markUserScrollIntent}
        >
          <div className={cn('mx-auto flex w-full flex-col gap-3', compact ? 'max-w-full' : 'max-w-4xl')}>
            {isEmptyThread ? (
              <div className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground">
                <MessageSquare className="h-5 w-5" aria-hidden="true" />
                <span>{t('aiChat.messages.empty')}</span>
              </div>
            ) : (
              <ThreadTimeline
                workspaceId={thread.workspaceId}
                threadId={thread.id}
                scrollContainerRef={scrollContainerRef}
              />
            )}
            <ThreadErrorNotice thread={thread} onRetry={onRetry} />
            <WorkingMessage status={thread.status} />
            {renderQueuedMessages(thread.queuedMessages)}
            <div ref={messagesEndRef} className="min-h-6 shrink-0" />
          </div>
        </div>
      </QuestionAnswerContext.Provider>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20">
        <div className="absolute inset-x-0 top-0 flex h-0 -translate-y-5 items-center justify-center">
          <button
            type="button"
            aria-label={t('aiChat.messages.scrollToBottom')}
            data-testid="ai-chat-scroll-to-bottom"
            onClick={() => {
              autoScrollEnabledRef.current = true;
              setAutoScrollEnabled(true);
              scrollToBottom();
            }}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full border border-border bg-background/90 text-foreground shadow-md backdrop-blur transition-all duration-200 hover:bg-accent hover:text-accent-foreground',
              showScrollButton && !isAtBottom ? 'pointer-events-auto opacity-100' : 'pointer-events-none translate-y-[-2rem] opacity-0',
            )}
          >
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <ChatInputArea
          thread={thread}
          capabilities={capabilities}
          onSubmitDraft={onSubmitDraft}
          onPostMessage={onPostMessage}
          onCancel={onCancel}
          onPatchDraft={(patch) => {
            if (isLocked(thread.status) && patch.agenticTool && patch.agenticTool !== thread.agenticTool) {
              return;
            }
            onPatchDraft(patch);
          }}
          onHeightChange={setInputOverlayHeight}
          draftHandoff={draftHandoff}
          onDraftHandoffApplied={onDraftHandoffApplied}
        />
      </div>
    </section>
  );
};
