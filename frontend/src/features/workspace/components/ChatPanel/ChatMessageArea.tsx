import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { cn } from '@/shared/utils/cn';
import { PermissionScope, PermissionRequestWidget } from '@/features/agent-tools/components/ClaudeToolWidget';
import AcpDecisionWidget from '@/features/agent-tools/components/AcpDecisionWidget';
import type { AgentMessage, ToolUseBlock, ToolResultBlock, AgenticTool, PermissionRequest, UserInputRequest, ToolDecisionType, ToolDecisionOutcome } from './agentSessionTypes';
import type { RunningToolExecution } from './agentSessionStore';
import { ChatMessageItem } from './ChatMessageItem';
import type { AskUserQuestionSubmitHandler } from './AgentContentBlockRenderer';

// 滾動重置延遲時間，確保滾動 effect 先執行完畢，避免競態條件
const SCROLL_RESET_DELAY_MS = 100;

export interface ChatMessageAreaProps {
  messages: AgentMessage[];
  hasActiveRequests: boolean;
  hasActiveConversation: boolean;
  onNewSession: () => void;
  typingIndicator: React.ReactNode;
  t: (key: string, params?: Record<string, string | number>) => string;
  showTimestamp?: boolean;
  // 分頁相關
  totalMessages?: number;
  isLoadingMoreMessages?: boolean;
  hasMoreMessages?: boolean;
  onLoadMoreMessages?: () => void;
  // 權限處理
  onPermissionDecision?: (requestId: string, allow: boolean, scope?: PermissionScope) => void;
  onAcpDecision?: (payload: {
    requestId: string;
    decisionType: ToolDecisionType;
    outcome: ToolDecisionOutcome;
    optionId?: string;
    scope?: PermissionScope;
    content?: string;
  }) => void;
  pendingPermission?: PermissionRequest | null;
  // User Input 狀態 (用於 AskUserQuestion 等工具)
  pendingUserInput?: UserInputRequest | null;
  // Agent 類型
  agentTool?: AgenticTool;
  // Streaming
  streamingContent?: string;
  isStreaming?: boolean;
  thinkingContent?: string;
  isThinking?: boolean;
  runningTools?: Map<string, RunningToolExecution>;
  // 預覽
  onPreviewMessage?: (message: AgentMessage) => void;
  previewLabel?: string;
  // AskUserQuestion
  onAskUserQuestionSubmit?: AskUserQuestionSubmitHandler;
  // 活躍任務 ID（用於區分即時和歷史訊息的工具顯示）
  activeTaskId?: string | null;
}

