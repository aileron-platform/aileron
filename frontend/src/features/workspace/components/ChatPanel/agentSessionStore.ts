/**
 * Agent Session Store
 *
 * 管理多 Agent 對話系統的本地狀態
 */
import { useSyncExternalStore } from 'react';

import type {
  AgentSession,
  AgentTask,
  AgentMessage,
  QueuedMessage,
  AgenticTool,
  SessionStatus,
  TaskStatus,
  PermissionRequest,
  UserInputRequest,
  ContextWindowStatus,
  TaskStatusNotice,
} from './agentSessionTypes';

export interface RunningToolExecution {
  toolUseId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  startedAt: string;
  result?: unknown;
  isError?: boolean;
  completedAt?: string;
}

// ============================================================================
// State Types
// ============================================================================

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'error';

export interface AgentSessionState {
  // 連線狀態
  connectionStatus: ConnectionStatus;
  connectionError?: string;

  // Session 狀態
  currentSessionId: string | null;
  sessions: AgentSession[];
  isLoadingSessions: boolean;

  // Task 狀態
  currentTaskId: string | null;
  tasks: AgentTask[];
  activeTask: AgentTask | null;
  activeTaskStatusNotice: TaskStatusNotice | null;
  taskErrors: Map<string, string>; // taskId -> error message

  // Message 狀態
  messages: AgentMessage[];
  totalMessages: number;
  isLoadingMessages: boolean;
  hasMoreMessages: boolean;

  // Queue 狀態
  queuedMessages: QueuedMessage[];

  // Streaming 狀態
  isStreaming: boolean;
  streamingContent: string;
  streamingTaskId: string | null;

  // Thinking 狀態
  isThinking: boolean;
  thinkingContent: string;

  // Permission 狀態
  pendingPermission: PermissionRequest | null;

  // User Input 狀態 (用於 AskUserQuestion 等工具)
  pendingUserInput: UserInputRequest | null;

  // Tool 狀態
  selectedTool: AgenticTool;

  // Tool Execution 狀態 - 追蹤正在執行的工具
  runningTools: Map<string, RunningToolExecution>;

  // Context Window 狀態
  contextWindow: ContextWindowStatus | null;
}

// ============================================================================
// Store Listener Type
// ============================================================================

export type StoreListener = () => void;

// ============================================================================
// Initial State
// ============================================================================

const INITIAL_STATE: AgentSessionState = {
  connectionStatus: 'idle',
  connectionError: undefined,

  currentSessionId: null,
  sessions: [],
  isLoadingSessions: false,

  currentTaskId: null,
  tasks: [],
  activeTask: null,
  activeTaskStatusNotice: null,
  taskErrors: new Map(),

  messages: [],
  totalMessages: 0,
  isLoadingMessages: false,
  hasMoreMessages: false,

  queuedMessages: [],

  isStreaming: false,
  streamingContent: '',
  streamingTaskId: null,

  isThinking: false,
  thinkingContent: '',

  pendingPermission: null,

  pendingUserInput: null,

  selectedTool: 'claude-code',

  runningTools: new Map(),

  contextWindow: null,
};

// ============================================================================
// Store Interface
// ============================================================================

export interface AgentSessionStore {
  // 獲取狀態
  getSnapshot: () => AgentSessionState;

  // 訂閱變更
  subscribe: (listener: StoreListener) => () => void;

  // 連線狀態
  setConnectionStatus: (status: ConnectionStatus, error?: string) => void;

  // Session 操作
  setCurrentSession: (sessionId: string | null) => void;
  setSessions: (sessions: AgentSession[]) => void;
  addSession: (session: AgentSession) => void;
  updateSession: (sessionId: string, updates: Partial<AgentSession>) => void;
  removeSession: (sessionId: string) => void;
  setLoadingSessions: (loading: boolean) => void;

  // Task 操作
  setCurrentTask: (taskId: string | null) => void;
  setTasks: (tasks: AgentTask[]) => void;
  addTask: (task: AgentTask) => void;
  updateTask: (taskId: string, updates: Partial<AgentTask>) => void;
  removeTask: (taskId: string) => void;
  setActiveTask: (task: AgentTask | null) => void;
  setActiveTaskStatusNotice: (notice: TaskStatusNotice | null) => void;
  setTaskError: (taskId: string, error: string) => void;
  clearTaskError: (taskId: string) => void;
  getTaskError: (taskId: string) => string | undefined;

