/**
 * AgentContentBlockRenderer - 訊息內容渲染器
 *
 * 使用 ClaudeToolWidget 渲染工具呼叫
 * 呈現風格：使用者訊息靠右，助手訊息靠左（無卡片包裝）
 */

import React from 'react';
import ClaudeToolWidget, { ClaudeToolType, PermissionScope } from '@/features/agent-tools/components/ClaudeToolWidget';
import AcpToolWidget from '@/features/agent-tools/components/AcpToolWidget';
import AcpDecisionWidget from '@/features/agent-tools/components/AcpDecisionWidget';
import { MarkdownRenderer } from '@/features/workspace/components/MarkdownRenderer';
import { createLogger } from '@/shared/services/logger';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { AgentMessage, ContentBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock, SystemBlock, SystemCompleteBlock, SystemStatusBlock, AgenticTool, PermissionRequest, UserInputRequest, ToolDecisionType, ToolDecisionOutcome } from './agentSessionTypes';
import { resolveAcpToolWidgetTypeWithKind } from './agentSessionTypes';

const logger = createLogger('AgentContentBlockRenderer');

/** AskUserQuestion 提交答案的回調類型 */
export type AskUserQuestionSubmitHandler = (
  toolUseId: string,
  answers: Record<string, string | string[]>
) => void;

interface AgentContentBlockRendererProps {
  message: AgentMessage;
  allMessages: AgentMessage[];
  showTimestamp?: boolean;
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onDeny?: (messageId: string) => void;
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
}

/**
 * 從所有訊息中找到對應的 tool_result
 */
function findToolResult(
  toolUseId: string,
  allMessages: AgentMessage[]
): ToolResultBlock | undefined {
  for (const msg of allMessages) {
    if (!msg.content_blocks) continue;
    for (const block of msg.content_blocks) {
      if (block.type === 'tool_result' && block.tool_use_id === toolUseId) {
        return block;
      }
    }
  }
  return undefined;
}

/**
 * 檢查 tool_use 是否有對應的 tool_result
 * 用於分頁時判斷是否顯示工具 widget
 */
function hasMatchingToolResult(
  toolUseId: string,
  allMessages: AgentMessage[]
): boolean {
  return findToolResult(toolUseId, allMessages) !== undefined;
}

/**
 * 解析 tool_result 的 content 欄位為字串
 */
function parseToolResultContent(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.map((c: any) => c?.text || c?.content?.text || JSON.stringify(c)).join('\n');
  }
  if (content && typeof content === 'object') {
    const record = content as Record<string, unknown>;
    if (typeof record.error_message === 'string') return record.error_message;
    if (typeof record.message === 'string') return record.message;
    if (typeof record.error === 'string') return record.error;
  }
  return JSON.stringify(content, null, 2);
}

/**
 * 文字區塊渲染 - 使用 MarkdownRenderer 組件（與對話預覽一致）
 */
const TextBlockRenderer: React.FC<{ block: ContentBlock }> = ({ block }) => {
  if (block.type !== 'text') return null;
  const textContent = (block as any).text || '';
  return (
    <div className="text-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <MarkdownRenderer content={textContent} />
    </div>
  );
};

function extractThinkingContent(block: ContentBlock): string {
  if (block.type !== 'thinking') return '';
  const raw = (block as ThinkingBlock).thinking ?? (block as any).text ?? '';
  return typeof raw === 'string' ? raw : '';
}

/**
 * Thinking 區塊渲染 - 使用 MarkdownRenderer 組件（與對話預覽一致）
 */
