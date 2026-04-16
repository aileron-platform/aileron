
/**
 * Agent Session React Hooks
 *
 * 提供 React 元件使用 Agent Session 功能的 hooks
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useAgentSession');
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useAgentSessionStore } from './agentSessionStore';
import { getEventDispatcher } from './agentSessionEvents';
import { agentApi } from './agentSessionApi';
import {
  useWebSocketClient,
  useRealtimeData,
  useRealtimeSessions,
  useStreamingMessages,
} from '../../realtime';
import { MESSAGES_PER_PAGE } from '../../realtime/agentSession/useRealtimeData';
import type {
  AgenticTool,
  ToolDecisionRequest,
  PromptRequest,
  PermissionConfig,
} from './agentSessionTypes';
import {
  resolveAgenticToolFromCliType,
  extractToolDecisionInput,
  isAgenticTool,
  isPermissionMode,
} from './agentSessionTypes';

interface UseAgentSessionOptions {
  runtimeBaseUrl: string;
  workspaceId: string;
  cliType?: string | null;
  autoConnect?: boolean;
  gitContextId?: string | null;
}

type StreamingSnapshot = {
  taskId: string | null;
  content: string;
  thinkingContent?: string;
};

export const hasRestorableSnapshotContent = (snapshot: StreamingSnapshot | null): boolean => {
  if (!snapshot) return false;
  const hasStreaming = typeof snapshot.content === 'string' && snapshot.content.length > 0;
  const hasThinking =
    typeof snapshot.thinkingContent === 'string' && snapshot.thinkingContent.length > 0;
  return hasStreaming || hasThinking;
};

const mergeStreamingText = (prefix: string, incoming: string) => {
  if (!prefix) return incoming;
  if (!incoming) return prefix;
  if (incoming.startsWith(prefix)) return incoming;
  if (prefix.startsWith(incoming)) return prefix;

  const maxOverlap = Math.min(prefix.length, incoming.length);
  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    if (prefix.slice(-overlap) === incoming.slice(0, overlap)) {
      return prefix + incoming.slice(overlap);
    }
  }
  return prefix + incoming;
};

const STREAMING_CACHE_PREFIX = 'agent_session:streaming:';
const getStreamingCacheKey = (sessionId: string) =>
  `${STREAMING_CACHE_PREFIX}${sessionId}`;
const WS_SEQ_CACHE_PREFIX = 'agent_session:ws_seq:';
const getWsSeqCacheKey = (sessionId: string) =>
  `${WS_SEQ_CACHE_PREFIX}${sessionId}`;

// 統一的存儲寫入處理，避免重複錯誤日誌
// 使用 WeakMap 追蹤已失敗的寫入器，而非 ref
const failedWriters = new WeakMap<Storage, boolean>();

const safeLocalStorageSet = (storage: Storage, key: string, value: string, loggerInstance: ReturnType<typeof createLogger>) => {
  try {
    storage.setItem(key, value);
  } catch (error) {
    if (!failedWriters.get(storage)) {
      loggerInstance.warn('Failed to write to storage', { error, key });
      failedWriters.set(storage, true);
    }
  }
};

const saveLastActiveSession = (workspaceId: string, sessionId: string) => {
  safeLocalStorageSet(localStorage, `agent_session:last_active:${workspaceId}`, sessionId, logger);
};

const clearLastActiveSession = (workspaceId: string) => {
  try {
    localStorage.removeItem(`agent_session:last_active:${workspaceId}`);
  } catch (error) {
    logger.warn('Failed to clear last active session from localStorage', { error, workspaceId });
  }
};

// 統一的 sessionStorage 讀寫輔助函數
const safeSessionStorageGet = (key: string): string | null => {
  try {
    return sessionStorage.getItem(key);
  } catch (e) {
    logger.warn('Failed to read from sessionStorage', { error: e, key });
    return null;
  }
};

// 追蹤已顯示的警告，避免重複通知
let sessionStorageAccessWarningShown = false;

const safeSessionStorageSet = (key: string, value: string): boolean => {
  try {
    sessionStorage.setItem(key, value);
    return true;
  } catch (e) {
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      // 嘗試清理舊的快取後重試（只刪除最舊的 50%）
      const allKeys: string[] = [];
      for (let i = 0; i < sessionStorage.length; i += 1) {
        const k = sessionStorage.key(i);
        if (k && k.startsWith(STREAMING_CACHE_PREFIX)) {
          allKeys.push(k);
        }
      }

      // 只刪除最舊的 50%（假設順序就是時間順序）
      const keysToRemove = allKeys.slice(0, Math.floor(allKeys.length / 2));
      keysToRemove.forEach(k => {
        if (k !== key) {  // 確保不刪除當前 key
          sessionStorage.removeItem(k);
        }
      });

      logger.info('Cleaned up old streaming cache', {
        totalKeys: allKeys.length,
        removedKeys: keysToRemove.length,
        currentKey: key
      });

      // 重試一次
      try {
        sessionStorage.setItem(key, value);
        return true;
      } catch (retryError) {
        logger.error('SessionStorage quota exceeded after cleanup', { error: retryError, key });
      }
    } else if (e instanceof DOMException) {
      // 針對其他 DOMException 提供更詳細的錯誤記錄
      logger.error('SessionStorage access error', {
        error: e,
        key,
        errorName: e.name,
        errorMessage: e.message
      });

      if (e.name === 'SecurityError') {
        logger.warn('SessionStorage blocked by privacy settings', { key });
        // 注意：實際的 toast 通知需要在呼叫端處理
        sessionStorageAccessWarningShown = true;
      }
    } else {
      logger.error('Failed to write to sessionStorage', {
        error: e,
        key,
        errorName: e instanceof Error ? e.name : 'unknown',
      });
    }
    return false;
  }
};

const safeSessionStorageRemove = (key: string) => {
  try {
    sessionStorage.removeItem(key);
  } catch (e) {
    logger.warn('Failed to remove from sessionStorage', { error: e, key });
  }
};

const loadLastWsSeq = (sessionId: string): number | null => {
  const raw = safeSessionStorageGet(getWsSeqCacheKey(sessionId));
  if (!raw) return null;

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }
  return Math.floor(parsed);
};

const saveLastWsSeq = (sessionId: string, seq: number): void => {
  const normalizedSeq = Math.max(0, Math.floor(seq));
  safeSessionStorageSet(getWsSeqCacheKey(sessionId), String(normalizedSeq));
};

const loadStreamingSnapshot = (sessionId: string): StreamingSnapshot | null => {
  const raw = safeSessionStorageGet(getStreamingCacheKey(sessionId));
  if (!raw) return null;

  try {
    return JSON.parse(raw) as StreamingSnapshot;
  } catch (e) {
    logger.warn('Failed to parse streaming snapshot', { error: e, sessionId });
    return null;
  }
};

const resolveSnapshotThinkingContent = (
  sessionId: string,
  taskId: string | null,
  currentThinkingContent: string
): string => {
  if (currentThinkingContent.length > 0) {
    return currentThinkingContent;
  }

  const previousSnapshot = loadStreamingSnapshot(sessionId);
  if (!previousSnapshot) return '';
  if (previousSnapshot.taskId !== taskId) return '';

  return typeof previousSnapshot.thinkingContent === 'string'
    ? previousSnapshot.thinkingContent
    : '';
};

const saveStreamingSnapshot = (
  sessionId: string,
  snapshot: StreamingSnapshot,
  quotaExceededRef: React.MutableRefObject<boolean>
) => {
  if (quotaExceededRef.current) {
    logger.debug('Skipping snapshot save due to quota exceeded', { sessionId });
    return;
  }

  try {
    const serialized = JSON.stringify(snapshot);
    const success = safeSessionStorageSet(getStreamingCacheKey(sessionId), serialized);

    if (!success) {
      quotaExceededRef.current = true;
      logger.error('SessionStorage quota exceeded - streaming state will not persist', {
        sessionId,
        snapshotSize: serialized.length,
        willBeLostOnRefresh: true
      });
    }
  } catch (e) {
    logger.error('Unexpected error saving streaming snapshot', {
      error: e,
      sessionId,
      errorName: e instanceof Error ? e.name : 'unknown'
    });
    quotaExceededRef.current = true;
  }
};

const clearStreamingSnapshot = (sessionId: string) => {
  safeSessionStorageRemove(getStreamingCacheKey(sessionId));
};

/**
 * 使用 Agent Session
 *
 * 提供完整的 Agent Session 操作介面
 */
