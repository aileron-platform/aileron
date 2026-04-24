/**
 * Agent Session WebSocket 事件處理器
 *
 * 處理來自 WebSocket 的各種事件，更新本地狀態
 */

import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AgentSessionEventDispatcher');

import type {
  WebSocketEvent,
  WebSocketEventType,
  AgentSession,
  AgentTask,
  AgentMessage,
  QueuedMessage,
  StreamingChunkEvent,
  ThinkingChunkEvent,
  ToolDecisionRequestEvent,
} from './agentSessionTypes';

// ============================================================================
// Event Handlers 類型
// ============================================================================

export interface EventHandlers {
  // Session 事件
  onSessionCreated?: (session: AgentSession) => void;
  onSessionPatched?: (session: Partial<AgentSession> & { session_id: string }) => void;
  onSessionRemoved?: (sessionId: string) => void;

  // Task 事件
  onTaskCreated?: (task: AgentTask) => void;
  onTaskPatched?: (task: Partial<AgentTask> & { task_id: string }) => void;
  onTaskRemoved?: (taskId: string) => void;
  onTaskStarted?: (sessionId: string, taskId: string) => void;
  onTaskCompleted?: (sessionId: string, taskId: string) => void;
  onTaskFailed?: (sessionId: string, taskId: string, error?: string) => void;
  onTaskStopAck?: (sessionId: string, taskId: string) => void;
  onTaskStopped?: (sessionId: string, taskId: string) => void;

  // Message 事件
  onMessageCreated?: (message: AgentMessage) => void;
  onMessagePatched?: (message: Partial<AgentMessage> & { message_id: string }) => void;
  onMessageRemoved?: (messageId: string) => void;
  onMessageQueued?: (sessionId: string, message: QueuedMessage) => void;
  onMessageDequeued?: (sessionId: string, messageId: string, queuePosition: number, reason: string) => void;

  // Streaming 事件
  onStreamingStart?: (sessionId: string, taskId: string, messageId?: string) => void;
  onStreamingChunk?: (sessionId: string, taskId: string, content: string, isPartial: boolean, messageId?: string) => void;
  onStreamingEnd?: (sessionId: string, taskId: string, data?: Record<string, unknown>, messageId?: string) => void;
  onStreamingError?: (sessionId: string, taskId: string, error: string, code?: string, messageId?: string) => void;

  // Thinking 事件
  onThinkingStart?: (sessionId: string, taskId: string, messageId?: string) => void;
  onThinkingChunk?: (sessionId: string, taskId: string, content: string, isPartial: boolean, messageId?: string) => void;
  onThinkingEnd?: (sessionId: string, taskId: string, messageId?: string) => void;

  // Tool Decision 事件
  onToolDecisionRequest?: (
    sessionId: string,
    taskId: string,
    request: ToolDecisionRequestEvent['data']
  ) => void;
  onToolDecisionResolved?: (
    sessionId: string,
    taskId: string,
    status: 'approved' | 'denied' | 'timeout',
    payload: Record<string, unknown>
  ) => void;

  // Tool 事件
  onToolStart?: (
    sessionId: string,
    taskId: string,
    toolUseId: string,
    toolName: string,
    toolInput: Record<string, unknown>
  ) => void;
  onToolComplete?: (
    sessionId: string,
    taskId: string,
    toolUseId: string,
    toolName: string,
    result: unknown,
    isError: boolean
  ) => void;
}

// ============================================================================
// Event Dispatcher
// ============================================================================

/**
 * 事件分發器
 *
 * 將 WebSocket 事件分發到對應的處理器
 */
export class AgentSessionEventDispatcher {
  private legacyHandlers: EventHandlers = {};
  private subscribers: Set<Partial<EventHandlers>> = new Set();

  /**
   * 設定事件處理器 (Legacy, overwrites all)
   */
  setHandlers(handlers: EventHandlers): void {
    this.legacyHandlers = handlers;
  }

  /**
   * 更新部分處理器 (Legacy, merges)
   */
  updateHandlers(handlers: Partial<EventHandlers>): void {
    this.legacyHandlers = { ...this.legacyHandlers, ...handlers };
  }