const ThinkingBlockRenderer: React.FC<{
  block: ContentBlock;
  isMessageActive: boolean;
}> = ({ block, isMessageActive }) => {
  const isThinkingBlock = block.type === 'thinking';
  const content = isThinkingBlock ? extractThinkingContent(block).trim() : '';

  const [isExpanded, setIsExpanded] = React.useState<boolean>(isMessageActive);

  React.useEffect(() => {
    if (!isMessageActive) {
      setIsExpanded(false);
    }
  }, [isMessageActive]);

  if (!isThinkingBlock || !content) return null;

  return (
    <div className="my-2 rounded-md bg-muted/50 p-3 text-sm text-muted-foreground border border-border/50">
      <button
        type="button"
        className="w-full flex items-center justify-between font-semibold text-xs opacity-70 text-left"
        onClick={() => setIsExpanded((prev) => !prev)}
      >
        <span>Thinking Process</span>
        {isExpanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </button>
      {isExpanded && (
        <div className="mt-1 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 text-muted-foreground">
          <MarkdownRenderer content={content} />
        </div>
      )}
    </div>
  );
};

/**
 * 工具呼叫區塊渲染 - 使用 ClaudeToolWidget
 */
const ToolUseBlockRenderer: React.FC<{
  block: ToolUseBlock;
  allMessages: AgentMessage[];
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onDeny?: (messageId: string) => void;
  pendingUserInput?: UserInputRequest | null;
  onAskUserQuestionSubmit?: AskUserQuestionSubmitHandler;
  agentTool?: AgenticTool;
}> = ({ block, allMessages, onApprove, onDeny, pendingUserInput, onAskUserQuestionSubmit, agentTool }) => {
  const toolResult = findToolResult(block.id, allMessages);
  const isAcpTool = agentTool && agentTool !== 'claude-code';

  // 處理 AskUserQuestion 特殊邏輯（需要在狀態判斷之前確定）
  const isAskUserQuestion = block.name === 'AskUserQuestion';

  // 解析 tool_result 內容
  let output: any;
  let error: string | undefined;
  let status: 'pending' | 'in_progress' | 'completed' | 'error';

  if (toolResult) {
    const parsedContent = parseToolResultContent(toolResult.content);

    // AskUserQuestion 特殊處理：
    // 後端使用 PermissionResultDeny 返回用戶答案
    // SDK 會設置 is_error=true，但後端 message_processor.py 已修正為 is_error=false
    // 此處保留作為防禦層，確保前端正確顯示已完成狀態
    if (isAskUserQuestion || !toolResult.is_error) {
      output = isAcpTool ? toolResult.content : parsedContent;
      status = 'completed';
    } else {
      error = isAcpTool ? parseToolResultContent(toolResult.content) : parsedContent;
      status = 'error';
    }
  } else {
    // 工具已呼叫但尚未完成，一律為執行中
    status = 'in_progress';
  }

  const isCollapsible = status !== 'in_progress';

  // 檢查是否有對應的 pendingUserInput
  // 後端發送 tool-decision:request (user_input) 時會包含 tool_use_id
  const hasPendingUserInput = isAskUserQuestion &&
    pendingUserInput?.tool_name === 'AskUserQuestion' &&
    (pendingUserInput?.tool_use_id === block.id || !pendingUserInput?.tool_use_id);

  // AskUserQuestion 特殊處理：
  // 當工具還在等待中（in_progress，沒有 tool_result），也視為 pending 狀態
  // 這確保即使 tool-decision:request 事件延遲，submit 按鈕也能顯示
  const shouldShowAskUserForm = isAskUserQuestion && status === 'in_progress';

  // 如果有 pendingUserInput 或是等待中的 AskUserQuestion，顯示 pending 狀態
  const effectiveStatus = (hasPendingUserInput || shouldShowAskUserForm) ? 'pending' as const : status;

  // AskUserQuestion 提交處理
  const handleAskUserQuestionSubmit = React.useCallback(
    (answers: Record<string, string | string[]>) => {
      if (onAskUserQuestionSubmit && isAskUserQuestion) {
        onAskUserQuestionSubmit(block.id, answers);
      }
    },
    [block.id, isAskUserQuestion, onAskUserQuestionSubmit]
  );

  // 從 output 解析已選擇的答案（用於頁面重整後恢復選擇狀態）
  // SDK 回傳格式: User has answered your questions: "Question"="Answer", "Q2"="A2". You can now continue...
  const parsedAnswers = React.useMemo(() => {
    if (!isAskUserQuestion || typeof output !== 'string' || status !== 'completed') {
      return undefined;
    }

    const questions = (block.input as Record<string, unknown>)?.questions as Array<{ question: string; multiSelect?: boolean }> | undefined;
    if (!questions || questions.length === 0) {
      return undefined;
    }

    const answers: Record<string, string | string[]> = {};
    const regex = /"([^"]+)"="([^"]+)"/g;
    let match;
    while ((match = regex.exec(output)) !== null) {
      const questionText = match[1];
      const answerText = match[2];
      const idx = questions.findIndex(q => q.question === questionText);
      if (idx >= 0) {
        if (questions[idx].multiSelect) {
          answers[`q${idx}`] = answerText.split(', ');
        } else {
          answers[`q${idx}`] = answerText;
        }
      }
    }

    return Object.keys(answers).length > 0 ? answers : undefined;
  }, [isAskUserQuestion, output, status, block.input]);

  if (isAcpTool) {
    const acpInput = block.input as Record<string, unknown>;
    const acpKind = (acpInput?._kind || acpInput?.kind) as string | undefined;
    const acpToolCallId = (acpInput?.toolCallId as string | undefined) || block.id;
    return (
      <AcpToolWidget
        toolName={block.name}
        widgetType={resolveAcpToolWidgetTypeWithKind(block.name, acpKind, acpToolCallId)}
        status={effectiveStatus}
        input={acpInput as Record<string, any>}
        output={output}
        error={error}
        collapsible={isCollapsible}
        defaultExpanded={false}
      />
    );
  }

  return (
    <ClaudeToolWidget
      toolType={block.name as ClaudeToolType}
      toolId={block.id}
      status={effectiveStatus}
      input={block.input as Record<string, any>}
      output={output}
      error={error}
      collapsible={isCollapsible}
      defaultExpanded={isAskUserQuestion}
      onApprove={onApprove}
      onDeny={onDeny}
      // AskUserQuestion 相關 props - 當有 pendingUserInput 或工具等待中時顯示提交按鈕
      onAskUserQuestionSubmit={(hasPendingUserInput || shouldShowAskUserForm) ? handleAskUserQuestionSubmit : undefined}
      isAskUserQuestionSubmitted={isAskUserQuestion && status === 'completed'}
      askUserQuestionAnswers={parsedAnswers}
    />
  );
};

/**
 * 使用者訊息渲染
 */
const UserMessageRenderer: React.FC<{ message: AgentMessage }> = ({ message }) => {
  const textBlocks = message.content_blocks?.filter(b => b.type === 'text') || [];
  const textContent = textBlocks.map(b => (b as any).text).join('\n');

  if (!textContent.trim()) return null;

  return (
    <div className="flex justify-end px-2 py-1">
      <div className="bg-primary/10 border border-primary/20 rounded-lg px-3 py-2 text-sm text-foreground max-w-[85%]">
        {textContent}
      </div>
    </div>
  );
};

/**
 * Permission Request 訊息渲染
 * 用於渲染 type === 'permission_request' 的訊息
 *
 * 參考 agor 的做法：始終顯示 permission request，根據狀態呈現不同的視覺樣式：
 * - pending + 匹配 pendingPermission: 顯示操作按鈕（批准/拒絕）
 * - pending + 不匹配 pendingPermission: 顯示等待狀態（任務已結束或等待前一個請求）
 * - approved: 顯示已批准狀態（綠色樣式，無按鈕）
 * - denied: 顯示已拒絕狀態（紅色樣式，無按鈕）
 * - timeout: 顯示已逾時狀態（灰色樣式，無按鈕）
 */
const PermissionRequestMessageRenderer: React.FC<{
  message: AgentMessage;
  agentTool?: AgenticTool;
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onDeny?: (messageId: string) => void;
  pendingPermission?: PermissionRequest | null;
  pendingUserInput?: UserInputRequest | null;
  onAcpDecision?: (payload: {
    requestId: string;
    decisionType: ToolDecisionType;
    outcome: ToolDecisionOutcome;
    optionId?: string;
    scope?: PermissionScope;
    content?: string;
  }) => void;
}> = ({ message, agentTool = 'claude-code', onApprove, onDeny, pendingPermission, pendingUserInput, onAcpDecision }) => {
  // 從訊息內容中提取權限請求資訊
  // 假設 content_blocks 或 raw_sdk_message 中包含 tool_name 和 tool_input
  const content = (message as any).content || (message.content_blocks?.[0] as any);
  const rawMessage = message.raw_sdk_message as any;

  const toolName = content?.tool_name || rawMessage?.tool_name || 'Unknown Tool';
  const toolInput = content?.tool_input || rawMessage?.tool_input || {};
  const requestId = content?.request_id || message.message_id;
  const status = content?.status || 'pending';
  const decisionType = (content?.decision_type as ToolDecisionType) || 'permission';
  const options = content?.options || pendingPermission?.options || pendingUserInput?.options;
  const toolCall = content?.tool_call || content?.raw_tool_call || pendingPermission?.tool_call || pendingUserInput?.tool_call;
  const approvedAt = content?.approved_at;
  const approvedBy = content?.approved_by;
  const reason = content?.reason;
  const decisionContent = content?.content;

  // 根據狀態決定 widget 的 status 屬性
  const getWidgetStatus = (): 'pending' | 'in_progress' | 'completed' | 'error' => {
    switch (status) {
      case 'approved':
        return 'completed';
      case 'denied':
      case 'timeout':
        return 'error';
      default:
        return 'pending';
    }
  };

  // 判斷是否為當前活躍的權限請求
  // 只有當訊息的 request_id 與 pendingPermission.request_id 匹配時才可互動
  const isPending = status === 'pending';
  const isActivePermission = isPending && pendingPermission?.request_id === requestId;
  const isActiveUserInput = isPending && pendingUserInput?.request_id === requestId;
  const isActive = decisionType === 'user_input' ? isActiveUserInput : isActivePermission;

  // 如果是 pending 狀態但不是活躍的權限請求，則顯示等待狀態
  // 這發生在：1. 任務已結束但權限狀態未更新  2. 等待前一個權限請求
  const isWaiting = isPending && !isActive;

  // user_input 類型（如 AskUserQuestion）不需要在 permission_request 訊息中渲染
  // 因為 tool_use block 已經透過 AskUserQuestionWidget 處理了所有顯示邏輯
  if (decisionType === 'user_input') {
    return null;
  }

  if (agentTool !== 'claude-code') {
    return (
      <div className="px-2 py-1">
        <AcpDecisionWidget
          requestId={requestId}
          status={status}
          decisionType={decisionType}
          toolName={toolName}
          toolInput={toolInput}
          toolCall={toolCall}
          options={options}
          reason={reason}
          content={decisionContent}
          isWaiting={isWaiting}
          onDecision={isActive && onAcpDecision
            ? (payload) =>
                onAcpDecision({
                  requestId,
                  decisionType,
                  outcome: payload.outcome,
                  optionId: payload.optionId,
                  scope: payload.scope,
                  content: payload.content,
                })
            : undefined}
        />
      </div>
    );
  }

  return (
    <div className="px-2 py-1">
      <ClaudeToolWidget
        toolType="PermissionRequest"
        toolId={requestId}
        status={getWidgetStatus()}
        agentTool={agentTool}
        isWaiting={isWaiting}
        input={{
          tool_name: toolName,
          tool_input: toolInput,
          permission_status: status,
          message_id: requestId,
          approved_at: approvedAt,
          approved_by: approvedBy,
        }}
        requested_at={message.created_at}
        onApprove={isActivePermission ? onApprove : undefined}
        onDeny={isActivePermission ? onDeny : undefined}
        collapsible={false}
        defaultExpanded={true}
      />
    </div>
  );
};

/**
 * 助手訊息渲染
 */
const AssistantMessageRenderer: React.FC<{
  message: AgentMessage;
  allMessages: AgentMessage[];
  agentTool?: AgenticTool;
  onApprove?: (messageId: string, scope: PermissionScope) => void;
  onDeny?: (messageId: string) => void;
  pendingUserInput?: UserInputRequest | null;
  onAskUserQuestionSubmit?: AskUserQuestionSubmitHandler;
  activeTaskId?: string | null;
}> = ({ message, allMessages, agentTool, onApprove, onDeny, pendingUserInput, onAskUserQuestionSubmit, activeTaskId }) => {
  const blocks = message.content_blocks || [];
  const isMessageActive =
    message.session_id === 'temp' ||
    (!!activeTaskId && !!message.task_id && message.task_id === activeTaskId);

  // 過濾邏輯：
  // 1. tool_result 永遠不獨立顯示（它們會在對應的 tool_use widget 中顯示）
  // 2. tool_use 顯示規則：
  //    - 如果有對應的 tool_result，顯示（歷史訊息，已完成）
  //    - 如果屬於當前活躍任務，顯示（即時訊息，執行中）
  //    - 否則不顯示（歷史訊息，未完成的工具調用）
  const renderableBlocks = blocks.filter(b => {
    if (b.type === 'tool_result') return false;
    // 允許 system 類型通過（用於 SystemInit）
    if (b.type === 'system') return true;
    // thinking 需有實際內容才渲染，避免顯示空的「Thinking Process」
    if (b.type === 'thinking') {
      return extractThinkingContent(b).trim().length > 0;
    }
    if (b.type === 'tool_use') {
      const toolUseBlock = b as ToolUseBlock;
      // 有對應的 tool_result，顯示
      if (hasMatchingToolResult(toolUseBlock.id, allMessages)) {
        return true;
      }
      // 屬於當前活躍任務，顯示（即時的，執行中）
      // 這裡需要確保 activeTaskId 和 message.task_id 都不是 null 才比較
      if (activeTaskId && message.task_id === activeTaskId) {
        return true;
      }
      // 歷史訊息，沒有 result，不顯示
      return false;
    }
    return true;
  });

  if (renderableBlocks.length === 0) return null;

  return (
    <div className="px-2 py-1 space-y-2">
      {renderableBlocks.map((block, idx) => {
        if (block.type === 'text') {
          return <TextBlockRenderer key={idx} block={block} />;
        }
        if (block.type === 'thinking') {
          return <ThinkingBlockRenderer key={idx} block={block} isMessageActive={isMessageActive} />;
        }
        if (block.type === 'tool_use') {
          return (
            <ToolUseBlockRenderer
              key={idx}
              block={block as ToolUseBlock}
              allMessages={allMessages}
              onApprove={onApprove}
              onDeny={onDeny}
              pendingUserInput={pendingUserInput}
              onAskUserQuestionSubmit={onAskUserQuestionSubmit}
              agentTool={agentTool}
            />
          );
        }
        // 處理 system block（用於 SystemInit 等系統訊息）
        if (block.type === 'system') {
          const systemBlock = block as SystemBlock;
          if (systemBlock.subtype === 'init') {
            return (
              <ClaudeToolWidget
                key={idx}
                toolType="SystemInit"
                toolId={`system-init-${idx}`}
                status="completed"
                input={{
                  sessionId: systemBlock.data?.session_id,
                  model: systemBlock.data?.model,
                  cwd: systemBlock.data?.cwd,
                  tools: systemBlock.data?.tools,
                  slash_commands: systemBlock.data?.slash_commands,
                  output_style: systemBlock.data?.output_style,
                  agents: systemBlock.data?.agents,
                  skills: systemBlock.data?.skills,
                  plugins: systemBlock.data?.plugins,
                }}
                collapsible={true}
                defaultExpanded={false}
              />
            );
          }
          return null;
        }

        // 處理 system_complete block（任務完成/失敗）
        if (block.type === 'system_complete') {
          const completeBlock = block as SystemCompleteBlock;
          const { stop_reason, result, message } = completeBlock;

          // 檢查是否為錯誤終止或包含錯誤訊息
          // 即使 stop_reason 是 'end_turn' 或 'max_tokens'，如果 result/message 包含錯誤關鍵字，也要顯示錯誤
          const errorKeywords = ['timeout', 'error', 'failed', 'crashed', 'hung', 'exception'];
          const resultStr = (result || '').toLowerCase();
          const messageStr = (message || '').toLowerCase();
          const hasErrorKeyword = errorKeywords.some(kw =>
            resultStr.includes(kw) || messageStr.includes(kw)
          );

          const isError = stop_reason && stop_reason !== 'end_turn' && stop_reason !== 'max_tokens';
          const hasErrorMessage = hasErrorKeyword && (result || message);

          if (isError || hasErrorMessage) {
            return (
              <ClaudeToolWidget
                key={idx}
                toolType="SystemError"
                toolId={`system-error-${idx}`}
                status="error"
                input={{
                  error: message || result || `任務因以下原因終止：${stop_reason}`,
                  code: stop_reason || 'task_error',
                }}
                collapsible={true}
                defaultExpanded={true}
              />
            );
          }
          return null;
        }

        // 處理 system_status block（系統狀態更新）
        if (block.type === 'system_status') {
          const statusBlock = block as SystemStatusBlock;
          const { status, message: statusMessage } = statusBlock;

          // 如果狀態為 error，顯示錯誤 Widget
          if (status === 'error') {
            return (
              <ClaudeToolWidget
                key={idx}
                toolType="SystemError"
                toolId={`system-error-${idx}`}
                status="error"
                input={{
                  error: statusMessage || '發生錯誤',
                  code: 'system_error',
                }}
                collapsible={true}
                defaultExpanded={true}
              />
            );
          }
          return null;
        }
        // 其他類型暫時忽略
        return null;
      })}
    </div>
  );
};

/**
 * 主渲染器
 */
export const AgentContentBlockRenderer: React.FC<AgentContentBlockRendererProps> = ({
  message,
  allMessages,
  onApprove,
  onDeny,
  agentTool,
  pendingPermission,
  pendingUserInput,
  onAcpDecision,
  onAskUserQuestionSubmit,
  activeTaskId,
}) => {
  const isUser = message.role === 'user';
  const isPermissionRequest = message.type === 'permission_request';

  if (isUser) {
    return <UserMessageRenderer message={message} />;
  }

  // 處理 permission_request 類型的訊息
  if (isPermissionRequest) {
    return (
      <PermissionRequestMessageRenderer
        message={message}
        agentTool={agentTool}
        onApprove={onApprove}
        onDeny={onDeny}
        pendingPermission={pendingPermission}
        pendingUserInput={pendingUserInput}
        onAcpDecision={onAcpDecision}
      />
    );
  }

  return (
    <AssistantMessageRenderer
      message={message}
      allMessages={allMessages}
      agentTool={agentTool}
      onApprove={onApprove}
      onDeny={onDeny}
      pendingUserInput={pendingUserInput}
      onAskUserQuestionSubmit={onAskUserQuestionSubmit}
      activeTaskId={activeTaskId}
    />
  );
};

export default AgentContentBlockRenderer;
