/**
 * useTaskProgress - 任務進度輪詢 Hook
 * 
 * 統一管理異步任務的進度查詢邏輯，避免代碼重複
 */

import { useEffect, useState, useCallback } from 'react';

export interface TaskProgress {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: TaskResult | null;
}

export interface TaskResult {
  message?: string;
  synced_count?: number;
}

interface UseTaskProgressOptions {
  pollInterval?: number;
  onComplete?: (result: TaskProgress) => void;
  onError?: (error: Error) => void;
}

const DEFAULT_POLL_INTERVAL = 1000; // 1 second

/**
 * 輪詢任務進度
 * 
 * @param taskId - 任務 ID
 * @param getProgress - 獲取進度的異步函數
 * @param options - 配置選項
 * @returns 進度狀態和控制函數
 */
export const useTaskProgress = (
  initialTaskId: string | null,
  getProgress: (id: string) => Promise<{ success: boolean; data?: TaskProgress }>,
  options: UseTaskProgressOptions = {}
) => {
  const {
    pollInterval = DEFAULT_POLL_INTERVAL,
    onComplete,
    onError
  } = options;

  const [taskId, setTaskId] = useState<string | null>(initialTaskId);
  const [progress, setProgress] = useState<TaskProgress | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  // 停止輪詢
  const stopPolling = useCallback(() => {
    setIsPolling(false);
  }, []);

  // 開始輪詢（可選傳入新的 taskId）
  const startPolling = useCallback((newTaskId?: string) => {
    if (newTaskId) {
      setTaskId(newTaskId);
      setIsPolling(true);
    } else if (taskId) {
      setIsPolling(true);
    }
  }, [taskId]);

  // 重置進度
  const resetProgress = useCallback(() => {
    setProgress(null);
    setIsPolling(false);
    setTaskId(null);
  }, []);

  // 輪詢邏輯
  useEffect(() => {
    if (!isPolling || !taskId) return;

    const pollInterval_id = setInterval(async () => {
      try {
        const response = await getProgress(taskId);
        if (response.success && response.data) {
          setProgress(response.data);

          // 如果任務完成或失敗，停止輪詢
          if (
            response.data.status === 'completed' ||
            response.data.status === 'failed' ||
            response.data.status === 'cancelled'
          ) {
            setIsPolling(false);
            onComplete?.(response.data);
          }
        }
      } catch (error) {
        const err = error instanceof Error ? error : new Error('Unknown error');
        onError?.(err);
      }
    }, pollInterval);

    return () => clearInterval(pollInterval_id);
  }, [isPolling, taskId, getProgress, pollInterval, onComplete, onError]);

  return {
    taskId,
    setTaskId,
    progress,
    setProgress,
    isPolling,
    setIsPolling,
    startPolling,
    stopPolling,
    resetProgress,
  };
};

export default useTaskProgress;