  // Message 操作
  setMessages: (messages: AgentMessage[]) => void;
  addMessage: (message: AgentMessage) => void;
  updateMessage: (messageId: string, updates: Partial<AgentMessage>) => void;
  removeMessage: (messageId: string) => void;
  prependMessages: (messages: AgentMessage[]) => void;
  setTotalMessages: (total: number) => void;
  setLoadingMessages: (loading: boolean) => void;
  setHasMoreMessages: (hasMore: boolean) => void;

  // Queue 操作
  setQueuedMessages: (messages: QueuedMessage[]) => void;
  addToQueue: (message: QueuedMessage) => void;
  removeFromQueue: (messageId: string) => void;
  clearQueue: () => void;

  // Streaming 操作
  startStreaming: (taskId: string) => void;
  appendStreamingContent: (content: string) => void;
  setStreamingContent: (content: string) => void;
  endStreaming: () => void;

  // Thinking 操作
  startThinking: () => void;
  appendThinkingContent: (content: string) => void;
  setThinkingContent: (content: string) => void;
  endThinking: () => void;

  // Permission 操作
  setPendingPermission: (request: PermissionRequest | null) => void;

  // User Input 操作
  setPendingUserInput: (request: UserInputRequest | null) => void;

  // Tool 操作
  setSelectedTool: (tool: AgenticTool) => void;

  // Tool Execution 操作
  startToolExecution: (toolUseId: string, toolName: string, toolInput: Record<string, unknown>) => void;
  resolveToolExecution: (toolUseId: string, result: unknown, isError: boolean) => void;
  completeToolExecution: (toolUseId: string) => void;
  removeToolExecution: (toolUseId: string) => void;
  isToolRunning: (toolUseId: string) => boolean;
  getRunningTool: (toolUseId: string) => RunningToolExecution | undefined;
  clearRunningTools: () => void;

  // Context Window 操作
  setContextWindow: (status: ContextWindowStatus | null) => void;

  // Stale Task 操作 - 檢查並重置卡住的任務
  checkAndResetStaleTasks: (thresholdMs?: number) => void;

  // 重置
  reset: () => void;
}

// ============================================================================
// Store Factory
// ============================================================================