  /**
   * 清除所有處理器 (Legacy)
   */
  clearHandlers(): void {
    this.legacyHandlers = {};
  }

  /**
   * 訂閱事件 (New, supports multiple listeners)
   */
  subscribe(handlers: Partial<EventHandlers>): () => void {
    this.subscribers.add(handlers);
    return () => {
      this.subscribers.delete(handlers);
    };
  }

  private emit<K extends keyof EventHandlers>(
    handlerName: K,
    ...args: Parameters<NonNullable<EventHandlers[K]>>
  ): void {
    // Legacy support
    const legacyHandler = this.legacyHandlers[handlerName] as
      | ((...handlerArgs: Parameters<NonNullable<EventHandlers[K]>>) => void)
      | undefined;
    legacyHandler?.(...args);

    // Subscribers support
    this.subscribers.forEach(sub => {
      const handler = sub[handlerName] as
        | ((...handlerArgs: Parameters<NonNullable<EventHandlers[K]>>) => void)
        | undefined;
      handler?.(...args);
    });
  }

  /**
   * 分發事件
   */
  dispatch(event: WebSocketEvent): void {
    const { type, data, session_id, task_id } = event;
    const normalizeSession = (
      payload: Partial<AgentSession> & { session_id?: string }
    ): (Partial<AgentSession> & { session_id: string }) | null => {
      const resolvedSessionId = payload.session_id ?? session_id;
      if (!resolvedSessionId) {
        logger.warn('Session event missing session_id', { type, payload });
        return null;
      }
      return {
        ...payload,
        session_id: resolvedSessionId,
      };
    };

    switch (type) {
      // Session 事件
      case 'sessions created':
        {
          const normalized = normalizeSession(data as Partial<AgentSession> & { session_id?: string });
          if (normalized) {
            this.emit('onSessionCreated', normalized as AgentSession);
          }
        }
        break;
      case 'session:init':
        // 初始化事件 - 更新現有 session 狀態，不觸發 onSessionCreated（避免無限迴圈）
        {
          const normalized = normalizeSession(data as Partial<AgentSession> & { session_id?: string });
          if (normalized) {
            this.emit('onSessionPatched', normalized);
          }
        }
        break;
      case 'sessions patched':
      case 'sessions updated':
        {
          const normalized = normalizeSession(data as Partial<AgentSession> & { session_id?: string });
          if (normalized) {
            this.emit('onSessionPatched', normalized);
          }
        }
        break;
      case 'sessions removed':
        this.emit('onSessionRemoved', (data as { session_id: string }).session_id);
        break;

      // Task 事件
      case 'tasks created':
        this.emit('onTaskCreated', data as unknown as AgentTask);
        break;
      case 'tasks patched':
      case 'tasks updated':
        this.emit('onTaskPatched', data as unknown as Partial<AgentTask> & { task_id: string });
        break;
      case 'tasks removed':
        this.emit('onTaskRemoved', (data as { task_id: string }).task_id);
        break;

      // Task 生命週期事件
      case 'task:started':
        // Task started event - 可以用來更新 UI 狀態
        logger.debug('Task started', { session_id, task_id, data });
        this.emit('onTaskPatched', data as unknown as Partial<AgentTask> & { task_id: string });
        if (session_id && task_id) {
          this.emit('onTaskStarted', session_id, task_id);
        }
        break;
      case 'task:completed':
        logger.debug('Task completed', { session_id, task_id, data });
        this.emit('onTaskPatched', data as unknown as Partial<AgentTask> & { task_id: string });
        if (session_id && task_id) {
          this.emit('onTaskCompleted', session_id, task_id);
        }
        break;
      case 'task:failed':
        logger.debug('Task failed', { session_id, task_id, data });
        this.emit('onTaskPatched', data as unknown as Partial<AgentTask> & { task_id: string });
        if (session_id && task_id) {
          const errorMsg = (data as { error_message?: string }).error_message;
          this.emit('onTaskFailed', session_id, task_id, errorMsg);
        }
        break;
      case 'task:stop_ack':
        // Task stop acknowledged - 後端已收到停止請求，前端應立即停止處理新訊息
        logger.debug('Task stop acknowledged', { session_id, task_id, data });
        if (session_id && task_id) {
          this.emit('onTaskStopAck', session_id, task_id);
        }
        break;
      case 'task:stopping':
        logger.debug('Task stopping', { session_id, task_id, data });
        if (task_id) {
          this.emit('onTaskPatched', { task_id, status: 'stopping' } as Partial<AgentTask> & { task_id: string });
        }
        break;
      case 'task:stopped':
        // Task fully stopped - 任務已完全停止
        logger.debug('Task stopped', { session_id, task_id, data });
        this.emit('onTaskPatched', data as unknown as Partial<AgentTask> & { task_id: string });
        if (session_id && task_id) {
          this.emit('onTaskStopped', session_id, task_id);
        }
        break;

      // Message 事件
      case 'messages created':
        logger.debug('Message created', { data });
        this.emit('onMessageCreated', data as unknown as AgentMessage);
        break;
      case 'messages patched':
      case 'messages updated':
        this.emit('onMessagePatched', data as unknown as Partial<AgentMessage> & { message_id: string });
        break;
      case 'messages removed':
        this.emit('onMessageRemoved', (data as { message_id: string }).message_id);
        break;
      case 'messages queued':
        {
          const queuedSessionId = session_id ?? (data as { session_id?: string }).session_id;
          if (queuedSessionId) {
            this.emit('onMessageQueued', queuedSessionId, data as QueuedMessage);
          }
        }
        break;
      case 'message:dequeued':
        {
          const dequeuedData = data as { session_id?: string; message_id: string; queue_position: number; reason: string };
          const dequeuedSessionId = session_id ?? dequeuedData.session_id;
          if (dequeuedSessionId) {
            this.emit('onMessageDequeued',
              dequeuedSessionId,
              dequeuedData.message_id,
              dequeuedData.queue_position,
              dequeuedData.reason
            );
          }
        }
        break;

      // Streaming 事件
      case 'streaming:start':
        if (session_id && task_id) {
          const msgId = (data as { message_id?: string }).message_id;
          this.emit('onStreamingStart', session_id, task_id, msgId);
        }
        break;
      case 'streaming:chunk':
        if (session_id && task_id) {
          const chunkEvent = event as StreamingChunkEvent;
          this.emit('onStreamingChunk',
            session_id,
            task_id,
            chunkEvent.data.content,
            chunkEvent.data.is_partial,
            chunkEvent.data.message_id
          );
        }
        break;
      case 'streaming:end':
        if (session_id && task_id) {
          const msgId = (data as { message_id?: string }).message_id;
          this.emit('onStreamingEnd', session_id, task_id, data, msgId);
        }
        break;
      case 'streaming:error':
        if (session_id && task_id) {
          const msgId = (data as { message_id?: string }).message_id;
          this.emit('onStreamingError',
            session_id,
            task_id,
            (data as { error: string }).error,
            (data as { code?: string }).code,
            msgId
          );
        }
        break;

      // Thinking 事件
      case 'thinking:start':
        if (session_id && task_id) {
          const msgId = (data as { message_id?: string }).message_id;
          this.emit('onThinkingStart', session_id, task_id, msgId);
        }
        break;
      case 'thinking:chunk':
        if (session_id && task_id) {
          const thinkingEvent = event as ThinkingChunkEvent;
          this.emit('onThinkingChunk',
            session_id,
            task_id,
            thinkingEvent.data.content,
            thinkingEvent.data.is_partial,
            thinkingEvent.data.message_id
          );
        }
        break;
      case 'thinking:end':
        if (session_id && task_id) {
          const msgId = (data as { message_id?: string }).message_id;
          this.emit('onThinkingEnd', session_id, task_id, msgId);
        }
        break;

      // Tool Decision 事件
      case 'tool-decision:request':
        if (session_id && task_id) {
          const decisionEvent = event as ToolDecisionRequestEvent;
          this.emit('onToolDecisionRequest', session_id, task_id, decisionEvent.data);
        }
        break;
      case 'tool-decision:approved':
      case 'tool-decision:denied':
      case 'tool-decision:timeout':
        if (session_id && task_id) {
          const status = type.split(':')[1] as 'approved' | 'denied' | 'timeout';
          this.emit('onToolDecisionResolved', session_id, task_id, status, data as Record<string, unknown>);
        }
        break;

      // Tool 事件
      case 'tool:start':
        if (session_id && task_id) {
          const d = data as { tool_use_id: string; tool_name: string; tool_input?: Record<string, unknown>; kind?: string; content?: unknown[]; locations?: unknown[] };
          const enrichedInput: Record<string, unknown> = { ...(d.tool_input ?? {}) };
          if (d.kind && !enrichedInput.kind) enrichedInput.kind = d.kind;
          if (d.content && !enrichedInput.content) enrichedInput.content = d.content;
          if (d.locations && !enrichedInput.locations) enrichedInput.locations = d.locations;
          this.emit('onToolStart', session_id, task_id, d.tool_use_id, d.tool_name, enrichedInput);
        }
        break;
      case 'tool:complete':
        if (session_id && task_id) {
          this.emit('onToolComplete',
            session_id,
            task_id,
            (data as { tool_use_id: string }).tool_use_id,
            (data as { tool_name: string }).tool_name,
            (data as { result: unknown }).result,
            (data as { is_error?: boolean }).is_error ?? false
          );
        }
        break;
      case 'tool:error':
        if (session_id && task_id) {
          const errorData = data as { tool_use_id: string; tool_name: string; error_message: string; error_code?: string };
          this.emit('onToolComplete',
            session_id,
            task_id,
            errorData.tool_use_id,
            errorData.tool_name,
            { error_message: errorData.error_message, error_code: errorData.error_code },
            true
          );
        }
        break;

      case 'error':
        // 處理 WebSocket 錯誤訊息
        logger.error('WebSocket error from server', {
          message: (data as { message?: string }).message || 'Unknown error',
          code: (data as { code?: string }).code,
          session_id,
        });
        // 可以在這裡觸發錯誤處理回調或更新狀態
        break;

      default:
        logger.warn('Unknown event type', { type });
    }
  }
}

