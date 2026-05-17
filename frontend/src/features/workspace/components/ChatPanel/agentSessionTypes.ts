/**
 * Agent Session 類型定義
 *
 * 支援多種 Agentic CLI 工具的對話系統類型
 */

// ============================================================================
// Enums
// ============================================================================

/** Agentic Tool 類型 */
export type AgenticTool = 'claude-code' | 'codex' | 'gemini' | 'opencode';

export const AGENTIC_TOOLS = ['claude-code', 'codex', 'gemini', 'opencode'] as const;

const normalizeCliTypeKey = (value: string): string =>
  value.trim().toLowerCase().replace(/[\s-]+/g, '');

/**
 * 將 workspace cliType（如 ClaudeCode / Gemini）轉為 agent_session 使用的 agentic_tool。
 */
export const resolveAgenticToolFromCliType = (cliType?: string | null): AgenticTool => {
  if (!cliType) return 'claude-code';
  const normalized = normalizeCliTypeKey(cliType);

  switch (normalized) {
    case 'claude':
    case 'claudecode':
      return 'claude-code';
    case 'codex':
      return 'codex';
    case 'gemini':
      return 'gemini';
    case 'opencode':
      return 'opencode';
    default:
      return 'claude-code';
  }
};

export const isAgenticTool = (value: unknown): value is AgenticTool =>
  typeof value === 'string' && AGENTIC_TOOLS.includes(value as AgenticTool);

/** Session 狀態 */
export type SessionStatus = 'idle' | 'running' | 'error';

/** Task 狀態 */
export type TaskStatus =
  | 'created'
  | 'running'
  | 'stopping'
  | 'awaiting_permission'
  | 'completed'
  | 'failed'
  | 'stopped';

/** Message 類型 */
export type MessageType =
  | 'user'
  | 'assistant'
  | 'system'
  | 'file-history-snapshot'
  | 'permission_request';

/** Message 角色 */
export type MessageRole = 'user' | 'assistant' | 'system';

/** Content Block 類型 */
export type ContentBlockType =
  | 'text'
  | 'image'
  | 'tool_use'
  | 'tool_result'
  | 'thinking'
  | 'system_status'
  | 'system_complete'
  | 'system';

/** Permission 狀態 */
export type PermissionStatus = 'pending' | 'approved' | 'denied' | 'timeout';

/** Permission Scope */
export type PermissionScope = 'once' | 'session' | 'project' | 'user' | 'local';

/**
 * Permission Mode - Claude SDK 原生權限模式
 *
 * - default: 每個工具都提示（最嚴格）
 * - acceptEdits: 自動接受檔案編輯，其他工具提示
 * - bypassPermissions: 允許所有操作（不提示）
 * - plan: 計劃模式（生成計劃但不執行）
 * - dontAsk: 允許所有操作（不提示、不詢問）
 * - auto: 自動決定權限模式
 */
export type PermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan' | 'dontAsk' | 'auto';

export const PERMISSION_MODES = [
  'default',
  'acceptEdits',
  'bypassPermissions',
  'plan',
  'dontAsk',
  'auto',
] as const;

export const isPermissionMode = (value: unknown): value is PermissionMode =>
  typeof value === 'string' && PERMISSION_MODES.includes(value as PermissionMode);

/** Permission Config for session creation */
export type CodexSandboxMode = 'strict' | 'relaxed' | 'off';
export type CodexApprovalPolicy = 'manual' | 'suggest' | 'auto';
export type GeminiSessionPermissionMode = 'default' | 'autoEdit' | 'yolo' | 'plan';

export const GEMINI_SESSION_PERMISSION_MODES = ['default', 'autoEdit', 'yolo', 'plan'] as const;
export const DEFAULT_GEMINI_SESSION_PERMISSION_MODE: GeminiSessionPermissionMode = 'yolo';

export const isGeminiSessionPermissionMode = (
  value: unknown,
): value is GeminiSessionPermissionMode =>
  typeof value === 'string'
  && GEMINI_SESSION_PERMISSION_MODES.includes(value as GeminiSessionPermissionMode);

export interface CodexPermissionConfig {
  sandboxMode: CodexSandboxMode;
  approvalPolicy: CodexApprovalPolicy;
}

export interface PermissionConfig {
  mode: PermissionMode;
  codex?: CodexPermissionConfig;
  gemini?: GeminiSessionPermissionMode;
  geminiSpawnedWith?: GeminiSessionPermissionMode;
}

// ============================================================================
// Content Blocks
// ============================================================================

export interface TextBlock {
  type: 'text';
  text: string;
}

