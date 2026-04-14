
import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import type { AgentMessage, AgentTask } from '../../components/ChatPanel/agentSessionTypes';
import { agentApi } from '../../components/ChatPanel/agentSessionApi';
import { useRealtimeMessages } from './useRealtimeMessages';
import { useRealtimeTasks } from './useRealtimeTasks';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useRealtimeData');

export interface UseRealtimeDataOptions {
    runtimeBaseUrl: string | null;
    sessionId: string | null;
    socket?: WebSocket | null; // Pass socket if needed for connection status check, but hooks use dispatcher
}

export interface UseRealtimeDataResult {
    messages: AgentMessage[];
    tasks: AgentTask[];
    taskErrors: Map<string, string>; // taskId -> error message
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
    setMessages: (messages: AgentMessage[]) => void;
    /** 用於載入更多歷史訊息時，將舊訊息合併到現有 Map 中（使用 functional updater 確保讀取最新 state） */
    mergeMessages: (messages: AgentMessage[]) => void;
    setTasks: (tasks: AgentTask[]) => void;
    // 分頁相關
    messagesTotal: number;
    hasMoreMessages: boolean;
    loadedOffset: number;
    setLoadedOffset: (offset: number) => void;
    setHasMoreMessages: (hasMore: boolean) => void;
}

// 初始載入的訊息數量（也用於分頁載入更多）
export const MESSAGES_PER_PAGE = 15;

export function useRealtimeData({
    runtimeBaseUrl,
    sessionId,
}: UseRealtimeDataOptions): UseRealtimeDataResult {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 分頁相關 state
    const [messagesTotal, setMessagesTotal] = useState(0);
    const [hasMoreMessages, setHasMoreMessages] = useState(false);
    const [loadedOffset, setLoadedOffset] = useState(0);

    const { messagesMap, setMessages, mergeMessages } = useRealtimeMessages(sessionId);
    const { tasksMap, taskErrors, setTasks, mergeTasks } = useRealtimeTasks(sessionId);

    // 追蹤是否已經初始化過，用於區分頁面重整和切換 session
    const initializedRef = useRef(false);
    const prevSessionIdRef = useRef<string | null>(null);

    const fetchData = useCallback(async (useMerge: boolean) => {
        if (!sessionId || !runtimeBaseUrl) return;

        setLoading(true);
        setError(null);

        try {
            // 第一步：獲取訊息總數
            const countResult = await agentApi.messages.listMessages(
                runtimeBaseUrl,
                sessionId,
                { limit: 1 }
            );

            // 驗證回應
            if (typeof countResult?.total !== 'number') {
                throw new Error('Invalid API response: total is not a number');
            }
            const total = countResult.total;

            // 第二步：計算 offset 來載入最新的 N 筆訊息
            const offset = Math.max(0, total - MESSAGES_PER_PAGE);

            // Fetch messages and tasks in parallel
            const [messagesResult, tasksResult] = await Promise.all([
                agentApi.messages.listMessages(runtimeBaseUrl, sessionId, {
                    limit: MESSAGES_PER_PAGE,
                    offset
                }),
                agentApi.tasks.listTasks(runtimeBaseUrl, sessionId, { limit: 100 }),
            ]);

            // 驗證回應格式
            if (!Array.isArray(messagesResult?.items)) {
                throw new Error('Invalid API response: messages.items is not an array');
            }
            if (!Array.isArray(tasksResult?.items)) {
                throw new Error('Invalid API response: tasks.items is not an array');
            }

            // 設置分頁狀態
            setMessagesTotal(total);
            setHasMoreMessages(offset > 0);
            setLoadedOffset(offset);

            if (useMerge) {
                // 頁面重整：合併訊息，保留 WebSocket 已接收的新訊息
                mergeMessages(messagesResult.items);
                mergeTasks(tasksResult.items);
            } else {
                // 切換 session：完全替換
                setMessages(messagesResult.items);
                setTasks(tasksResult.items);
            }
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to fetch session data';
            logger.error('Failed to fetch realtime data', {
                error: err,
                sessionId,
                errorMessage,
                errorType: err instanceof TypeError ? 'network' :
                           err instanceof SyntaxError ? 'parse' : 'unknown'
            });
            setError(errorMessage);

            // 不要在所有錯誤情況下清空數據
            // 只在初次載入失敗時才清空
            if (!useMerge) {
                // 這是初次載入或切換 session，清空是合理的
                setMessagesTotal(0);
                setHasMoreMessages(false);
                setLoadedOffset(0);
                setMessages([]);
                setTasks([]);
            } else {
                // 這是頁面重整或重連失敗，保留現有數據
                // 用戶仍能看到之前的訊息，只是可能不是最新的
                logger.info('Preserving existing messages after fetch failure (merge mode)', {
                    sessionId,
                    errorPreserved: errorMessage
                });
            }
        } finally {
            setLoading(false);
        }
    }, [mergeMessages, mergeTasks, runtimeBaseUrl, sessionId, setMessages, setTasks]);

    useEffect(() => {
        // 當 sessionId 為 null 時（例如切換到新建的 workspace），
        // 清空所有資料以避免顯示舊 workspace 的內容
        if (!sessionId) {
            // 檢查是否為 session 切換（從有 session 變成無 session）
            if (initializedRef.current && prevSessionIdRef.current !== null) {
                // 這是切換到新建 workspace（沒有 session），清空資料
                logger.debug('Session cleared (switched to new workspace), clearing data');
                setMessages([]);
                setTasks([]);
                setMessagesTotal(0);
                setHasMoreMessages(false);
                setLoadedOffset(0);
            }
            prevSessionIdRef.current = null;
            return;
        }

        // 判斷是否為切換 session（而非頁面重整）
        const isSessionSwitch = initializedRef.current && prevSessionIdRef.current !== sessionId;

        if (isSessionSwitch) {
            // 切換到不同的 session：清空並重新載入
            setMessages([]);
            setTasks([]);
            fetchData(false);
        } else {
            // 初次載入或頁面重整：使用合併，保留 WebSocket 訊息
            fetchData(true);
        }

        prevSessionIdRef.current = sessionId;
        initializedRef.current = true;
    }, [fetchData, runtimeBaseUrl, sessionId, setMessages, setTasks]);

    const messages = useMemo(() => {
        return Array.from(messagesMap.values()).sort((a, b) => {
            // 首先按照 created_at 排序
            const timeDiff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
            if (timeDiff !== 0) return timeDiff;
            // 時間相同時，按照 message_id 排序以保持穩定性
            return (a.message_id || '').localeCompare(b.message_id || '');
        });
    }, [messagesMap]);

    const tasks = useMemo(() => {
        return Array.from(tasksMap.values()).sort((a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
    }, [tasksMap]);

    // refresh 使用 merge，保留 WebSocket 訊息
    const refresh = useCallback(async () => {
        await fetchData(true);
    }, [fetchData]);

    return {
        messages,
        tasks,
        taskErrors,
        loading,
        error,
        refresh,
        setMessages,
        mergeMessages,  // 用於載入更多訊息時合併（使用 functional updater 確保讀取最新 state）
        setTasks,
        // 分頁相關
        messagesTotal,
        hasMoreMessages,
        loadedOffset,
        setLoadedOffset,
        setHasMoreMessages,
    };
}