// ============================================================================
// Event Filters
// ============================================================================

/**
 * 篩選特定 session 的事件
 */
export function filterBySession(
  event: WebSocketEvent,
  sessionId: string
): boolean {
  return event.session_id === sessionId;
}

/**
 * 篩選特定 task 的事件
 */
export function filterByTask(
  event: WebSocketEvent,
  taskId: string
): boolean {
  return event.task_id === taskId;
}

/**
 * 篩選串流相關事件
 */
export function isStreamingEvent(event: WebSocketEvent): boolean {
  return event.type.startsWith('streaming:');
}

/**
 * 篩選思考相關事件
 */
export function isThinkingEvent(event: WebSocketEvent): boolean {
  return event.type.startsWith('thinking:');
}

/**
 * 篩選權限相關事件
 */
export function isToolDecisionEvent(event: WebSocketEvent): boolean {
  return event.type.startsWith('tool-decision:');
}

/**
 * 篩選 CRUD 事件
 */
export function isCrudEvent(event: WebSocketEvent): boolean {
  const crudTypes: WebSocketEventType[] = [
    'sessions created',
    'session:init',
    'sessions patched',
    'sessions updated',
    'sessions removed',
    'tasks created',
    'tasks patched',
    'tasks updated',
    'tasks removed',
    'messages created',
    'messages patched',
    'messages updated',
    'messages removed',
    'messages queued',
    'message:dequeued',
  ];
  return crudTypes.includes(event.type);
}

// ============================================================================
// 建立單例
// ============================================================================

let dispatcherInstance: AgentSessionEventDispatcher | null = null;

export function getEventDispatcher(): AgentSessionEventDispatcher {
  if (!dispatcherInstance) {
    dispatcherInstance = new AgentSessionEventDispatcher();
  }
  return dispatcherInstance;
}

export function resetEventDispatcher(): void {
  if (dispatcherInstance) {
    dispatcherInstance.clearHandlers();
  }
  dispatcherInstance = null;
}