export function createAgentSessionStore(): AgentSessionStore {
  let state: AgentSessionState = { ...INITIAL_STATE };
  const listeners = new Set<StoreListener>();

  const notify = () => {
    listeners.forEach((listener) => listener());
  };

  const setState = (partial: Partial<AgentSessionState>) => {
    state = { ...state, ...partial };
    notify();
  };

  return {
    // 獲取狀態
    getSnapshot: () => state,

    // 訂閱變更
    subscribe: (listener: StoreListener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },

    // 連線狀態
    setConnectionStatus: (status: ConnectionStatus, error?: string) => {
      setState({ connectionStatus: status, connectionError: error });
    },

    // Session 操作
    setCurrentSession: (sessionId: string | null) => {
      setState({ currentSessionId: sessionId });
    },
    setSessions: (sessions: AgentSession[]) => {
      setState({ sessions });
    },
    addSession: (session: AgentSession) => {
      setState({ sessions: [...state.sessions, session] });
    },
    updateSession: (sessionId: string, updates: Partial<AgentSession>) => {
      const sessions = state.sessions.map((s) =>
        s.session_id === sessionId ? { ...s, ...updates } : s
      );
      setState({ sessions });
    },
    removeSession: (sessionId: string) => {
      const sessions = state.sessions.filter((s) => s.session_id !== sessionId);
      setState({ sessions });
    },
    setLoadingSessions: (loading: boolean) => {
      setState({ isLoadingSessions: loading });
    },

    // Task 操作
    setCurrentTask: (taskId: string | null) => {
      setState({ currentTaskId: taskId });
    },
    setTasks: (tasks: AgentTask[]) => {
      setState({ tasks });
    },
    addTask: (task: AgentTask) => {
      setState({ tasks: [...state.tasks, task] });
    },
    updateTask: (taskId: string, updates: Partial<AgentTask>) => {
      const tasks = state.tasks.map((t) =>
        t.task_id === taskId ? { ...t, ...updates } : t
      );
      // 同時更新 activeTask 如果它是正在更新的 task
      let activeTask = state.activeTask;
      let activeTaskStatusNotice = state.activeTaskStatusNotice;
      if (activeTask && activeTask.task_id === taskId) {
        activeTask = { ...activeTask, ...updates };
        if (updates.status && ['completed', 'failed', 'stopped'].includes(updates.status)) {
          activeTaskStatusNotice = null;
        }
      }
      setState({ tasks, activeTask, activeTaskStatusNotice });
    },
    removeTask: (taskId: string) => {
      const tasks = state.tasks.filter((t) => t.task_id !== taskId);
      let activeTask = state.activeTask;
      if (activeTask && activeTask.task_id === taskId) {
        activeTask = null;
      }
      setState({ tasks, activeTask, activeTaskStatusNotice: null });
    },
    setActiveTask: (task: AgentTask | null) => {
      setState({
        activeTask: task,
        activeTaskStatusNotice:
          task && state.activeTaskStatusNotice?.task_id === task.task_id
            ? state.activeTaskStatusNotice
            : null,
        currentTaskId: task?.task_id ?? null,
      });
    },
    setActiveTaskStatusNotice: (notice: TaskStatusNotice | null) => {
      setState({ activeTaskStatusNotice: notice });
    },

    // Task Errors 操作
    setTaskError: (taskId: string, error: string) => {
      const newTaskErrors = new Map(state.taskErrors);
      newTaskErrors.set(taskId, error);
      setState({ taskErrors: newTaskErrors });
    },
    clearTaskError: (taskId: string) => {
      const newTaskErrors = new Map(state.taskErrors);
      newTaskErrors.delete(taskId);
      setState({ taskErrors: newTaskErrors });
    },
    getTaskError: (taskId: string) => {
      return state.taskErrors.get(taskId);
    },

    // Message 操作
    setMessages: (messages: AgentMessage[]) => {
      setState({ messages });
    },
    addMessage: (message: AgentMessage) => {
      setState({ messages: [...state.messages, message] });
    },
    updateMessage: (messageId: string, updates: Partial<AgentMessage>) => {
      const messages = state.messages.map((m) =>
        m.message_id === messageId ? { ...m, ...updates } : m
      );
      setState({ messages });
    },
    removeMessage: (messageId: string) => {
      const messages = state.messages.filter((m) => m.message_id !== messageId);
      setState({ messages });
    },
    prependMessages: (messages: AgentMessage[]) => {
      setState({ messages: [...messages, ...state.messages] });
    },
    setTotalMessages: (total: number) => {
      setState({ totalMessages: total });
    },
    setLoadingMessages: (loading: boolean) => {
      setState({ isLoadingMessages: loading });
    },
    setHasMoreMessages: (hasMore: boolean) => {
      setState({ hasMoreMessages: hasMore });
    },

    // Queue 操作
    setQueuedMessages: (messages: QueuedMessage[]) => {
      setState({ queuedMessages: messages });
    },
    addToQueue: (message: QueuedMessage) => {
      setState({ queuedMessages: [...state.queuedMessages, message] });
    },
    removeFromQueue: (messageId: string) => {
      const queuedMessages = state.queuedMessages.filter(
        (m) => m.message_id !== messageId
      );
      setState({ queuedMessages });
    },
    clearQueue: () => {
      setState({ queuedMessages: [] });
    },

    // Streaming 操作
    startStreaming: (taskId: string) => {
      setState({
        isStreaming: true,
        streamingContent: '',
        streamingTaskId: taskId,
      });
    },
    appendStreamingContent: (content: string) => {
      setState({ streamingContent: state.streamingContent + content });
    },
    setStreamingContent: (content: string) => {
      setState({ streamingContent: content });
    },
    endStreaming: () => {
      // 冪等性檢查：如果已經不在 streaming 狀態，直接返回
      if (!state.isStreaming) {
        return;
      }
      setState({
        isStreaming: false,
        streamingContent: '',
        streamingTaskId: null,
      });
    },

    // Thinking 操作
    startThinking: () => {
      setState({ isThinking: true, thinkingContent: '' });
    },
    appendThinkingContent: (content: string) => {
      setState({ thinkingContent: state.thinkingContent + content });
    },
    setThinkingContent: (content: string) => {
      setState({ thinkingContent: content });
    },
    endThinking: () => {
      // 冪等性檢查：如果已經不在 thinking 狀態，直接返回
      if (!state.isThinking) {
        return;
      }
      setState({ isThinking: false, thinkingContent: '' });
    },

    // Permission 操作
    setPendingPermission: (request: PermissionRequest | null) => {
      setState({ pendingPermission: request });
    },

    // User Input 操作
    setPendingUserInput: (request: UserInputRequest | null) => {
      setState({ pendingUserInput: request });
    },

    // Tool 操作
    setSelectedTool: (tool: AgenticTool) => {
      setState({ selectedTool: tool });
    },

    // Tool Execution 操作
    startToolExecution: (toolUseId: string, toolName: string, toolInput: Record<string, unknown>) => {
      const newRunningTools = new Map(state.runningTools);
      newRunningTools.set(toolUseId, {
        toolUseId,
        toolName,
        toolInput,
        startedAt: new Date().toISOString(),
      });
      setState({ runningTools: newRunningTools });
    },
    resolveToolExecution: (toolUseId: string, result: unknown, isError: boolean) => {
      const newRunningTools = new Map(state.runningTools);
      const existing = newRunningTools.get(toolUseId);
      if (existing) {
        newRunningTools.set(toolUseId, {
          ...existing,
          result,
          isError,
          completedAt: new Date().toISOString(),
        });
      } else {
        newRunningTools.set(toolUseId, {
          toolUseId,
          toolName: 'tool',
          toolInput: {},
          startedAt: new Date().toISOString(),
          result,
          isError,
          completedAt: new Date().toISOString(),
        });
      }
      setState({ runningTools: newRunningTools });
    },
    completeToolExecution: (toolUseId: string) => {
      const newRunningTools = new Map(state.runningTools);
      newRunningTools.delete(toolUseId);
      setState({ runningTools: newRunningTools });
    },
    removeToolExecution: (toolUseId: string) => {
      const newRunningTools = new Map(state.runningTools);
      newRunningTools.delete(toolUseId);
      setState({ runningTools: newRunningTools });
    },
    isToolRunning: (toolUseId: string) => {
      return state.runningTools.has(toolUseId);
    },
    getRunningTool: (toolUseId: string) => {
      return state.runningTools.get(toolUseId);
    },
    clearRunningTools: () => {
      setState({ runningTools: new Map() });
    },

    // Context Window 操作
    setContextWindow: (status: ContextWindowStatus | null) => {
      setState({ contextWindow: status });
    },

    // Stale Task 操作 - 檢查並重置卡住的任務
    checkAndResetStaleTasks: (thresholdMs: number = 60000) => {
      // 預設閾值為 60 秒
      const now = Date.now();
      const staleTasks: string[] = [];
      const staleThreshold = now - thresholdMs;

      // 找出處於 running 或 stopping 狀態且超過閾值的任務
      state.tasks.forEach((task) => {
        if (task.status === 'running' || task.status === 'stopping') {
          const taskUpdatedTime = new Date(task.updated_at || task.created_at).getTime();
          if (taskUpdatedTime < staleThreshold) {
            staleTasks.push(task.task_id);
          }
        }
      });

      if (staleTasks.length > 0) {
        // 將卡住的任務標記為 failed
        const updatedTasks = state.tasks.map((task) => {
          if (staleTasks.includes(task.task_id)) {
            return {
              ...task,
              status: 'failed' as TaskStatus,
              error_message: 'Task disconnected due to network issue',
            };
          }
          return task;
        });

        // 清除 activeTask 和 streaming 狀態
        let activeTask = state.activeTask;
        if (activeTask && staleTasks.includes(activeTask.task_id)) {
          activeTask = null;
        }

        setState({
          tasks: updatedTasks,
          activeTask,
          activeTaskStatusNotice: activeTask ? state.activeTaskStatusNotice : null,
          isStreaming: false,
          streamingContent: '',
          streamingTaskId: null,
          isThinking: false,
          thinkingContent: '',
        });
      }
    },

    // 重置
    reset: () => {
      state = { ...INITIAL_STATE, runningTools: new Map(), taskErrors: new Map() };
      notify();
    },
  };
}

// ============================================================================
// Singleton Instance
// ============================================================================

let storeInstance: AgentSessionStore | null = null;

export function getAgentSessionStore(): AgentSessionStore {
  if (!storeInstance) {
    storeInstance = createAgentSessionStore();
  }
  return storeInstance;
}

export function resetAgentSessionStore(): void {
  if (storeInstance) {
    storeInstance.reset();
  }
  storeInstance = null;
}

/**
 * 使用 Agent Session Store Hook
 */
export function useAgentSessionStore() {
  const store = getAgentSessionStore();

  const state = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot
  );

  return { state, store };
}
