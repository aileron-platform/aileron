
import { useState, useEffect, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useRealtimeTasks');
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';
import type { AgentTask } from '../../components/ChatPanel/agentSessionTypes';

const TERMINAL_TASK_STATUSES = new Set(['completed', 'failed', 'stopped']);

export function useRealtimeTasks(sessionId: string | null) {
    const [tasksMap, setTasksMap] = useState<Map<string, AgentTask>>(new Map());
    // 追蹤任務失敗的錯誤訊息，用於 UI 顯示
    const [taskErrors, setTaskErrors] = useState<Map<string, string>>(new Map());

    const handleTaskCreated = useCallback((task: AgentTask) => {
        if (sessionId && task.session_id !== sessionId) return;

        setTasksMap(prev => {
            const next = new Map(prev);
            next.set(task.task_id, task);
            return next;
        });
        // 清除該任務的錯誤（新任務開始時）
        setTaskErrors(prev => {
            const next = new Map(prev);
            next.delete(task.task_id);
            return next;
        });
    }, [sessionId]);

    const handleTaskPatched = useCallback((task: Partial<AgentTask> & { task_id: string }) => {
        logger.debug('Task patched event received', { task });
        setTasksMap(prev => {
            const next = new Map(prev);
            const existing = next.get(task.task_id);
            if (existing) {
                if (sessionId && existing.session_id !== sessionId) return prev;

                const updated = { ...existing, ...task };
                logger.debug('Updating existing task', { taskId: updated.task_id, status: updated.status });
                next.set(task.task_id, updated);

                // 如果任務狀態變為 failed，清除錯誤（因為可能已經在 onTaskFailed 中處理過了）
                if (updated.status === 'failed' && !task.error_message) {
                    setTaskErrors(prev => {
                        const next = new Map(prev);
                        next.delete(task.task_id);
                        return next;
                    });
                }
            } else {
                // Task 不在 map 中，可能是初始載入時尚未收到 task_created 事件
                // 在此情況下，我們仍然應該更新 map（假設至少有 session_id）
                logger.debug('Task not in map, adding from patch event', { taskId: task.task_id, status: task.status });
                // 只有當 task 有足夠的資訊時才添加（至少需要 task_id 和 session_id）
                if (task.task_id && task.session_id) {
                    if (sessionId && task.session_id !== sessionId) return prev;
                    next.set(task.task_id, task as AgentTask);

                    // 檢查是否為失敗的任務（載入時已有錯誤）
                    if (task.status === 'failed' && task.error_message) {
                        setTaskErrors(prev => {
                            const next = new Map(prev);
                            next.set(task.task_id, task.error_message);
                            return next;
                        });
                    }
                }
            }
            return next;
        });
    }, [sessionId]);

    const handleTaskRemoved = useCallback((taskId: string) => {
        setTasksMap(prev => {
            const next = new Map(prev);
            next.delete(taskId);
            return next;
        });
        // 同時清除錯誤
        setTaskErrors(prev => {
            const next = new Map(prev);
            next.delete(taskId);
            return next;
        });
    }, []);

    // 處理任務失敗事件
    const handleTaskFailed = useCallback((eventSessionId: string, taskId: string, errorMsg?: string) => {
        if (sessionId && eventSessionId !== sessionId) {
            return;
        }
        if (!errorMsg) {
            logger.warn('Task failed without error message', { taskId, sessionId });
        } else {
            logger.warn('Task failed', { taskId, sessionId, errorMsg });
        }
        // 即使沒有錯誤訊息，也設置一個通用錯誤
        setTaskErrors(prev => {
            const next = new Map(prev);
            next.set(taskId, errorMsg || 'Task failed unexpectedly');
            return next;
        });
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId) return;

        const dispatcher = getEventDispatcher();
        const unsubscribe = dispatcher.subscribe({
            onTaskCreated: handleTaskCreated,
            onTaskPatched: handleTaskPatched,
            onTaskRemoved: handleTaskRemoved,
            onTaskFailed: handleTaskFailed,
        });

        return () => {
            unsubscribe();
        };
    }, [sessionId, handleTaskCreated, handleTaskPatched, handleTaskRemoved, handleTaskFailed]);

    // 完全替換 tasks（用於切換 session）
    const setTasks = useCallback((newTasks: AgentTask[]) => {
        const map = new Map<string, AgentTask>();
        newTasks.forEach(task => map.set(task.task_id, task));
        setTasksMap(map);
    }, []);

    // 合併 tasks（用於頁面重整，保留 WebSocket 已接收的新 tasks）
    const mergeTasks = useCallback((newTasks: AgentTask[]) => {
        setTasksMap(prev => {
            const next = new Map(prev);
            newTasks.forEach(task => {
                const existing = next.get(task.task_id);
                if (!existing) {
                    next.set(task.task_id, task);
                } else {
                    const existingTime = new Date(existing.updated_at || existing.created_at).getTime();
                    const newTime = new Date(task.updated_at || task.created_at).getTime();
                    const statusChanged = existing.status !== task.status;
                    const incomingIsTerminal = TERMINAL_TASK_STATUSES.has(task.status);
                    const existingIsTerminal = TERMINAL_TASK_STATUSES.has(existing.status);

                    // 既有終態不可被同 task 的非終態覆蓋，避免 completed/failed/stopped 回退為 running。
                    if (existingIsTerminal && !incomingIsTerminal) {
                        return;
                    }

                    // 同一 task 在未提供可靠 updated_at 時，通常會落在相同 created_at。
                    // 此時只允許：
                    // 1) 非終態 -> 終態（收斂）
                    // 2) 非終態之間的狀態更新
                    // 並保留「終態不可回退」規則。
                    if (
                        newTime > existingTime ||
                        (newTime === existingTime && statusChanged && !existingIsTerminal)
                    ) {
                        next.set(task.task_id, task);
                    }
                }
            });
            return next;
        });
    }, []);

    return {
        tasksMap,
        taskErrors,
        setTasks,
        mergeTasks,
    };
}