export const ChatMessageArea: React.FC<ChatMessageAreaProps> = ({
  messages: propMessages,
  hasActiveRequests,
  hasActiveConversation,
  onNewSession,
  typingIndicator,
  t,
  showTimestamp = true,
  totalMessages = 0,
  isLoadingMoreMessages = false,
  hasMoreMessages = false,
  onLoadMoreMessages,
  onPermissionDecision,
  onAcpDecision,
  pendingPermission,
  pendingUserInput,
  agentTool,
  streamingContent,
  isStreaming,
  thinkingContent,
  isThinking,
  runningTools = new Map(),
  onPreviewMessage,
  previewLabel,
  onAskUserQuestionSubmit,
  activeTaskId,
}) => {
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);
  const isInitialRender = useRef(true);

  // 滾動狀態管理 - 統一追蹤滾動相關狀態
  const scrollState = useRef({
    isLoadingMore: false,
    justLoadedMore: false,
    firstMessageId: null as string | null,
    previousLength: 0,
  }).current;

  const useStreamingTypewriter = (content: string, active: boolean, charsPerFrame: number = 3) => {
    const [displayText, setDisplayText] = useState('');
    const displayedLengthRef = useRef(0);
    const rafRef = useRef<number | null>(null);
    const contentRef = useRef(content);

    useEffect(() => {
      contentRef.current = content;

      // 停止時直接同步內容，避免殘留動畫
      if (!active) {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
        displayedLengthRef.current = content.length;
        setDisplayText(content);
        return;
      }

      // 若內容被重置（變短了，可能是新的 session），重新開始
      if (content.length < displayedLengthRef.current) {
        displayedLengthRef.current = 0;
      }

      // 取消之前的動畫
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }

      // 如果已經顯示完畢，不需要動畫
      if (displayedLengthRef.current >= content.length) {
        return;
      }

      const animate = () => {
        const currentContent = contentRef.current;
        const targetLength = currentContent.length;

        if (displayedLengthRef.current < targetLength) {
          // 每幀顯示多個字符，加快速度
          displayedLengthRef.current = Math.min(
            displayedLengthRef.current + charsPerFrame,
            targetLength
          );
          setDisplayText(currentContent.slice(0, displayedLengthRef.current));
          rafRef.current = requestAnimationFrame(animate);
        }
      };

      rafRef.current = requestAnimationFrame(animate);

      return () => {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);
      };
    }, [content, active, charsPerFrame]);

    return displayText;
  };

  const streamingDisplayText = useStreamingTypewriter(streamingContent || '', !!isStreaming);
  const thinkingDisplayText = useStreamingTypewriter(thinkingContent || '', !!isThinking);

  const toolUseIdsInMessages = useMemo(() => {
    const ids = new Set<string>();
    propMessages.forEach(msg => {
      msg.content_blocks?.forEach(block => {
        if (block.type === 'tool_use') {
          ids.add(block.id);
        }
      });
    });
    return ids;
  }, [propMessages]);

  const formatToolResult = useCallback((result: unknown): unknown => {
    if (agentTool && agentTool !== 'claude-code') {
      return result;
    }
    if (typeof result === 'string') return result;
    if (result && typeof result === 'object') {
      const record = result as Record<string, unknown>;
      if (record.error_message) return String(record.error_message);
      if (record.message) return String(record.message);
    }
    return JSON.stringify(result, null, 2);
  }, [agentTool]);

  // 先把 running tool 轉成暫時訊息，避免等到 tool_result 才出現
  const runningToolMessages = useMemo<AgentMessage[]>(() => {
    const tempMessages: AgentMessage[] = [];

    runningTools.forEach(tool => {
      if (toolUseIdsInMessages.has(tool.toolUseId)) return;

      const blocks: Array<ToolUseBlock | ToolResultBlock> = [
        {
          type: 'tool_use',
          id: tool.toolUseId,
          name: tool.toolName,
          input: tool.toolInput,
        } satisfies ToolUseBlock,
      ];

      if (tool.result !== undefined) {
        blocks.push({
          type: 'tool_result',
          tool_use_id: tool.toolUseId,
          content: formatToolResult(tool.result) as any,
          is_error: tool.isError,
        } satisfies ToolResultBlock);
      }

      tempMessages.push({
        message_id: `tool-placeholder-${tool.toolUseId}`,
        session_id: 'temp',
        role: 'assistant',
        type: 'assistant',
        created_at: tool.startedAt,
        index: propMessages.length + tempMessages.length,
        content_blocks: blocks,
        queued: false,
      });
    });

    return tempMessages;
  }, [propMessages.length, runningTools, toolUseIdsInMessages, formatToolResult]);

  // Combine messages with running tool placeholders and streaming content
  const messages = useMemo(() => {
    const combined = [...propMessages, ...runningToolMessages];

    if (!isStreaming && !isThinking && !streamingDisplayText) return combined;

    // Create a temporary message for streaming/thinking
    const tempMsg: AgentMessage = {
      message_id: 'streaming-temp',
      session_id: 'temp',
      role: 'assistant',
      type: 'assistant',
      created_at: new Date().toISOString(),
      index: combined.length,
      content_blocks: [],
      queued: false,
    };

    if (thinkingDisplayText || isThinking) {
      tempMsg.content_blocks!.push({
        type: 'thinking',
        thinking: thinkingDisplayText || ''
      });
    }

    if (streamingDisplayText || isStreaming) {
      // Assuming streaming content is text for now
      tempMsg.content_blocks!.push({
        type: 'text',
        text: streamingDisplayText || ''
      });
    }

    return [...combined, tempMsg];
  }, [propMessages, runningToolMessages, isStreaming, streamingDisplayText, isThinking, thinkingDisplayText]);

  const lastAssistantMessageId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.session_id !== 'temp' && !msg.queued) {
        return msg.message_id;
      }
    }
    return null;
  }, [messages]);
  const hasActiveResponseLifecycle = Boolean(isStreaming || isThinking || activeTaskId);

  // 檢查 pendingPermission 是否已存在於 messages 中，避免重複渲染
  const hasPendingInMessages = useMemo(() => {
    if (!pendingPermission) return false;
    return messages.some(
      msg => msg.type === 'permission_request' &&
             (msg.content_blocks?.[0] as any)?.request_id === pendingPermission.request_id
    );
  }, [messages, pendingPermission]);

  const hasMessages = messages.length > 0;
  const showInitialHint = !hasMessages && !hasActiveRequests && !hasActiveConversation;

  const containerClasses = cn(
    'flex h-full flex-col min-w-0 max-w-full overflow-x-hidden',
    showInitialHint ? 'px-6 py-4 justify-center' : 'py-2 gap-1'
  );

  const messageListClasses = 'flex flex-col w-full min-w-0 gap-1';

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = 'smooth') => {
      const viewport = scrollAreaRef.current?.querySelector(
        '[data-radix-scroll-area-viewport]'
      ) as HTMLDivElement | null;

      if (!viewport) {
        return;
      }

      viewport.scrollTo({
        top: viewport.scrollHeight,
        behavior,
      });
    },
    []
  );

  const handleApprove = useCallback((messageId: string, scope: PermissionScope) => {
    onPermissionDecision?.(messageId, true, scope);
  }, [onPermissionDecision]);

  const handleDeny = useCallback((messageId: string) => {
    onPermissionDecision?.(messageId, false);
  }, [onPermissionDecision]);

  // 處理 pending permission
  const handlePendingApprove = useCallback((messageId: string, scope: PermissionScope) => {
    if (pendingPermission) {
      onPermissionDecision?.(pendingPermission.request_id, true, scope);
    }
  }, [pendingPermission, onPermissionDecision]);

  const handlePendingDeny = useCallback((messageId: string) => {
    if (pendingPermission) {
      onPermissionDecision?.(pendingPermission.request_id, false);
    }
  }, [pendingPermission, onPermissionDecision]);

  // 滾動邏輯統一管理
  useEffect(() => {
    if (showInitialHint) return;

    // 追蹤載入狀態變化
    if (scrollState.isLoadingMore && !isLoadingMoreMessages) {
      scrollState.justLoadedMore = true;
    }
    scrollState.isLoadingMore = isLoadingMoreMessages;

    const currentFirstId = messages[0]?.message_id || null;
    const wasMessagesPrepended = scrollState.firstMessageId !== null &&
                                   currentFirstId !== null &&
                                   currentFirstId !== scrollState.firstMessageId;

    // 判斷是否應該跳過滾動
    const shouldSkipScroll = isLoadingMoreMessages ||
                             scrollState.justLoadedMore ||
                             wasMessagesPrepended;

    // 更新狀態
    scrollState.firstMessageId = currentFirstId;
    scrollState.previousLength = messages.length;

    if (shouldSkipScroll) {
      return;
    }

    const behavior = isInitialRender.current ? 'auto' : 'smooth';
    scrollToBottom(behavior);
    isInitialRender.current = false;

    // 延遲重置 justLoadedMore
    if (scrollState.justLoadedMore) {
      const timer = setTimeout(() => {
        scrollState.justLoadedMore = false;
      }, SCROLL_RESET_DELAY_MS);
      return () => clearTimeout(timer);
    }
  }, [messages, hasActiveRequests, scrollToBottom, showInitialHint, isLoadingMoreMessages, scrollState]);

  // 串流內容更新時的滾動
  useEffect(() => {
    if ((isStreaming || isThinking) && (streamingContent || thinkingContent)) {
      scrollToBottom('auto');
    }
  }, [streamingContent, thinkingContent, isStreaming, isThinking, scrollToBottom]);

  return (
    <div className="flex-1 overflow-hidden min-w-0">
      <ScrollArea ref={scrollAreaRef} className="h-full overflow-x-hidden [&>div>div]:!block">
        <div className={containerClasses}>
          {showInitialHint ? (
            <div className="flex flex-1 flex-col items-center justify-center px-6 text-center text-muted-foreground">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted/60 text-muted-foreground">
                <MessageSquare className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-foreground">
                {t('workspace.chat.empty.title')}
              </h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                {t('workspace.chat.empty.description')}
              </p>
              <Button variant="outline" size="sm" className="mt-4" onClick={onNewSession}>
                {t('workspace.chat.empty.action')}
              </Button>
            </div>
          ) : (
            <>
              {/* 載入更多歷史訊息按鈕 */}
              {hasMoreMessages && !isLoadingMoreMessages && onLoadMoreMessages && (
                <div className="flex justify-center py-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onLoadMoreMessages}
                    className="text-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary"
                  >
                    {totalMessages > 0
                      ? t('workspace.chat.messages.loadMoreWithCount', { count: totalMessages })
                      : t('workspace.chat.messages.loadMore')
                    }
                  </Button>
                </div>
              )}

              {/* 載入中指示器 */}
              {isLoadingMoreMessages && (
                <div className="flex justify-center py-3">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled
                    className="text-sm border-primary/20 bg-primary/5 text-primary"
                  >
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary mr-2"></div>
                    {t('workspace.chat.messages.loadingMore')}
                  </Button>
                </div>
              )}

              <div className={messageListClasses}>
                {messages
                  .map((message) => (
                    <ChatMessageItem
                      key={message.message_id}
                      message={message}
                      allMessages={messages}
                      showTimestamp={showTimestamp}
                      onApprove={handleApprove}
                      onDeny={handleDeny}
                      isLastAssistant={message.message_id === lastAssistantMessageId}
                      onOpenPreview={onPreviewMessage}
                      previewLabel={previewLabel}
                      agentTool={agentTool}
                      pendingPermission={pendingPermission}
                      pendingUserInput={pendingUserInput}
                      onAcpDecision={onAcpDecision}
                      onAskUserQuestionSubmit={onAskUserQuestionSubmit}
                      activeTaskId={activeTaskId}
                      hasActiveResponseLifecycle={hasActiveResponseLifecycle}
                    />
                  ))}
              </div>
            </>
          )}

          {/* Pending Permission Widget - 顯示在訊息列表底部（僅當 messages 中尚無相同請求時） */}
          {pendingPermission && !hasPendingInMessages && (
            <div className="px-4 py-2">
              {agentTool && agentTool !== 'claude-code' && agentTool !== 'codex' ? (
                <AcpDecisionWidget
                  requestId={pendingPermission.request_id}
                  status="pending"
                  decisionType="permission"
                  toolName={pendingPermission.tool_name}
                  toolInput={pendingPermission.tool_input}
                  toolCall={pendingPermission.tool_call}
                  options={pendingPermission.options}
                  onDecision={onAcpDecision
                    ? (payload) =>
                        onAcpDecision({
                          requestId: pendingPermission.request_id,
                          decisionType: 'permission',
                          outcome: payload.outcome,
                          optionId: payload.optionId,
                          scope: payload.scope,
                          content: payload.content,
                        })
                    : undefined}
                />
              ) : (
                <PermissionRequestWidget
                  status="pending"
                  isExpanded={true}
                  agentTool={agentTool || 'claude-code'}
                  input={{
                    tool_name: pendingPermission.tool_name,
                    tool_input: pendingPermission.tool_input,
                    permission_status: 'pending',
                    message_id: pendingPermission.request_id,
                  }}
                  requested_at={new Date().toISOString()}
                  onApprove={handlePendingApprove}
                  onCodexApprove={(messageId, scope) => handlePendingApprove(messageId, scope)}
                  onDeny={handlePendingDeny}
                />
              )}
            </div>
          )}

          {hasActiveRequests && typingIndicator}
        </div>
      </ScrollArea>
    </div>
  );
};

export default ChatMessageArea;
