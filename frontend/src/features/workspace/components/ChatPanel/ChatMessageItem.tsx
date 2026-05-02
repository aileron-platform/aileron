/**
 * ChatMessageItem - 訊息項目組件
 *
 * 使用 AgentContentBlockRenderer 顯示訊息內容和工具使用
 */

import React, { useMemo } from 'react';
import type { AgentMessage, AgenticTool, PermissionRequest, UserInputRequest, ToolDecisionType, ToolDecisionOutcome } from './agentSessionTypes';
import { AgentContentBlockRenderer, type AskUserQuestionSubmitHandler } from './AgentContentBlockRenderer';
import { PermissionScope } from '@/features/agent-tools/components/ClaudeToolWidget';
import { Button } from '@/shared/components/ui/button';
import { Eye } from 'lucide-react';

export interface ChatMessageItemProps {
  message: AgentMessage;
  allMessages: AgentMessage[];
  showTimestamp?: boolean;
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onDeny?: (messageId: string) => void;
  onOpenPreview?: (message: AgentMessage) => void;
  previewLabel?: string;
  isLastAssistant?: boolean;
  agentTool?: AgenticTool;
  /** 當前活躍的權限請求（來自 WebSocket） */
  pendingPermission?: PermissionRequest | null;
  /** 當前活躍的 User Input 請求（來自 WebSocket，用於 AskUserQuestion） */
  pendingUserInput?: UserInputRequest | null;
  /** ACP tool-decision 決策回調 */
  onAcpDecision?: (payload: {
    requestId: string;
    decisionType: ToolDecisionType;
    outcome: ToolDecisionOutcome;
    optionId?: string;
    scope?: PermissionScope;
    content?: string;
  }) => void;
  /** AskUserQuestion 提交回調 */
  onAskUserQuestionSubmit?: AskUserQuestionSubmitHandler;
  /** 當前活躍任務的 ID（用於區分即時和歷史訊息） */
  activeTaskId?: string | null;
  /** 當前 session 是否仍有 streaming/thinking 中的回應 */
  hasActiveResponseLifecycle?: boolean;
}

/**
 * 檢查訊息是否有可渲染的內容
 * - user 訊息：需要有 text 類型的區塊且內容不為空
 * - assistant 訊息：需要有非 tool_result 的區塊
 * - tool_result 訊息會在對應的 tool_use widget 中顯示，不需要獨立渲染
 */
function hasRenderableContent(message: AgentMessage): boolean {
  const blocks = message.content_blocks || [];

  if (message.role === 'user') {
    // user 訊息只渲染 text 類型
    return blocks.some(
      block => block.type === 'text' &&
               typeof (block as any).text === 'string' &&
               (block as any).text.trim().length > 0
    );
  }

  // assistant 訊息過濾掉 tool_result（它們會在對應的 tool_use 中顯示）
  // thinking 需要有實際內容才算可渲染，避免空白區塊造成「假 Thinking Process」
  const renderableBlocks = blocks.filter(b => {
    if (b.type === 'tool_result') return false;
    if (b.type === 'thinking') {
      const content = (b as any).thinking ?? (b as any).text ?? '';
      return typeof content === 'string' && content.trim().length > 0;
    }
    return true;
  });
  return renderableBlocks.length > 0;
}

/**
 * 訊息項目組件
 *
 * 使用 Agent Widget 系統完整顯示訊息內容
 */
export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  allMessages,
  showTimestamp = true,
  onApprove,
  onDeny,
  onOpenPreview,
  previewLabel,
  isLastAssistant = false,
  agentTool,
  pendingPermission,
  pendingUserInput,
  onAcpDecision,
  onAskUserQuestionSubmit,
  activeTaskId,
  hasActiveResponseLifecycle = false,
}) => {
  // 檢查是否有可渲染的內容，避免產生空的 div 元素造成間距不一致
  const shouldRender = useMemo(() => hasRenderableContent(message), [message]);
  const isMessageLifecycleActive = Boolean(
    hasActiveResponseLifecycle &&
    (message.task_id ? message.task_id === activeTaskId : isLastAssistant)
  );

  const hasQuestionForm = useMemo(
    () =>
      message.content_blocks?.some(
        block =>
          block.type === 'text' &&
          typeof (block as any).text === 'string' &&
          (block as any).text.includes('<question-form'),
      ) ?? false,
    [message.content_blocks],
  );

  const canPreview =
    message.role === 'assistant' &&
    message.session_id !== 'temp' &&
    isLastAssistant &&
    !isMessageLifecycleActive &&
    !hasQuestionForm &&
    onOpenPreview &&
    (
      message.content_blocks?.some(
        block => block.type === 'text' && typeof (block as any).text === 'string' && (block as any).text.trim().length > 0
      ) ||
      !!message.raw_sdk_message
    );

  // 如果沒有可渲染的內容且不需要顯示預覽按鈕，返回 null 避免產生空 div
  if (!shouldRender && !canPreview) {
    return null;
  }

  return (
    <div className="space-y-1">
      <AgentContentBlockRenderer
        message={message}
        allMessages={allMessages}
        showTimestamp={showTimestamp}
        onApprove={onApprove}
        onDeny={onDeny}
        agentTool={agentTool}
        pendingPermission={pendingPermission}
        pendingUserInput={pendingUserInput}
        onAcpDecision={onAcpDecision}
        onAskUserQuestionSubmit={onAskUserQuestionSubmit}
        activeTaskId={activeTaskId}
        isLastMessage={isLastAssistant}
      />
      {canPreview && (
        <div className="flex justify-center py-1">
          <div className="inline-flex max-w-[85%] items-center gap-1 border border-border/40 rounded-md bg-muted/40 px-2 py-1 shadow-sm">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-primary hover:text-primary hover:bg-primary/10"
              onClick={() => onOpenPreview?.(message)}
            >
              <Eye className="mr-1 h-3.5 w-3.5" />
              {previewLabel}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
