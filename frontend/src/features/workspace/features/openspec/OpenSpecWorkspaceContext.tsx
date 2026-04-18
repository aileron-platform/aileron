import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useWorkspace } from '../../providers/WorkspaceProvider';
import {
  openSpecApi,
  type OpenSpecActionItem,
  type OpenSpecCustomizationDebugResult,
  type OpenSpecCustomizationState,
  type OpenSpecCustomizationValidationResult,
  type OpenSpecNavigationChange,
  type OpenSpecWorkspaceState,
} from '../../components/ChatPanel/openSpecApi';
import { getEventDispatcher } from '../../components/ChatPanel/agentSessionEvents';

const logger = createLogger('OpenSpecWorkspaceContext');
const AUTO_REFRESH_DEBOUNCE_MS = 400;
const AUTO_REFRESH_FOLLOW_UP_MS = 1500;

interface OpenSpecWorkspaceContextValue {
  state: OpenSpecWorkspaceState | null;
  actions: OpenSpecActionItem[];
  changes: OpenSpecNavigationChange[];
  customization: OpenSpecCustomizationState | null;
  customizationValidation: OpenSpecCustomizationValidationResult | null;
  customizationDebug: OpenSpecCustomizationDebugResult | null;
  recommendedActions: OpenSpecActionItem[];
  isLoading: boolean;
  isCustomizationLoading: boolean;
  focusChangeName: string | null;
  refresh: (options?: { reloadActiveDocument?: boolean }) => Promise<void>;
  refreshCustomization: () => Promise<void>;
  runCustomizationValidate: (path?: string | null) => Promise<OpenSpecCustomizationValidationResult | null>;
  runCustomizationDebug: (path?: string | null) => Promise<OpenSpecCustomizationDebugResult | null>;
  customizationDialog: 'validation' | 'debug' | null;
  openCustomizationValidationDialog: (path?: string | null) => Promise<void>;
  openCustomizationDebugDialog: (path?: string | null) => Promise<void>;
  closeCustomizationDialog: () => void;
  setCustomizationValidation: React.Dispatch<React.SetStateAction<OpenSpecCustomizationValidationResult | null>>;
  setCustomizationDebug: React.Dispatch<React.SetStateAction<OpenSpecCustomizationDebugResult | null>>;
}

const OpenSpecWorkspaceContext = createContext<OpenSpecWorkspaceContextValue | null>(null);

const deriveFocusChangeName = (selectedPath: string | null): string | null => {
  if (!selectedPath?.startsWith('/openspec/changes/')) {
    return null;
  }

  const segments = selectedPath.split('/').filter(Boolean);
  return segments[2] || null;
};

