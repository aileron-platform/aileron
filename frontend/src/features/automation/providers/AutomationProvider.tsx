/**
 * AutomationProvider - Scheduler center state management
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AutomationProvider');
import {
  AutomationMetrics,
  AutomationJob,
  JobCalendarEvent,
  JobCreateInput,
  JobExecution,
  JobStatus,
  JobUpdateInput,
} from '../types';
import { automationApi } from '../services/automationApi';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { hasActiveExecutions } from '../utils/executionUtils';
import { POLLING_CONFIG } from '../constants';

// 預設 Metrics 值
const DEFAULT_METRICS: AutomationMetrics = {
  activeCount: 0,
  pausedCount: 0,
  failedCount: 0,
  draftCount: 0,
  successRate: 0,
  runningExecutions: 0,
  queuedExecutions: 0,
  averageDuration: 0,
};

// API 調用名稱（用於錯誤日誌）
const API_CALL_NAMES = ['listJobs', 'getMetrics', 'getRecentExecutions', 'getCalendarEvents'] as const;

export type AutomationView = 'tasks' | 'history';
export type AutomationFilter = 'all' | JobStatus;

interface AutomationState {
  automationJobs: AutomationJob[];
  metrics: AutomationMetrics | null;
  jobExecutions: JobExecution[];
  calendarEvents: JobCalendarEvent[];
  loading: boolean;
  view: AutomationView;
  filter: AutomationFilter;
  search: string;
  selectedTaskId: string | null;
  isCreateDialogOpen: boolean;
  creating: boolean;
  isEditDialogOpen: boolean;
  editLoading: boolean;
  editingTask: AutomationJob | null;
  editing: boolean;
}

interface AutomationContextValue {
  state: AutomationState;
  setView: (view: AutomationView) => void;
  setFilter: (filter: AutomationFilter) => void;
  setSearch: (value: string) => void;
  selectTask: (taskId: string | null) => void;
  refresh: () => Promise<void>;
  toggleTaskStatus: (taskId: string, status: JobStatus) => Promise<void>;
  openCreateDialog: () => void;
  closeCreateDialog: () => void;
  createTask: (payload: JobCreateInput) => Promise<void>;
  executeTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  openEditDialog: (taskId: string) => void;
  closeEditDialog: () => void;
  updateTask: (payload: JobUpdateInput) => Promise<void>;
}

const AutomationContext = createContext<AutomationContextValue | undefined>(undefined);

const initialState: AutomationState = {
  automationJobs: [],
  metrics: null,
  jobExecutions: [],
  calendarEvents: [],
  loading: true,
  view: 'tasks',
  filter: 'all',
  search: '',
  selectedTaskId: null,
  isCreateDialogOpen: false,
  creating: false,
  isEditDialogOpen: false,
  editLoading: false,
  editingTask: null,
  editing: false,
};

interface AutomationProviderProps {
  children: React.ReactNode;
}

export const AutomationProvider: React.FC<AutomationProviderProps> = ({ children }) => {
  const [state, setState] = useState<AutomationState>(initialState);
  const { isAuthenticated, isLoading: isInitializing } = useAuth();

  const loadData = useCallback(async () => {
    logger.debug('loadData called', { isAuthenticated, isInitializing });

    // 只在已認證時才載入數據
    if (!isAuthenticated) {
      logger.warn('Skipping data load - not authenticated');
      setState(prev => ({ ...prev, loading: false }));
      return;
    }

    logger.debug('Starting data load...');
    setState(prev => ({ ...prev, loading: true }));

    try {
      // 使用 Promise.allSettled 允許部分 API 失敗
      const results = await Promise.allSettled([
        automationApi.listJobs(),
        automationApi.getMetrics(),
        automationApi.getRecentExecutions(12),
        automationApi.getCalendarEvents(),
      ]);

      // 提取成功的結果
      const automationJobs = results[0].status === 'fulfilled' ? results[0].value : [];
      const metrics = results[1].status === 'fulfilled' ? results[1].value : DEFAULT_METRICS;
      const jobExecutions = results[2].status === 'fulfilled' ? results[2].value : [];
      const calendarEvents = results[3].status === 'fulfilled' ? results[3].value : [];

      // 記錄失敗的 API 調用
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          logger.warn(`${API_CALL_NAMES[index]} failed`, { reason: result.reason });
        }
      });

      logger.debug('Data loaded', {
        jobs: automationJobs.length,
        executions: jobExecutions.length,
        events: calendarEvents.length,
      });

      setState(prev => ({
        ...prev,
        automationJobs,
        metrics,
        jobExecutions,
        calendarEvents,
        loading: false,
      }));
    } catch (error) {
      logger.error('Failed to load data', { error });
      setState(prev => ({ ...prev, loading: false }));
      // 不要重新拋出錯誤，避免中斷應用
    }
  }, [isAuthenticated]);

  useEffect(() => {
    logger.debug('useEffect triggered', { isInitializing, isAuthenticated });

    // 等待認證初始化完成且已認證後再載入數據
    if (!isInitializing && isAuthenticated) {
      void loadData();
    }
  }, [isInitializing, isAuthenticated]);

  // 自動輪詢執行狀態（當有執行中、排隊中或等待中的任務時）
  useEffect(() => {
    // 只在已認證時才輪詢
    if (!isAuthenticated) {
      return;
    }

    // 如果沒有活躍的任務，不需要輪詢
    if (!hasActiveExecutions(state.jobExecutions)) {
      return;
    }

    // 檢查頁面可見性
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void loadData();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    // 定期輪詢（只在頁面可見時）
    const intervalId = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void loadData();
      }
    }, POLLING_CONFIG.INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [state.jobExecutions, loadData, isAuthenticated]);

  const setView = useCallback((view: AutomationView) => {
    setState(prev => ({ ...prev, view }));
  }, []);

  const setFilter = useCallback((filter: AutomationFilter) => {
    setState(prev => ({ ...prev, filter }));
  }, []);

  const setSearch = useCallback((value: string) => {
    setState(prev => ({ ...prev, search: value }));
  }, []);

  const selectTask = useCallback((taskId: string | null) => {
    setState(prev => ({ ...prev, selectedTaskId: taskId }));
  }, []);

  const refresh = useCallback(async () => {
    await loadData();
  }, [loadData]);

  const toggleTaskStatus = useCallback(async (taskId: string, status: JobStatus) => {
    const updated = await automationApi.updateJobStatus(taskId, status);
    setState(prev => ({
      ...prev,
      automationJobs: prev.automationJobs.map(task => (task.id === taskId ? updated : task)),
      selectedTaskId: prev.selectedTaskId === taskId ? updated.id : prev.selectedTaskId,
    }));
  }, []);

  const openCreateDialog = useCallback(() => {
    setState(prev => ({ ...prev, isCreateDialogOpen: true }));
  }, []);

  const closeCreateDialog = useCallback(() => {
    setState(prev => ({ ...prev, isCreateDialogOpen: false }));
  }, []);

  const createTask = useCallback(async (payload: JobCreateInput) => {
    setState(prev => ({ ...prev, creating: true }));
    try {
      await automationApi.createJob(payload);
      await loadData();
      setState(prev => ({ ...prev, creating: false, isCreateDialogOpen: false }));
    } catch (error) {
      setState(prev => ({ ...prev, creating: false }));
      throw error;
    }
  }, [loadData]);

  const deleteTask = useCallback(async (taskId: string) => {
    await automationApi.deleteJob(taskId);
    await loadData();
  }, [loadData]);

  const executeTask = useCallback(async (taskId: string) => {
    await automationApi.executeJob(taskId);
    await loadData();
  }, [loadData]);

  const openEditDialog = useCallback((taskId: string) => {
    setState(prev => ({
      ...prev,
      selectedTaskId: taskId,
      isEditDialogOpen: true,
      editLoading: true,
      editingTask: null,
    }));

    void (async () => {
      try {
        const task = await automationApi.getJob(taskId);
        setState(prev => ({
          ...prev,
          editLoading: false,
          editingTask: task,
          isEditDialogOpen: prev.isEditDialogOpen,
        }));
      } catch (error) {
        logger.error('Failed to load scheduler task', { error });
        setState(prev => ({
          ...prev,
          editLoading: false,
          isEditDialogOpen: false,
          editingTask: null,
        }));
      }
    })();
  }, []);

  const closeEditDialog = useCallback(() => {
    setState(prev => ({
      ...prev,
      isEditDialogOpen: false,
      editLoading: false,
      editingTask: null,
    }));
  }, []);

  const updateTask = useCallback(async (payload: JobUpdateInput) => {
    setState(prev => ({ ...prev, editing: true }));
    try {
      await automationApi.updateJob(payload);
      await loadData();
      setState(prev => ({
        ...prev,
        editing: false,
        isEditDialogOpen: false,
        editingTask: null,
        selectedTaskId: payload.id,
      }));
    } catch (error) {
      setState(prev => ({ ...prev, editing: false }));
      throw error;
    }
  }, [loadData]);

  const value = useMemo<AutomationContextValue>(() => ({
    state,
    setView,
    setFilter,
    setSearch,
    selectTask,
    refresh,
    toggleTaskStatus,
    openCreateDialog,
    closeCreateDialog,
    createTask,
    executeTask,
    deleteTask,
    openEditDialog,
    closeEditDialog,
    updateTask,
  }), [state, setView, setFilter, setSearch, selectTask, refresh, toggleTaskStatus, openCreateDialog, closeCreateDialog, createTask, executeTask, deleteTask, openEditDialog, closeEditDialog, updateTask]);

  return (
    <AutomationContext.Provider value={value}>
      {children}
    </AutomationContext.Provider>
  );
};

export const useAutomation = (): AutomationContextValue => {
  const context = useContext(AutomationContext);
  if (!context) {
    throw new Error('useAutomation must be used within a AutomationProvider');
  }
  return context;
};
