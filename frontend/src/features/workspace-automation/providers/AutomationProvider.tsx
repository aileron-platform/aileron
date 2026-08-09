/**
 * AutomationProvider - Automation center state management
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
  JobCreateInput,
  JobExecution,
  JobStatus,
  JobUpdateInput,
} from '../model/automationTypes';
import { automationApi } from '../api/automationApi';
import { useAuth } from '@/features/auth/public';
import { hasActiveExecutions } from '../model/executionModel';
import { POLLING_CONFIG } from '../model/automationStatusModel';

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

const API_CALL_NAMES = ['listJobs', 'getMetrics', 'getRecentExecutions'] as const;

export type AutomationFilter = 'all' | JobStatus;

interface AutomationState {
  automationJobs: AutomationJob[];
  metrics: AutomationMetrics | null;
  jobExecutions: JobExecution[];
  filter: AutomationFilter;
  search: string;
  isCreateDialogOpen: boolean;
  creating: boolean;
  isEditDialogOpen: boolean;
  editLoading: boolean;
  editingTask: AutomationJob | null;
  editing: boolean;
}

interface AutomationContextValue {
  state: AutomationState;
  setFilter: (filter: AutomationFilter) => void;
  setSearch: (value: string) => void;
  refresh: () => Promise<void>;
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
  filter: 'all',
  search: '',
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

    if (!isAuthenticated) {
      logger.warn('Skipping data load - not authenticated');
      return;
    }

    logger.debug('Starting data load...');

    try {
      const results = await Promise.allSettled([
        automationApi.listJobs(),
        automationApi.getMetrics(),
        automationApi.getRecentExecutions(12),
      ]);

      const automationJobs = results[0].status === 'fulfilled' ? results[0].value : [];
      const metrics = results[1].status === 'fulfilled' ? results[1].value : DEFAULT_METRICS;
      const jobExecutions = results[2].status === 'fulfilled' ? results[2].value : [];
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          logger.warn(`${API_CALL_NAMES[index]} failed`, { reason: result.reason });
        }
      });

      logger.debug('Data loaded', {
        jobs: automationJobs.length,
        executions: jobExecutions.length,
      });

      setState(prev => ({
        ...prev,
        automationJobs,
        metrics,
        jobExecutions,
      }));
    } catch (error) {
      logger.error('Failed to load data', { error });
    }
  }, [isAuthenticated, isInitializing]);

  useEffect(() => {
    logger.debug('useEffect triggered', { isInitializing, isAuthenticated });

    if (!isInitializing && isAuthenticated) {
      void loadData();
    }
  }, [isInitializing, isAuthenticated, loadData]);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    if (!hasActiveExecutions(state.jobExecutions)) {
      return;
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void loadData();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

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

  const setFilter = useCallback((filter: AutomationFilter) => {
    setState(prev => ({ ...prev, filter }));
  }, []);

  const setSearch = useCallback((value: string) => {
    setState(prev => ({ ...prev, search: value }));
  }, []);

  const refresh = useCallback(async () => {
    await loadData();
  }, [loadData]);

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
        logger.error('Failed to load automation task', { error });
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
      }));
    } catch (error) {
      setState(prev => ({ ...prev, editing: false }));
      throw error;
    }
  }, [loadData]);

  const value = useMemo<AutomationContextValue>(() => ({
    state,
    setFilter,
    setSearch,
    refresh,
    openCreateDialog,
    closeCreateDialog,
    createTask,
    executeTask,
    deleteTask,
    openEditDialog,
    closeEditDialog,
    updateTask,
  }), [state, setFilter, setSearch, refresh, openCreateDialog, closeCreateDialog, createTask, executeTask, deleteTask, openEditDialog, closeEditDialog, updateTask]);

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