export const OpenSpecWorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { workspaceRuntime, state: workspaceState, fileEditor } = useWorkspace();
  const { isAuthenticated, isLoading: isAuthLoading, getAccessToken } = useAuth();
  const [state, setState] = useState<OpenSpecWorkspaceState | null>(null);
  const [actions, setActions] = useState<OpenSpecActionItem[]>([]);
  const [changes, setChanges] = useState<OpenSpecNavigationChange[]>([]);
  const [customization, setCustomization] = useState<OpenSpecCustomizationState | null>(null);
  const [customizationValidation, setCustomizationValidation] = useState<OpenSpecCustomizationValidationResult | null>(null);
  const [customizationDebug, setCustomizationDebug] = useState<OpenSpecCustomizationDebugResult | null>(null);
  const [customizationDialog, setCustomizationDialog] = useState<'validation' | 'debug' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCustomizationLoading, setIsCustomizationLoading] = useState(false);
  const inFlightRefreshRef = useRef<Promise<void> | null>(null);
  const autoRefreshTimerRef = useRef<number | null>(null);
  const autoRefreshFollowUpTimerRef = useRef<number | null>(null);
  const openSpecTabStateRef = useRef(workspaceState.openspec);
  const reloadCurrentFileRef = useRef(fileEditor.reloadCurrentFile);
  const actionContextRef = useRef({
    subview: workspaceState.openspec.subView,
    focusedChangeName: deriveFocusChangeName(workspaceState.openspec.selectedPath),
  });
  const accessToken = getAccessToken();
  const isAuthReady = !isAuthLoading && isAuthenticated && Boolean(accessToken);

  useEffect(() => {
    openSpecTabStateRef.current = workspaceState.openspec;
  }, [workspaceState.openspec]);

  useEffect(() => {
    actionContextRef.current = {
      subview: workspaceState.openspec.subView,
      focusedChangeName: deriveFocusChangeName(workspaceState.openspec.selectedPath),
    };
  }, [workspaceState.openspec.selectedPath, workspaceState.openspec.subView]);

  useEffect(() => {
    reloadCurrentFileRef.current = fileEditor.reloadCurrentFile;
  }, [fileEditor.reloadCurrentFile]);

  const refresh = useCallback(async (options?: { reloadActiveDocument?: boolean }) => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setState(null);
      setActions([]);
      setChanges([]);
      setIsLoading(false);
      return;
    }

    if (!isAuthReady) {
      setIsLoading(false);
      return;
    }

    if (inFlightRefreshRef.current) {
      await inFlightRefreshRef.current;
      return;
    }

    const refreshPromise = (async () => {
      setIsLoading(true);
      try {
        const result = await openSpecApi.getWorkspaceState(
          workspaceRuntime.runtimeBaseUrl,
          workspaceRuntime.workspaceId,
          actionContextRef.current,
        );
        const nextActions = Array.isArray(result.actions) ? result.actions : [];
        const nextChanges = Array.isArray(result.changes) ? result.changes : [];
        setState(result.state);
        setActions(nextActions);
        setChanges(nextChanges);

        if (options?.reloadActiveDocument !== false) {
          const currentOpenSpecState = openSpecTabStateRef.current;
          const activeOpenSpecTab = currentOpenSpecState.openTabs.find(
            (tab) => tab.id === currentOpenSpecState.activeTabId,
          );
          const activePath = activeOpenSpecTab?.path ?? currentOpenSpecState.activeTabId ?? null;
          const isDirty = activePath ? currentOpenSpecState.modifiedTabs.includes(activePath) : false;
          const knownDocumentPaths = new Set(
            nextChanges.flatMap((change) => [
              change.proposalPath,
              change.designPath,
              change.tasksPath,
              ...change.specs.map((spec) => spec.path),
            ].filter((path): path is string => Boolean(path))),
          );
          if (
            activePath?.startsWith('/openspec/')
            && !isDirty
            && knownDocumentPaths.has(activePath)
          ) {
            await reloadCurrentFileRef.current('openspec');
          }
        }
      } catch (error) {
        logger.error('Failed to load OpenSpec workspace state', { error });
        setState(null);
        setActions([]);
        setChanges([]);
      } finally {
        setIsLoading(false);
        inFlightRefreshRef.current = null;
      }
    })();

    inFlightRefreshRef.current = refreshPromise;
    await refreshPromise;
  }, [isAuthReady, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const refreshCustomization = useCallback(async () => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      setCustomization(null);
      setIsCustomizationLoading(false);
      return;
    }

    if (!isAuthReady) {
      setIsCustomizationLoading(false);
      return;
    }

    setIsCustomizationLoading(true);
    try {
      const result = await openSpecApi.getCustomizationState(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
      );
      setCustomization(result);
    } catch (error) {
      logger.error('Failed to load OpenSpec customization state', { error });
      setCustomization(null);
    } finally {
      setIsCustomizationLoading(false);
    }
  }, [isAuthReady, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const runCustomizationValidate = useCallback(async (path?: string | null) => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      return null;
    }
    const targetPath = path ?? openSpecTabStateRef.current.selectedPath;
    if (!targetPath) {
      return null;
    }
    try {
      const result = await openSpecApi.validateCustomization(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        targetPath,
      );
      setCustomizationValidation(result);
      return result;
    } catch (error) {
      logger.error('Failed to validate OpenSpec customization', { error, targetPath });
      setCustomizationValidation(null);
      return null;
    }
  }, [workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const runCustomizationDebug = useCallback(async (path?: string | null) => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl) {
      return null;
    }
    const targetPath = path ?? openSpecTabStateRef.current.selectedPath;
    if (!targetPath) {
      return null;
    }
    try {
      const result = await openSpecApi.debugCustomization(
        workspaceRuntime.runtimeBaseUrl,
        workspaceRuntime.workspaceId,
        targetPath,
      );
      setCustomizationDebug(result);
      return result;
    } catch (error) {
      logger.error('Failed to debug OpenSpec customization', { error, targetPath });
      setCustomizationDebug(null);
      return null;
    }
  }, [workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const openCustomizationValidationDialog = useCallback(async (path?: string | null) => {
    const result = await runCustomizationValidate(path);
    if (result) {
      setCustomizationDialog('validation');
    }
  }, [runCustomizationValidate]);

  const openCustomizationDebugDialog = useCallback(async (path?: string | null) => {
    const result = await runCustomizationDebug(path);
    if (result) {
      setCustomizationDialog('debug');
    }
  }, [runCustomizationDebug]);

  const closeCustomizationDialog = useCallback(() => {
    setCustomizationDialog(null);
  }, []);

  useEffect(() => {
    void refresh();
  }, [isAuthReady, refresh, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  useEffect(() => {
    if (workspaceState.openspec.subView !== 'customization') {
      return;
    }
    void refreshCustomization();
  }, [refreshCustomization, workspaceState.openspec.subView]);

  useEffect(() => {
    return () => {
      if (autoRefreshTimerRef.current !== null) {
        window.clearTimeout(autoRefreshTimerRef.current);
      }
      if (autoRefreshFollowUpTimerRef.current !== null) {
        window.clearTimeout(autoRefreshFollowUpTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!workspaceRuntime.workspaceId || !workspaceRuntime.runtimeBaseUrl || !isAuthReady) {
      return;
    }

    const dispatcher = getEventDispatcher();
    const scheduleAutoRefresh = () => {
      if (autoRefreshTimerRef.current !== null) {
        window.clearTimeout(autoRefreshTimerRef.current);
      }
      if (autoRefreshFollowUpTimerRef.current !== null) {
        window.clearTimeout(autoRefreshFollowUpTimerRef.current);
      }

      autoRefreshTimerRef.current = window.setTimeout(() => {
        void refresh({ reloadActiveDocument: true });
      }, AUTO_REFRESH_DEBOUNCE_MS);

      autoRefreshFollowUpTimerRef.current = window.setTimeout(() => {
        void refresh({ reloadActiveDocument: true });
      }, AUTO_REFRESH_FOLLOW_UP_MS);
    };

    const unsubscribe = dispatcher.subscribe({
      onTaskCompleted: scheduleAutoRefresh,
      onTaskFailed: scheduleAutoRefresh,
      onTaskStopped: scheduleAutoRefresh,
    });

    return () => {
      unsubscribe();
      if (autoRefreshTimerRef.current !== null) {
        window.clearTimeout(autoRefreshTimerRef.current);
        autoRefreshTimerRef.current = null;
      }
      if (autoRefreshFollowUpTimerRef.current !== null) {
        window.clearTimeout(autoRefreshFollowUpTimerRef.current);
        autoRefreshFollowUpTimerRef.current = null;
      }
    };
  }, [isAuthReady, refresh, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const focusChangeName = useMemo(
    () => deriveFocusChangeName(workspaceState.openspec.selectedPath),
    [workspaceState.openspec.selectedPath],
  );

  const recommendedActions = useMemo(() => {
    const visibleActions = actions.filter((action) => action.availability !== 'hidden');
    const preferred = visibleActions.filter((action) => action.recommended);
    return (preferred.length > 0 ? preferred : visibleActions)
      .filter((action) => action.availability === 'enabled')
      .slice(0, 3);
  }, [actions]);

  const value = useMemo<OpenSpecWorkspaceContextValue>(() => ({
    state,
    actions,
    changes,
    customization,
    customizationValidation,
    customizationDebug,
    customizationDialog,
    recommendedActions,
    isLoading,
    isCustomizationLoading,
    focusChangeName,
    refresh,
    refreshCustomization,
    runCustomizationValidate,
    runCustomizationDebug,
    openCustomizationValidationDialog,
    openCustomizationDebugDialog,
    closeCustomizationDialog,
    setCustomizationValidation,
    setCustomizationDebug,
  }), [
    actions,
    changes,
    customization,
    customizationDialog,
    customizationDebug,
    customizationValidation,
    closeCustomizationDialog,
    focusChangeName,
    isCustomizationLoading,
    isLoading,
    openCustomizationDebugDialog,
    openCustomizationValidationDialog,
    recommendedActions,
    refresh,
    refreshCustomization,
    runCustomizationDebug,
    runCustomizationValidate,
    state,
  ]);

  return (
    <OpenSpecWorkspaceContext.Provider value={value}>
      {children}
    </OpenSpecWorkspaceContext.Provider>
  );
};

export const useOpenSpecWorkspace = (): OpenSpecWorkspaceContextValue => {
  const context = useContext(OpenSpecWorkspaceContext);
  if (!context) {
    throw new Error('useOpenSpecWorkspace 必須在 OpenSpecWorkspaceProvider 內使用');
  }
  return context;
};