export function useAgentSession(options: UseAgentSessionOptions) {
  const { runtimeBaseUrl, workspaceId, cliType, autoConnect = true, gitContextId } = options;
  const { state, store } = useAgentSessionStore();
  const { getAccessToken } = useAuth();
  const workspaceDefaultTool = resolveAgenticToolFromCliType(cliType);
  const restoredStreamingRef = useRef<string | null>(null);
  const prevConnectedRef = useRef(false);
  const restoredStreamingPrefixRef = useRef<string | null>(null);
  const restoredThinkingPrefixRef = useRef<string | null>(null);
  const pendingStreamingResumeRef = useRef(false);
  const pendingThinkingResumeRef = useRef(false);
  // 追蹤已停止的任務 ID，用於忽略後續的 streaming 訊息
  const stoppedTaskIdsRef = useRef<Set<string>>(new Set());
  // 追蹤已顯示錯誤的任務 ID，避免 task:failed 和 streaming:error 重複顯示
  const failedTaskIdsRef = useRef<Set<string>>(new Set());
  // 追蹤 sessionStorage 配額是否已經用盡，避免重複嘗試儲存
  const sessionStorageQuotaExceededRef = useRef(false);
  const latestWsSeqRef = useRef(0);
  const allowSeqRollbackRef = useRef(false);

  const wsReplayLastSeq = useMemo(() => {
    if (!state.currentSessionId) return null;
    return loadLastWsSeq(state.currentSessionId);
  }, [state.currentSessionId]);

  // 1. Connection
  const { socket, connected, connecting, error: connError } = useWebSocketClient({
    runtimeBaseUrl,
    workspaceId,
    sessionId: state.currentSessionId,
    lastSeq: wsReplayLastSeq,
    autoConnect,
    token: getAccessToken(),
  });

  // 日誌:追蹤 sessionId 變化
  useEffect(() => {
    logger.info('useAgentSession: currentSessionId changed', {
      sessionId: state.currentSessionId,
      workspaceId,
      hasSocket: !!socket,
      connected,
      connecting
    });
  }, [state.currentSessionId, workspaceId, socket, connected, connecting]);

  // 2. Realtime Data - Must be called before useEffects that use their setters
  const {
    messages,
    tasks,
    loading: dataLoading,
    refresh,
    mergeMessages: mergeRealtimeMessages,  // 用於載入更多訊息時合併（使用 functional updater 確保讀取最新 state）
    // 分頁相關
    messagesTotal,
    hasMoreMessages: realtimeHasMore,
    loadedOffset,
    setLoadedOffset,
    setHasMoreMessages: setRealtimeHasMore,
  } = useRealtimeData({
    runtimeBaseUrl,
    sessionId: state.currentSessionId,
  });

  const {
    sessionsMap,
    setSessions: setRealtimeSessions,
    upsertSession: upsertRealtimeSession,
  } = useRealtimeSessions(workspaceId);
  const streamingMessages = useStreamingMessages(state.currentSessionId);

  useEffect(() => {
    store.setSelectedTool(workspaceDefaultTool);
  }, [workspaceId, workspaceDefaultTool, store]);

  // Sync connection status
  useEffect(() => {
    store.setConnectionStatus(
      connected ? 'open' : connecting ? 'connecting' : connError ? 'error' : 'idle',
      connError || undefined
    );
  }, [connected, connecting, connError, store]);

  // 重整/重連後先用 REST 拉一次歷史資料，再繼續接收 WebSocket
  useEffect(() => {
    if (!state.currentSessionId || !connected) {
      prevConnectedRef.current = connected;
      return;
    }

    const justReconnected = connected && !prevConnectedRef.current;
    if (justReconnected) {
      refresh()
        .then(() => {
          // 重連成功後，檢查並重置卡住的任務（超過 60 秒仍在 running/stopping 狀態）
          store.checkAndResetStaleTasks(60000);
        })
        .catch((err) => {
          logger.error('Failed to refresh data after reconnect', { error: err });
          // 通知用戶重新整理失敗
          store.setConnectionStatus('error', 'Failed to refresh messages after reconnect. Please refresh the page.');
        });
    }

    prevConnectedRef.current = connected;
  }, [connected, refresh, state.currentSessionId, store]);

  // 追蹤前一個 workspaceId，用於檢測 workspace 切換
  const prevWorkspaceIdRef = useRef<string | null>(null);

  // Initialize: Load sessions and restore last active session
  useEffect(() => {
    if (!runtimeBaseUrl || !workspaceId) return;

    const isWorkspaceSwitch = prevWorkspaceIdRef.current !== null && prevWorkspaceIdRef.current !== workspaceId;
    prevWorkspaceIdRef.current = workspaceId;

    const init = async () => {
      // 保存要驗證的 sessionId，避免依賴可能變化的 state
      let sessionIdToVerify: string | null = null;

      // 如果是 workspace 切換，重置 store 狀態並嘗試同步讀取 lastSessionId
      if (isWorkspaceSwitch) {
        logger.debug('Workspace switched, resetting store state', {
          prevWorkspaceId: prevWorkspaceIdRef.current,
          newWorkspaceId: workspaceId
        });

        // 重置 store 狀態，清除舊 workspace 的所有資料
        store.reset();

        // 讀取 localStorage 中的 lastSessionId，稍後在驗證後再設置
        try {
          const lastSessionId = localStorage.getItem(`agent_session:last_active:${workspaceId}`);
          if (lastSessionId) {
            sessionIdToVerify = lastSessionId;
            logger.debug('Workspace switched, found last session to verify', { workspaceId, lastSessionId });
          } else {
            logger.debug('Workspace switched, no previous session found', { workspaceId });
          }
        } catch (error) {
          logger.warn('Could not restore last session during workspace switch', {
            error,
            errorName: error instanceof Error ? error.name : 'unknown',
            workspaceId
          });

          // 檢查是否為 SecurityError（隱私模式）
          if (error instanceof DOMException && error.name === 'SecurityError') {
            logger.warn('LocalStorage access blocked - browser may be in private mode');
            // 注意：實際的 toast 通知需要在呼叫端處理
          }
        }
        // 注意：這裡不要立即 setCurrentSession，等到驗證通過後再設置
      }

      // Load sessions
      store.setLoadingSessions(true);
      try {
        const response = await agentApi.sessions.listSessions(runtimeBaseUrl, {
          workspace_id: workspaceId,
          source: 'user',
          archived: false,
          limit: 50,
        });
        store.setSessions(response.items);
        setRealtimeSessions(response.items);

        // 如果不是 workspace 切換（初次載入），才在這裡恢復 session
        if (!isWorkspaceSwitch) {
          try {
            const lastSessionId = localStorage.getItem(`agent_session:last_active:${workspaceId}`);
            if (lastSessionId) {
              // 驗證 session 是否仍存在於載入的列表中
              const sessionExists = response.items.some(s => s.session_id === lastSessionId);
              if (sessionExists) {
                store.setCurrentSession(lastSessionId);
              } else {
                logger.debug('Previously saved session no longer exists, will select latest or create new', { lastSessionId, workspaceId });
                // 不設置為 null,讓後續的統一邏輯處理
                sessionIdToVerify = null;
              }
            } else {
              // 沒有 lastSessionId,讓後續邏輯選擇最新的或建立新的
              logger.debug('No previous session found on first load, will select latest or create new', { workspaceId });
              sessionIdToVerify = null;
            }
          } catch (error) {
            logger.warn('Could not restore last session from localStorage', {
              error,
              errorName: error instanceof Error ? error.name : 'unknown',
              workspaceId
            });

            // 檢查是否為 SecurityError（隱私模式）
            if (error instanceof DOMException && error.name === 'SecurityError') {
              logger.warn('LocalStorage access blocked - browser may be in private mode');
            }

            sessionIdToVerify = null;
          }
        }

        // 如果是 workspace 切換，驗證先前設定的 session 是否仍存在
        // 使用保存的 sessionIdToVerify 而非 state.currentSessionId，避免競態條件
        let shouldSelectNewSession = false;
        if (isWorkspaceSwitch && sessionIdToVerify) {
          const sessionExists = response.items.some(s => s.session_id === sessionIdToVerify);
          if (!sessionExists) {
            logger.debug('Previously restored session no longer exists after workspace switch', {
              sessionId: sessionIdToVerify,
              workspaceId
            });
            // 標記需要選擇新的 session，但先不要清空 currentSessionId 避免斷開連線
            shouldSelectNewSession = true;
            sessionIdToVerify = null;
          }
        }

        // 如果是 workspace 切換，或初次載入沒有可用 session,根據情況選擇或建立 session
        const currentSessionId = store.getSnapshot().currentSessionId;

        if (isWorkspaceSwitch || !currentSessionId) {
          const action = isWorkspaceSwitch ? 'Workspace switch' : 'First load';
          logger.debug(`${action}: selecting session to connect`, {
            workspaceId,
            hasSessionToVerify: !!sessionIdToVerify,
            shouldSelectNewSession,
            totalSessions: response.items.length,
            currentSessionId,
          });

          let selectedSessionId: string | null = null;

          if (sessionIdToVerify && !shouldSelectNewSession) {
            // 情況1: 有預設 session 且驗證通過，連線到預設 session
            selectedSessionId = sessionIdToVerify;
            logger.info(`✓ Case 1: Auto-connecting to previously selected session (${action})`, {
              workspaceId,
              sessionId: sessionIdToVerify
            });
          } else if (response.items.length > 0) {
            // 情況2: 沒有預設 session 或預設已失效，選擇最新的（列表第一個是最近更新的）
            const latestSession = response.items[0];
            selectedSessionId = latestSession.session_id;
            logger.info(`✓ Case 2: Auto-selecting latest session (${action})`, {
              workspaceId,
              sessionId: latestSession.session_id,
              createdAt: latestSession.created_at,
              reason: shouldSelectNewSession ? 'previous session no longer exists' : 'no previous session'
            });
          } else {
            // 情況3: 沒有任何 sessions，建立一個新的
            logger.debug(`✓ Case 3: No sessions found, creating initial session (${action})`, { workspaceId });
            try {
              const newSession = await agentApi.sessions.createSession(runtimeBaseUrl, {
                workspace_id: workspaceId,
                agentic_tool: workspaceDefaultTool,
                git_context_id: gitContextId ?? undefined,
              });
              upsertRealtimeSession(newSession);
              saveLastWsSeq(newSession.session_id, 0);
              selectedSessionId = newSession.session_id;
              logger.info(`✓ Case 3: Auto-created and connecting to new session (${action})`, {
                workspaceId,
                sessionId: newSession.session_id
              });
            } catch (createError) {
              logger.error('Failed to auto-create initial session', {
                error: createError,
                errorMessage: createError instanceof Error ? createError.message : 'Unknown error',
                workspaceId
              });
              // 通知用戶建立失敗
              store.setConnectionStatus('error',
                'Unable to initialize this workspace. Please check your connection and try again.'
              );
            }
          }

          // 統一設置選定的 session (確保只設置一次)
          if (selectedSessionId) {
            logger.info(`✓ Setting current session (${action})`, {
              workspaceId,
              sessionId: selectedSessionId
            });
            store.setCurrentSession(selectedSessionId);
            saveLastActiveSession(workspaceId, selectedSessionId);
          } else {
            // 這種情況不應該發生,但作為安全保護
            logger.error(`No session selected after ${action.toLowerCase()} logic!`, {
              workspaceId,
              sessionIdToVerify,
              shouldSelectNewSession,
              totalSessions: response.items.length
            });
            store.setConnectionStatus('error',
              'Failed to select a session. Please refresh the page.'
            );
          }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to load sessions';
        logger.error('Failed to load sessions', { error, errorMessage });
        // 通知用戶載入失敗
        store.setConnectionStatus('error', 'Unable to load sessions. Please check your connection and try again.');
      } finally {
        store.setLoadingSessions(false);
      }
    };

    init();
  }, [runtimeBaseUrl, workspaceId, workspaceDefaultTool, store, setRealtimeSessions, upsertRealtimeSession, gitContextId]);

  // Dispatch events from WebSocket to Dispatcher
  useEffect(() => {
    if (!socket) return;
    const dispatcher = getEventDispatcher();
    allowSeqRollbackRef.current = true;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        // 驗證基本格式
        if (!data || typeof data !== 'object') {
          logger.warn('WS message is not an object', { data });
          return;
        }
        if (!data.type) {
          logger.warn('WS message missing type field', { data });
          return;
        }

        const eventSeq = typeof data.seq === 'number' ? data.seq : null;
        const eventSessionId = typeof data.session_id === 'string' ? data.session_id : null;
        if (
          eventSeq !== null &&
          eventSessionId &&
          state.currentSessionId &&
          eventSessionId === state.currentSessionId
        ) {
          if (eventSeq <= latestWsSeqRef.current) {
            if (!(allowSeqRollbackRef.current && eventSeq < latestWsSeqRef.current)) {
              return;
            }
            logger.warn('Detected websocket seq rollback, resetting local cursor', {
              sessionId: eventSessionId,
              previousSeq: latestWsSeqRef.current,
              incomingSeq: eventSeq,
            });
          }
          latestWsSeqRef.current = eventSeq;
          saveLastWsSeq(eventSessionId, eventSeq);
          allowSeqRollbackRef.current = false;
        }

        if (data.type === 'pong' || data.type === 'subscribed' || data.type === 'unsubscribed') return;
        dispatcher.dispatch(data);
      } catch (e) {
        logger.error('Failed to process WS message', { error: e, rawData: event.data });
      }
    };

    socket.addEventListener('message', handleMessage);
    return () => socket.removeEventListener('message', handleMessage);
  }, [socket, state.currentSessionId]);

  // Tool events handling - show tool usage immediately on tool:start
  useEffect(() => {
    const dispatcher = getEventDispatcher();

    const unsubscribe = dispatcher.subscribe({
      onToolStart: (sessionId, _taskId, toolUseId, toolName, toolInput) => {
        if (sessionId !== state.currentSessionId) return;
        store.startToolExecution(toolUseId, toolName, toolInput);
      },
      onToolComplete: (sessionId, _taskId, toolUseId, _toolName, result, isError) => {
        if (sessionId !== state.currentSessionId) return;
        store.resolveToolExecution(toolUseId, result, isError);
      },
      // 當實際訊息帶著 tool_use 出現時，移除暫存的 running tool
      onMessageCreated: (message) => {
        if (message.session_id !== state.currentSessionId) return;
        message.content_blocks
          ?.filter(b => b.type === 'tool_use')
          .forEach(b => store.removeToolExecution(b.id));
      }
    });

    return () => {
      unsubscribe();
    };
  }, [state.currentSessionId, store]);

  // 使用 ref 來保持對最新 pendingPermission 的引用，避免閉包問題
  const pendingPermissionRef = useRef(state.pendingPermission);
  useEffect(() => {
    pendingPermissionRef.current = state.pendingPermission;
  }, [state.pendingPermission]);

  const pendingUserInputRef = useRef(state.pendingUserInput);
  useEffect(() => {
    pendingUserInputRef.current = state.pendingUserInput;
  }, [state.pendingUserInput]);

  // 使用 ref 保持對最新 currentSessionId 的引用
  const currentSessionIdRef = useRef(state.currentSessionId);
  useEffect(() => {
    currentSessionIdRef.current = state.currentSessionId;
  }, [state.currentSessionId]);

  useEffect(() => {
    const sessionId = state.currentSessionId;
    if (!sessionId) {
      latestWsSeqRef.current = 0;
      allowSeqRollbackRef.current = false;
      return;
    }
    latestWsSeqRef.current = loadLastWsSeq(sessionId) ?? 0;
    allowSeqRollbackRef.current = true;
  }, [state.currentSessionId]);

  // Queue events handling - 處理訊息佇列相關事件
  useEffect(() => {
    const dispatcher = getEventDispatcher();

    const unsubscribe = dispatcher.subscribe({
      onMessageQueued: (sessionId, message) => {
        if (sessionId !== currentSessionIdRef.current) return;
        store.addToQueue(message);
      },
      onMessageDequeued: (sessionId, messageId, _queuePosition, _reason) => {
        if (sessionId !== currentSessionIdRef.current) return;
        store.removeFromQueue(messageId);
      },
    });

    return () => {
      unsubscribe();
    };
  }, [store]);

  // Tool Decision events handling
  useEffect(() => {
    const dispatcher = getEventDispatcher();

    const unsubscribe = dispatcher.subscribe({
      onToolDecisionRequest: (sessionId, taskId, request) => {
        if (sessionId !== currentSessionIdRef.current) return;

        const toolCall = request.tool_call || {};
        const toolName = toolCall.title || 'tool';
        const toolInput = extractToolDecisionInput(toolCall);
        const toolUseId = toolCall.toolCallId;

        if (request.decision_type === 'permission') {
          store.setPendingPermission({
            request_id: request.request_id,
            task_id: taskId,
            tool_name: toolName,
            tool_input: toolInput,
            timeout: request.timeout,
            tool_use_id: toolUseId,
            options: request.options,
            tool_call: request.tool_call,
          });
          return;
        }

        if (request.decision_type === 'user_input') {
          store.setPendingUserInput({
            request_id: request.request_id,
            task_id: taskId,
            tool_name: toolName,
            tool_input: toolInput,
            timeout: request.timeout,
            tool_use_id: toolUseId,
            options: request.options,
            tool_call: request.tool_call,
          });
        }
      },
      onToolDecisionResolved: (sessionId, _taskId, _status, payload) => {
        if (sessionId !== currentSessionIdRef.current) return;
        const requestId = (payload as { request_id?: string }).request_id;
        if (!requestId) return;

        const pendingPermission = pendingPermissionRef.current;
        if (pendingPermission && pendingPermission.request_id === requestId) {
          store.setPendingPermission(null);
        }

        const pendingInput = pendingUserInputRef.current;
        if (pendingInput && pendingInput.request_id === requestId) {
          store.setPendingUserInput(null);
        }
      },
    });

    return () => {
      unsubscribe();
    };
  }, [store]);  // 只依賴 store，避免因 state 變化導致重複訂閱

  // Task stop events handling - 當收到停止確認時，立即清除 streaming 狀態
  useEffect(() => {
    const dispatcher = getEventDispatcher();

    const unsubscribe = dispatcher.subscribe({
      onTaskStopAck: (sessionId, taskId) => {
        if (sessionId !== currentSessionIdRef.current) return;

        // 標記此任務為已停止，後續的 streaming 訊息將被忽略
        stoppedTaskIdsRef.current.add(taskId);

        // 立即結束 streaming 狀態
        store.endStreaming();
        store.endThinking();
        store.setStreamingContent('');
        store.setThinkingContent('');
        store.clearRunningTools();

        // 清除 streaming snapshot
        if (sessionId) {
          clearStreamingSnapshot(sessionId);
        }
        restoredStreamingPrefixRef.current = null;
        restoredThinkingPrefixRef.current = null;
        pendingStreamingResumeRef.current = false;
        pendingThinkingResumeRef.current = false;
      },
      onTaskStopped: (sessionId, taskId) => {
        if (sessionId !== currentSessionIdRef.current) return;

        // 確保 streaming 狀態已清除（備用）
        store.endStreaming();
        store.endThinking();
        store.clearRunningTools();

        // 任務已完全停止，可以從追蹤集合中移除（延遲清理，避免競態條件）
        setTimeout(() => {
          stoppedTaskIdsRef.current.delete(taskId);
        }, 1000);
      },
      onTaskFailed: (sessionId, taskId, errorMsg) => {
        if (sessionId !== currentSessionIdRef.current) return;

        // 記錄任務失敗事件（這是重要的錯誤事件）
        const currentState = store.getSnapshot();
        logger.error('Task failed', {
          sessionId,
          taskId,
          errorMsg: errorMsg || '<no error message>',
          activeTaskId: currentState.activeTask?.task_id,
          isStreaming: currentState.isStreaming,
          isThinking: currentState.isThinking
        });

        const displayError = errorMsg || 'Task failed unexpectedly. Please try again.';

        // 記錄任務錯誤到 store
        store.setTaskError(taskId, displayError);

        // 將錯誤訊息插入聊天流（避免與 streaming:error 重複）
        if (!failedTaskIdsRef.current.has(taskId)) {
          failedTaskIdsRef.current.add(taskId);
          store.addMessage({
            message_id: `error-${taskId}-${Date.now()}`,
            session_id: sessionId,
            task_id: taskId,
            created_at: new Date().toISOString(),
            index: currentState.messages.length,
            type: 'assistant',
            role: 'assistant',
            content_blocks: [{
              type: 'system_complete',
              stop_reason: 'error',
              message: displayError,
            } as any],
          });
        }

        // 任務失敗時也要清除 streaming 狀態
        store.endStreaming();
        store.endThinking();
        store.clearRunningTools();

        // 清除 streaming snapshot
        if (sessionId) {
          clearStreamingSnapshot(sessionId);
        }
        restoredStreamingPrefixRef.current = null;
        restoredThinkingPrefixRef.current = null;
        pendingStreamingResumeRef.current = false;
        pendingThinkingResumeRef.current = false;
      },
      // Task completed event - 當任務正常完成時，延遲清除 streaming 狀態以確保完整顯示
      onTaskCompleted: (sessionId, taskId) => {
        if (sessionId !== currentSessionIdRef.current) return;

        logger.debug('Task completed, checking streaming state before clearing', {
          sessionId,
          taskId,
          isStreaming: store.getSnapshot().isStreaming,
          isThinking: store.getSnapshot().isThinking
        });

        // 延遲 100ms 清除，給 streaming:end 事件處理的時間
        setTimeout(() => {
          const currentState = store.getSnapshot();
          // 只在沒有 streaming 時才清除
          if (!currentState.isStreaming && !currentState.isThinking) {
            store.clearRunningTools();
          }
        }, 100);

        void refresh().catch((error) => {
          logger.warn('Failed to refresh realtime data after task completion', {
            sessionId,
            taskId,
            error,
          });
        });

        // 清除 streaming snapshot
        clearStreamingSnapshot(sessionId);
        restoredStreamingPrefixRef.current = null;
        restoredThinkingPrefixRef.current = null;
        pendingStreamingResumeRef.current = false;
        pendingThinkingResumeRef.current = false;
      },
      onStreamingError: (sessionId, taskId, error, code) => {
        if (sessionId !== currentSessionIdRef.current) return;

        logger.error('Streaming error', { sessionId, taskId, error, code });

        // 將 streaming 錯誤插入聊天流（避免與 task:failed 重複）
        if (!failedTaskIdsRef.current.has(taskId)) {
          failedTaskIdsRef.current.add(taskId);
          const currentState = store.getSnapshot();
          store.addMessage({
            message_id: `streaming-error-${taskId}-${Date.now()}`,
            session_id: sessionId,
            task_id: taskId,
            created_at: new Date().toISOString(),
            index: currentState.messages.length,
            type: 'assistant',
            role: 'assistant',
            content_blocks: [{
              type: 'system_complete',
              stop_reason: code || 'error',
              message: error,
            } as any],
          });
        }

        store.endStreaming();
        store.endThinking();
        store.clearRunningTools();
      },
    });

    return () => {
      unsubscribe();
    };
  }, [refresh, store]);

  // 切換 Session 時重置暫態狀態，避免跨 Session 汙染。
  useEffect(() => {
    store.endStreaming();
    store.endThinking();
    store.setStreamingContent('');
    store.setThinkingContent('');
    store.clearRunningTools();
    store.setPendingPermission(null);
    store.setPendingUserInput(null);
    store.clearQueue();
    stoppedTaskIdsRef.current.clear();
    failedTaskIdsRef.current.clear();
    restoredStreamingRef.current = null;
    restoredStreamingPrefixRef.current = null;
    restoredThinkingPrefixRef.current = null;
    pendingStreamingResumeRef.current = false;
    pendingThinkingResumeRef.current = false;
  }, [state.currentSessionId, store]);

  // Sync Sessions from realtime map to store
  useEffect(() => {
    const sessionsFromMap = Array.from(sessionsMap.values());
    if (sessionsFromMap.length > 0) {
      store.setSessions(sessionsFromMap);
    }
  }, [sessionsMap, store]);

  // Sync Messages and Tasks
  useEffect(() => {
    if (state.currentSessionId) {
      store.setMessages(messages);
      store.setTotalMessages(messagesTotal);  // 使用 API 返回的 total
      store.setHasMoreMessages(realtimeHasMore);  // 使用 realtime data 的 hasMore
      store.setTasks(tasks);
      store.setLoadingMessages(dataLoading);

      // 以當前 session 的活躍 task 集合判斷，避免多 task session 下被單一舊任務誤導。
      const activeTasks = tasks.filter(t =>
        t.session_id === state.currentSessionId &&
        ['running', 'awaiting_permission', 'stopping', 'created'].includes(t.status)
      );
      const activeTask = activeTasks.length > 0 ? activeTasks[activeTasks.length - 1] : null;
      const previousActiveTask = state.activeTask;
      const newActiveTask = activeTask || null;

      // 當 activeTask 從有值變為 null 時，處理狀態清除
      if (previousActiveTask && !newActiveTask) {
        logger.debug('Active task cleared', {
          previousTaskId: previousActiveTask.task_id,
          previousStatus: previousActiveTask.status,
          isStreaming: state.isStreaming,
          isThinking: state.isThinking
        });

        // 只清除 running tools，streaming 狀態由 streaming:end 事件處理
        store.clearRunningTools();

        // 如果 task 是 completed/stopped 狀態，延遲檢查並清除
        if (['completed', 'stopped', 'failed'].includes(previousActiveTask.status)) {
          setTimeout(() => {
            const currentState = store.getSnapshot();
            if (currentState.isStreaming && !currentState.activeTask) {
              logger.debug('Force ending streaming after task completion');
              store.endStreaming();
            }
            if (currentState.isThinking && !currentState.activeTask) {
              store.endThinking();
            }
          }, 500);
        }
      }

      store.setActiveTask(newActiveTask);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // state.activeTask, state.isStreaming, state.isThinking 僅用於比較，不應作為依賴
    // 否則當 store.endStreaming() 或 store.endThinking() 修改這些值時會造成無限迴圈
  }, [messages, tasks, dataLoading, state.currentSessionId, store, messagesTotal, realtimeHasMore]);

  // 注意：歷史訊息的載入已由 useRealtimeData 處理，包含合併邏輯
  // 不再需要額外的 fetchHistory，避免覆蓋 useRealtimeData 的合併結果

  // Sync Streaming & Thinking
  useEffect(() => {
    // Find active streaming/thinking messages
    // Note: This logic assumes single active stream/thinking displayed in main UI via store
    // Phase 5 should update UI to use streamingMessages map directly.

    // 檢查是否在等待權限 - 如果是，暫停流式訊息
    const currentSessionId = state.currentSessionId;
    const hasPendingPermissionForCurrentSession =
      !!state.pendingPermission &&
      state.tasks.some(
        t =>
          t.session_id === currentSessionId &&
          t.task_id === state.pendingPermission?.task_id
      );
    const isAwaitingPermission =
      hasPendingPermissionForCurrentSession ||
      (state.activeTask?.session_id === currentSessionId &&
        state.activeTask?.status === 'awaiting_permission') ||
      state.tasks.some(
        t => t.session_id === currentSessionId && t.status === 'awaiting_permission'
      );

    if (isAwaitingPermission) {
      // 權限請求時暫停流式訊息，不更新內容
      // 但不結束流式狀態，因為批准後需要繼續
      return;
    }

    // 檢查當前任務是否已被停止 - 如果是，忽略後續的 streaming 更新
    const activeTaskId = state.activeTask?.task_id;
    if (activeTaskId && stoppedTaskIdsRef.current.has(activeTaskId)) {
      // 已停止的任務，不更新 streaming 內容
      return;
    }

    const activeStatuses = ['running', 'stopping', 'created'];
    const hasActiveTask =
      (state.activeTask &&
        state.activeTask.session_id === currentSessionId &&
        activeStatuses.includes(state.activeTask.status)) ||
      state.tasks.some(
        t => t.session_id === currentSessionId && activeStatuses.includes(t.status)
      );

    const currentSessionStreams = Array.from(streamingMessages.values()).filter(
      m => m.session_id === currentSessionId
    );

    const activeStream = currentSessionStreams.find(m => m.isStreaming);
    if (activeStream) {
      pendingStreamingResumeRef.current = false;
      if (!state.isStreaming) store.startStreaming(activeStream.task_id || '');
      const base = restoredStreamingPrefixRef.current || '';
      const merged = mergeStreamingText(base, activeStream.content);
      store.setStreamingContent(merged);
    } else if (state.isStreaming) {
      // Reload 後 streamingMessages 會先是空的；若我們剛還原過 snapshot，需等待新 chunk 接上
      if (pendingStreamingResumeRef.current) {
        // 若資料載入已完成且沒有任何活躍任務，代表 snapshot 不會再續傳，應立即收斂 UI。
        if (!state.isLoadingMessages && !hasActiveTask) {
          logger.info('Ending streaming state (no active stream/event)', {
            sessionId: currentSessionId,
            reason: 'resume-timeout-no-active-task',
            hadPendingResume: pendingStreamingResumeRef.current,
            hasActiveTask,
          });
          store.endStreaming();
          restoredStreamingPrefixRef.current = null;
          pendingStreamingResumeRef.current = false;
        }
      } else {
        logger.info('Ending streaming state (stream closed)', {
          sessionId: currentSessionId,
          reason: 'no-active-stream',
          hasActiveTask,
        });
        store.endStreaming();
        restoredStreamingPrefixRef.current = null;
      }
    }

    const activeThinking = currentSessionStreams.find(m => m.isThinking);
    if (activeThinking) {
      pendingThinkingResumeRef.current = false;
      if (!state.isThinking) store.startThinking();
      const base = restoredThinkingPrefixRef.current || '';
      const merged = mergeStreamingText(base, activeThinking.thinkingContent || '');
      store.setThinkingContent(merged);
    } else if (state.isThinking) {
      if (pendingThinkingResumeRef.current) {
        if (!state.isLoadingMessages && !hasActiveTask) {
          logger.info('Ending thinking state (no active think/event)', {
            sessionId: currentSessionId,
            reason: 'resume-timeout-no-active-task',
            hadPendingResume: pendingThinkingResumeRef.current,
            hasActiveTask,
          });
          store.endThinking();
          restoredThinkingPrefixRef.current = null;
          pendingThinkingResumeRef.current = false;
        }
      } else {
        logger.info('Ending thinking state (think closed)', {
          sessionId: currentSessionId,
          reason: 'no-active-thinking',
          hasActiveTask,
        });
        store.endThinking();
        restoredThinkingPrefixRef.current = null;
      }
    }
  }, [
    streamingMessages,
    store,
    state.isStreaming,
    state.isThinking,
    state.activeTask,
    state.tasks,
    state.pendingPermission,
    state.isLoadingMessages,
  ]);

  // Persist streaming buffer so reload後仍能顯示既有輸出並持續接收新的 chunk
  useEffect(() => {
    const sessionId = state.currentSessionId;
    if (!sessionId) return;

    const activeStatuses = ['running', 'awaiting_permission', 'stopping', 'created'];
    const sessionTasks = state.tasks.filter(t => t.session_id === sessionId);
    const hasActiveTask =
      state.isStreaming ||
      state.isThinking ||
      (state.activeTask &&
        state.activeTask.session_id === sessionId &&
        activeStatuses.includes(state.activeTask.status)) ||
      sessionTasks.some(t => activeStatuses.includes(t.status));
    const activeTaskId = state.streamingTaskId || state.activeTask?.task_id || null;

    if (state.isStreaming || state.isThinking || hasActiveTask) {
      const thinkingForSnapshot = resolveSnapshotThinkingContent(
        sessionId,
        activeTaskId,
        state.thinkingContent,
      );
      saveStreamingSnapshot(sessionId, {
        taskId: activeTaskId,
        content: state.streamingContent,
        thinkingContent: thinkingForSnapshot,
      }, sessionStorageQuotaExceededRef);
    } else if (sessionTasks.length > 0 && !hasActiveTask) {
      clearStreamingSnapshot(sessionId);
      restoredStreamingRef.current = null;
      restoredStreamingPrefixRef.current = null;
      restoredThinkingPrefixRef.current = null;
      pendingStreamingResumeRef.current = false;
      pendingThinkingResumeRef.current = false;
    }
  }, [
    state.isStreaming,
    state.isThinking,
    state.streamingContent,
    state.thinkingContent,
    state.streamingTaskId,
    state.activeTask,
    state.tasks,
    state.currentSessionId,
  ]);

  // 在重新整理後，如仍有 running task，還原暫存的串流內容
  useEffect(() => {
    const sessionId = state.currentSessionId;
    if (!sessionId) return;
    if (restoredStreamingRef.current === sessionId) return;
    if (state.isStreaming || state.isThinking) return;

    const snapshot = loadStreamingSnapshot(sessionId);
    if (hasRestorableSnapshotContent(snapshot)) {
      const hasStreaming = snapshot.content.length > 0;
      const hasThinking = typeof snapshot.thinkingContent === 'string' && snapshot.thinkingContent.length > 0;
      const taskId = snapshot.taskId || state.activeTask?.task_id || 'streaming-snapshot';

      if (hasStreaming) {
        store.startStreaming(taskId);
        store.setStreamingContent(snapshot.content);
      }

      if (hasThinking) {
        store.startThinking();
        store.setThinkingContent(snapshot.thinkingContent || '');
      }

      restoredStreamingPrefixRef.current = hasStreaming ? snapshot.content : null;
      restoredThinkingPrefixRef.current = hasThinking ? (snapshot.thinkingContent || '') : null;
      pendingStreamingResumeRef.current = hasStreaming;
      pendingThinkingResumeRef.current = hasThinking;
      restoredStreamingRef.current = sessionId;
    }
  }, [
    state.currentSessionId,
    state.activeTask,
    state.isStreaming,
    state.isThinking,
    store,
  ]);

  // --- Actions ---

  // 載入 sessions (Managed by useRealtimeSessions mainly, but can force refresh via API if needed)
  const loadSessions = useCallback(async () => {
    store.setLoadingSessions(true);
    try {
      const response = await agentApi.sessions.listSessions(runtimeBaseUrl, {
        workspace_id: workspaceId,
        source: 'user',
        archived: false,
        limit: 50,
      });
      store.setSessions(response.items);
      // Also sync to realtime map so it persists across re-renders
      setRealtimeSessions(response.items);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load sessions';
      logger.error('Failed to load sessions', { error, errorMessage });
      // 通知用戶重新載入失敗
      store.setConnectionStatus('error', 'Unable to refresh sessions. Please try again.');
    } finally {
      store.setLoadingSessions(false);
    }
  }, [runtimeBaseUrl, workspaceId, store, setRealtimeSessions]);

  // Load messages is mainly handled by useRealtimeData automatically on session change.
  // manual loadMessages is mostly for session switching which is handled by selectSession.
  const loadMessages = useCallback(async (sessionId: string) => {
    // Just setting current session triggers useRealtimeData
    store.setCurrentSession(sessionId);
  }, [store]);

  // Load more messages (Pagination) - 載入更舊的訊息
  const loadMoreMessages = useCallback(async () => {
    if (!state.currentSessionId || state.isLoadingMessages) {
      return;
    }

    // 計算要載入的 offset（往前載入更舊的訊息）
    const olderOffset = Math.max(0, loadedOffset - MESSAGES_PER_PAGE);
    const actualLimit = loadedOffset - olderOffset;  // 實際要載入的數量

    if (actualLimit <= 0) {
      // 已到達最舊的訊息，不再有歷史訊息可載入
      logger.debug('No more historical messages to load', {
        sessionId: state.currentSessionId,
        loadedOffset,
        actualLimit
      });
      store.setHasMoreMessages(false);
      setRealtimeHasMore(false);
      return;
    }

    store.setLoadingMessages(true);
    try {
      const response = await agentApi.messages.listMessages(
        runtimeBaseUrl,
        state.currentSessionId,
        { limit: actualLimit, offset: olderOffset }
      );

      // 驗證回應格式
      if (!response?.items || !Array.isArray(response.items)) {
        throw new Error('Invalid API response: expected items array');
      }

      // 合併舊訊息 - mergeRealtimeMessages 會更新內部的 messagesMap state
      // 使用 functional updater 確保合併時讀取最新的 map 狀態
      // "Sync Messages and Tasks" effect（第 751 行）會自動將變更同步到 store
      mergeRealtimeMessages(response.items);

      // 更新 offset 和 hasMoreMessages
      setLoadedOffset(olderOffset);
      const hasMore = olderOffset > 0;
      setRealtimeHasMore(hasMore);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load more messages';
      logger.error('Failed to load more messages', {
        error,
        sessionId: state.currentSessionId,
        offset: olderOffset,
        limit: actualLimit,
        errorMessage
      });
      // 設置連線狀態讓 UI 可以顯示錯誤提示
      store.setConnectionStatus('error', 'Failed to load older messages. Please try again.');
      // 不設置 hasMoreMessages 為 false，允許重試
    } finally {
      store.setLoadingMessages(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    runtimeBaseUrl,
    state.currentSessionId,
    state.isLoadingMessages,
    store,
    loadedOffset,
    setLoadedOffset,
    setRealtimeHasMore,
    mergeRealtimeMessages,
    MESSAGES_PER_PAGE,
  ]);

  const selectSession = useCallback(
    async (sessionId: string) => {
      store.setCurrentSession(sessionId);
      // Don't clear messages here - let useRealtimeData handle it
      // Save to localStorage for persistence
      saveLastActiveSession(workspaceId, sessionId);
      // useRealtimeData will react and fetch the messages
    },
    [store, workspaceId]
  );

  const createSession = useCallback(
    async (tool?: AgenticTool, permissionConfig?: PermissionConfig) => {
      const resolvedTool = isAgenticTool(tool)
        ? tool
        : isAgenticTool(state.selectedTool)
          ? state.selectedTool
          : workspaceDefaultTool;
      const resolvedPermissionConfig = permissionConfig && isPermissionMode(permissionConfig.mode)
        ? permissionConfig
        : undefined;

      try {
        const session = await agentApi.sessions.createSession(runtimeBaseUrl, {
          workspace_id: workspaceId,
          agentic_tool: resolvedTool,
          permission_config: resolvedPermissionConfig,
          git_context_id: gitContextId ?? undefined,
        });
        upsertRealtimeSession(session);
        saveLastWsSeq(session.session_id, 0);
        store.setCurrentSession(session.session_id);
        // Save to localStorage for persistence
        saveLastActiveSession(workspaceId, session.session_id);
        return session;
      } catch (error) {
        logger.error('Failed to create session', {
          error,
          workspaceId,
          requestedTool: tool,
          selectedTool: state.selectedTool,
          resolvedTool,
          permissionMode: permissionConfig?.mode,
        });
        throw error;
      }
    },
    [runtimeBaseUrl, workspaceId, workspaceDefaultTool, state.selectedTool, store, upsertRealtimeSession, gitContextId]
  );

  const sendMessage = useCallback(
    async (prompt: string, options?: Partial<PromptRequest>, permissionConfig?: PermissionConfig) => {
      const currentState = store.getSnapshot();

      // 防止重複發送：檢查是否正在 streaming 或 thinking
      if (currentState.isStreaming || currentState.isThinking) {
        logger.warn('Cannot send message while streaming/thinking is active', {
          isStreaming: currentState.isStreaming,
          isThinking: currentState.isThinking
        });
        return { success: false, error: 'Already processing' };
      }

      // 防止重複發送：檢查是否有正在執行的任務
      if (currentState.activeTask?.status === 'running') {
        logger.warn('Cannot send message while task is running', {
          taskId: currentState.activeTask.task_id,
          taskStatus: currentState.activeTask.status
        });
        return { success: false, error: 'Task is running' };
      }

      let sessionId = state.currentSessionId;

      if (!sessionId) {
        const session = await createSession(undefined, permissionConfig);
        sessionId = session.session_id;
      }

      try {
        const response = await agentApi.sessions.executePrompt(
          runtimeBaseUrl,
          sessionId,
          {
            prompt,
            stream: true,
            permission_mode: permissionConfig?.mode,
            ...options,
          }
        );
        return response;
      } catch (error) {
        logger.error('Failed to send message', { error });
        throw error;
      }
    },
    [runtimeBaseUrl, state.currentSessionId, createSession]
  );

  const stopTask = useCallback(async () => {
    if (!state.activeTask) return;

    const { session_id: sessionId, task_id: taskId } = state.activeTask;
    if (!sessionId || !taskId) {
      logger.warn('Cannot stop task due to missing identifiers', {
        activeTask: state.activeTask,
      });
      throw new Error('無法停止任務：缺少任務識別資訊');
    }

    try {
      await agentApi.tasks.stopTask(runtimeBaseUrl, sessionId, taskId);
    } catch (error) {
      logger.error('Failed to stop task', { error });
      throw error;
    }
  }, [runtimeBaseUrl, state.activeTask]);

  const handleToolDecision = useCallback(
    async (decision: ToolDecisionRequest) => {
      if (!state.currentSessionId) return;
      try {
        await agentApi.sessions.submitToolDecision(
          runtimeBaseUrl,
          state.currentSessionId,
          decision
        );
        if (decision.decision_type === 'permission') {
          store.setPendingPermission(null);
        } else if (decision.decision_type === 'user_input') {
          store.setPendingUserInput(null);
        }
      } catch (error) {
        logger.error('Failed to submit tool decision', { error });
        throw error;
      }
    },
    [runtimeBaseUrl, state.currentSessionId, store]
  );

  const selectTool = useCallback(
    (tool: AgenticTool) => {
      store.setSelectedTool(tool);
    },
    [store]
  );

  const archiveSession = useCallback(
    async (sessionId: string, reason?: string) => {
      try {
        await agentApi.sessions.archiveSession(runtimeBaseUrl, sessionId, reason);
        // Event listener 'onSessionRemoved' or similar should handle this.
        // But we can update manually to be responsive.
        store.removeSession(sessionId);
        if (state.currentSessionId === sessionId) {
          store.setCurrentSession(null);
          store.setMessages([]);
        }
      } catch (error) {
        logger.error('Failed to archive session', { error });
        throw error;
      }
    },
    [runtimeBaseUrl, state.currentSessionId, store]
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await agentApi.sessions.deleteSession(runtimeBaseUrl, sessionId);
        store.removeSession(sessionId);

        const remainingTasks = store
          .getSnapshot()
          .tasks
          .filter((task) => task.session_id !== sessionId);
        store.setTasks(remainingTasks);

        if (state.currentSessionId === sessionId) {
          clearLastActiveSession(workspaceId);
          safeSessionStorageRemove(getStreamingCacheKey(sessionId));
          safeSessionStorageRemove(getWsSeqCacheKey(sessionId));
          store.setCurrentSession(null);
          store.setCurrentTask(null);
          store.setActiveTask(null);
          store.setMessages([]);
          store.setTotalMessages(0);
          store.setHasMoreMessages(false);
          store.setLoadingMessages(false);
          store.clearQueue();
          store.endStreaming();
          store.endThinking();
          store.setPendingPermission(null);
          store.setPendingUserInput(null);
          store.clearRunningTools();
        }
      } catch (error) {
        logger.error('Failed to delete session', { error, sessionId });
        throw error;
      }
    },
    [runtimeBaseUrl, state.currentSessionId, store, workspaceId]
  );

  // Queue 操作
  const loadQueuedMessages = useCallback(async () => {
    if (!state.currentSessionId) return;
    try {
      const response = await agentApi.sessions.getQueuedMessages(
        runtimeBaseUrl,
        state.currentSessionId
      );
      store.setQueuedMessages(response.messages || []);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load queued messages';
      logger.error('Failed to load queued messages', {
        error,
        errorMessage,
        sessionId: state.currentSessionId,
        errorType: error instanceof TypeError ? 'network' :
                   error instanceof SyntaxError ? 'parse' : 'unknown'
      });
      // queued messages 是後台操作，失敗不會影響主要功能
      // 但記錄完整錯誤資訊以便診斷
      // TODO: 考慮在 UI 上顯示非侵入式的錯誤提示
    }
  }, [runtimeBaseUrl, state.currentSessionId, store]);

  const deleteQueuedMessage = useCallback(
    async (messageId: string) => {
      if (!state.currentSessionId) return;
      try {
        await agentApi.sessions.deleteQueuedMessage(
          runtimeBaseUrl,
          state.currentSessionId,
          messageId
        );
        // WebSocket event will handle store.removeFromQueue
      } catch (error) {
        logger.error('Failed to delete queued message', { error });
        throw error;
      }
    },
    [runtimeBaseUrl, state.currentSessionId]
  );

  // 切換 session 時載入 queue
  useEffect(() => {
    if (state.currentSessionId && connected) {
      loadQueuedMessages();
    }
  }, [state.currentSessionId, connected, loadQueuedMessages]);

  return {
    state,
    loadSessions,
    selectSession,
    createSession,
    archiveSession,
    deleteSession,
    loadMessages,
    loadMoreMessages,
    sendMessage,
    stopTask,
    handleToolDecision,
    selectTool,
    // Queue 操作
    loadQueuedMessages,
    deleteQueuedMessage,
  };
}