export interface ImageBlock {
  type: 'image';
  source: {
    type: 'base64' | 'url';
    media_type?: string;
    data?: string;
    url?: string;
    path?: string;
  };
}

export interface ToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: unknown;
  is_error?: boolean;
}

export interface ThinkingBlock {
  type: 'thinking';
  // 標準欄位
  thinking?: string;
  // 相容舊格式（部分 ACP/Gemini 回傳）
  text?: string;
}

export interface SystemStatusBlock {
  type: 'system_status';
  status: string;
  message?: string;
}

export interface SystemCompleteBlock {
  type: 'system_complete';
  stop_reason: string;
  result?: string;
  message?: string;
  metadata?: Record<string, unknown>;
}

export interface SystemBlock {
  type: 'system';
  subtype: string;
  data?: Record<string, unknown>;
}

export type ContentBlock =
  | TextBlock
  | ImageBlock
  | ToolUseBlock
  | ToolResultBlock
  | ThinkingBlock
  | SystemStatusBlock
  | SystemCompleteBlock
  | SystemBlock;

// ============================================================================
// Token Usage
// ============================================================================

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
  total_tokens?: number;
}

export interface ContextWindowStatus {
  used: number;
  limit: number;
  percentage: number;
  needs_compaction: boolean;
}

// ============================================================================
// Tool Capabilities
// ============================================================================

export interface ToolCapabilities {
  name: string;
  streaming: boolean;
  thinking: boolean;
  multimodal: boolean;
  max_context_window: number;
  prompt_caching: boolean;
  local_execution: boolean;
  built_in_tools: string[];
}

// ============================================================================
// Session
// ============================================================================

export interface AgentSession {
  session_id: string;
  created_at: string;
  updated_at?: string | null;
  created_by: string;
  status: SessionStatus;
  agentic_tool: AgenticTool;
  workspace_id: string;
  source?: string;
  ready_for_prompt: boolean;
  archived: boolean;
  archived_reason?: string | null;
  git_context_id?: string | null;
  workspace_path?: string | null;
  // Data blob fields
  model?: string | null;
  context_window_limit?: number | null;
  context_window_used?: number | null;
  message_count?: number;
  title?: string | null;
  permission_config?: PermissionConfig | null;
}

export interface SessionCreateRequest {
  workspace_id: string;
  agentic_tool?: AgenticTool;
  model?: string | null;
  created_by?: string;
  permission_config?: PermissionConfig | null;
  git_context_id?: string | null;
}

export interface SessionUpdateRequest {
  status?: SessionStatus;
  model?: string | null;
  title?: string | null;
  permission_config?: PermissionConfig | null;
}

export interface SessionListResponse {
  items: AgentSession[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// Task
// ============================================================================

export interface AgentTask {
  task_id: string;
  session_id: string;
  created_at: string;
  updated_at?: string | null;
  created_by: string;
  status: TaskStatus;
  message_start_index?: number | null;
  message_end_index?: number | null;
  // Data blob fields
  full_prompt?: string | null;
  model?: string | null;
  tool_use_count?: number;
  error_message?: string | null;
  stopped_reason?: string | null;
  raw_sdk_response?: Record<string, unknown> | null;
  duration_ms?: number | null;
  token_usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cache_creation_tokens?: number | null;
    cache_read_tokens?: number | null;
    cost_usd?: number | null;
    service_tier?: string | null;
  } | null;
}

export interface TaskCreateRequest {
  session_id: string;
  full_prompt?: string;
  created_by?: string;
}

export interface TaskListResponse {
  items: AgentTask[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// Queued Message
// ============================================================================

export interface QueuedMessage {
  message_id: string;
  content_preview?: string;
  queue_position?: number;
  created_at?: string | null;
  status?: 'queued' | 'dispatching' | null;
}

// ============================================================================
// Message
// ============================================================================

export interface AgentMessage {
  message_id: string;
  session_id: string;
  task_id?: string | null;
  created_at: string;
  index: number;
  type: MessageType;
  role: MessageRole;
  // Data blob fields
  content_blocks?: ContentBlock[];
  raw_sdk_message?: Record<string, unknown> | null;
  metadata?: {
    model?: string | null;
    source?: string | null;
    tokens?: {
      input?: number | null;
      output?: number | null;
      cache_read?: number | null;
      cache_creation?: number | null;
    } | null;
  } | null;
  queued?: boolean;
  in_context?: boolean;
}

export interface MessageCreateRequest {
  session_id: string;
  type: MessageType;
  role: MessageRole;
  content_blocks?: ContentBlock[];
  task_id?: string | null;
  queued?: boolean;
}

export interface MessageListResponse {
  items: AgentMessage[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================================
// Permission Request
// ============================================================================

export interface PermissionRequest {
  request_id: string;
  task_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  timeout?: number;
  tool_use_id?: string;
  options?: ToolDecisionOption[];
  tool_call?: ToolDecisionToolCall;
}

export type ToolDecisionType = 'permission' | 'user_input';
export type ToolDecisionOutcome = 'selected' | 'cancelled';

export interface ToolDecisionOption {
  option_id?: string;
  optionId?: string;
  name: string;
  kind: 'allow_once' | 'allow_always' | 'reject_once' | 'reject_always';
  scope?: PermissionScope;
}

export interface ToolDecisionToolCall {
  toolCallId?: string;
  title?: string;
  kind?: string;
  status?: string;
  sessionUpdate?: string;
  locations?: Array<Record<string, unknown>>;
  content?: Array<Record<string, unknown>>;
  rawInput?: Record<string, unknown>;
  raw_input?: Record<string, unknown>;
  input?: Record<string, unknown>;
  params?: Record<string, unknown>;
  arguments?: Record<string, unknown>;
}

export interface ToolDecisionRequest {
  request_id: string;
  task_id: string;
  decision_type: ToolDecisionType;
  outcome: ToolDecisionOutcome;
  option_id?: string;
  scope?: PermissionScope;
  decided_by: string;
  reason?: string;
  content?: string;
}

export type AcpToolWidgetType = 'read' | 'write' | 'terminal' | 'generic';

export const ACP_TOOL_WIDGET_MAP: Record<string, AcpToolWidgetType> = {
  read_text_file: 'read',
  read_file: 'read',
  read: 'read',
  write_text_file: 'write',
  write_file: 'write',
  edit_text_file: 'write',
  write: 'write',
  edit: 'write',
  create_terminal: 'terminal',
  terminal: 'terminal',
  terminal_output: 'terminal',
  bash: 'terminal',
  shell: 'terminal',
};

export const ACP_TOOL_WIDGET_FALLBACK: AcpToolWidgetType = 'generic';

export const resolveAcpToolWidgetType = (toolName?: string): AcpToolWidgetType => {
  if (!toolName) return ACP_TOOL_WIDGET_FALLBACK;
  const normalized = toolName.toLowerCase();
  const direct = ACP_TOOL_WIDGET_MAP[normalized];
  if (direct) return direct;
  if (normalized.includes('read')) return 'read';
  if (normalized.includes('write') || normalized.includes('edit')) return 'write';
  if (normalized.includes('terminal') || normalized.includes('bash') || normalized.includes('shell')) return 'terminal';
  return ACP_TOOL_WIDGET_FALLBACK;
};

const ACP_KIND_WIDGET_MAP: Record<string, AcpToolWidgetType> = {
  read: 'read',
  search: 'read',
  edit: 'write',
  delete: 'write',
  move: 'write',
  execute: 'terminal',
  think: 'generic',
  fetch: 'generic',
  switch_mode: 'generic',
  other: 'generic',
};

const ACP_TOOL_CALL_PREFIX_WIDGET_MAP: Array<[string, AcpToolWidgetType]> = [
  ['read_file', 'read'],
  ['read_text_file', 'read'],
  ['write_file', 'write'],
  ['write_text_file', 'write'],
  ['edit_text_file', 'write'],
  ['run_shell_command', 'terminal'],
  ['create_terminal', 'terminal'],
  ['terminal_output', 'terminal'],
];

export const resolveAcpToolWidgetTypeWithKind = (
  toolName?: string,
  kind?: string | null,
  toolCallId?: string | null,
): AcpToolWidgetType => {
  if (kind) {
    const fromKind = ACP_KIND_WIDGET_MAP[kind];
    if (fromKind) return fromKind;
  }
  if (toolCallId) {
    const normalizedCallId = toolCallId.toLowerCase();
    for (const [prefix, widgetType] of ACP_TOOL_CALL_PREFIX_WIDGET_MAP) {
      if (normalizedCallId.startsWith(prefix)) {
        return widgetType;
      }
    }
  }
  return resolveAcpToolWidgetType(toolName);
};

const isNonEmptyRecord = (value: unknown): value is Record<string, unknown> =>
  !!value &&
  typeof value === 'object' &&
  !Array.isArray(value) &&
  Object.keys(value as Record<string, unknown>).length > 0;

const normalizeRecord = (value: unknown): Record<string, unknown> => {
  if (isNonEmptyRecord(value)) return value;
  return {};
};

export const extractToolDecisionInput = (
  toolCall?: ToolDecisionToolCall | Record<string, unknown> | null,
  fallbackInput?: Record<string, unknown> | null,
): Record<string, unknown> => {
  const call = (toolCall ?? {}) as ToolDecisionToolCall & Record<string, unknown>;
  const candidates: unknown[] = [
    call.input,
    call.params,
    call.arguments,
    call.rawInput,
    call.raw_input,
    fallbackInput,
  ];

  for (const candidate of candidates) {
    if (isNonEmptyRecord(candidate)) return candidate;
  }

  const acpProjection: Record<string, unknown> = {};
  if (typeof call.toolCallId === 'string' && call.toolCallId.trim()) acpProjection.toolCallId = call.toolCallId;
  if (typeof call.title === 'string' && call.title.trim()) acpProjection.title = call.title;
  if (typeof call.kind === 'string' && call.kind.trim()) acpProjection.kind = call.kind;
  if (typeof call.status === 'string' && call.status.trim()) acpProjection.status = call.status;
  if (typeof call.sessionUpdate === 'string' && call.sessionUpdate.trim()) acpProjection.sessionUpdate = call.sessionUpdate;
  if (Array.isArray(call.locations) && call.locations.length > 0) acpProjection.locations = call.locations;
  if (Array.isArray(call.content) && call.content.length > 0) acpProjection.content = call.content;

  if (isNonEmptyRecord(acpProjection)) {
    return acpProjection;
  }

  return normalizeRecord(fallbackInput);
};

// ============================================================================
// User Input Request (用於 AskUserQuestion 等工具)
// ============================================================================

export interface UserInputRequest {
  request_id: string;
  task_id: string;
  tool_name: string;
  tool_use_id?: string;
  tool_input: Record<string, unknown>;
  timeout?: number;
  options?: ToolDecisionOption[];
  tool_call?: ToolDecisionToolCall;
}

// ============================================================================
// Prompt Execution
// ============================================================================

export interface PromptRequest {
  prompt: string;
  model?: string | null;
  system_prompt?: string | null;
  images?: string[];
  context_files?: string[];
  stream?: boolean;
  thinking_mode?: 'off' | 'brief' | 'extended';
  thinking_budget?: number;
  permission_mode?: PermissionMode;
}

export interface PromptResponse {
  success: boolean;
  task_id: string | null;
  status: string;
  streaming: boolean;
  queued?: boolean;
  message_id?: string;
  queue_position?: number;
}

// ============================================================================
// WebSocket Events
// ============================================================================

export type WebSocketEventType =
  // Error events
  | 'error'
  // CRUD events
  | 'sessions created'
  | 'session:init'
  | 'sessions patched'
  | 'sessions updated'
  | 'sessions removed'
  | 'tasks created'
  | 'tasks patched'
  | 'tasks updated'
  | 'tasks removed'
  | 'messages created'
  | 'messages patched'
  | 'messages updated'
  | 'messages removed'
  | 'messages queued'
  | 'message:dequeued'
  | 'queue:processing_failed'
  // Streaming events
  | 'streaming:start'
  | 'streaming:chunk'
  | 'streaming:end'
  | 'streaming:error'
  // Thinking events
  | 'thinking:start'
  | 'thinking:chunk'
  | 'thinking:end'
  // Task lifecycle events
  | 'task:started'
  | 'task:completed'
  | 'task:failed'
  | 'task:stop_ack'
  | 'task:stopping'
  | 'task:stopped'
  // Tool Decision events
  | 'tool-decision:request'
  | 'tool-decision:approved'
  | 'tool-decision:denied'
  | 'tool-decision:timeout'
  // Tool events
  | 'tool:start'
  | 'tool:complete'
  | 'tool:error';

export interface WebSocketEvent {
  type: WebSocketEventType;
  data: Record<string, unknown>;
  session_id?: string;
  task_id?: string;
  seq?: number;
  timestamp: string;
}

export interface StreamingChunkEvent {
  type: 'streaming:chunk';
  data: {
    message_id?: string;
    content: string;
    is_partial: boolean;
  };
  session_id: string;
  task_id: string;
  seq?: number;
  timestamp: string;
}

export interface ThinkingChunkEvent {
  type: 'thinking:chunk';
  data: {
    message_id?: string;
    content: string;
    is_partial: boolean;
  };
  session_id: string;
  task_id: string;
  seq?: number;
  timestamp: string;
}

export interface ToolDecisionRequestPayload {
  request_id: string;
  decision_type: ToolDecisionType;
  options?: ToolDecisionOption[];
  tool_call?: ToolDecisionToolCall;
  timeout?: number;
}

export interface ToolDecisionRequestEvent {
  type: 'tool-decision:request';
  data: ToolDecisionRequestPayload;
  session_id: string;
  task_id: string;
  seq?: number;
  timestamp: string;
}
