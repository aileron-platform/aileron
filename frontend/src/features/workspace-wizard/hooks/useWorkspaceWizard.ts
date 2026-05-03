import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react';
import {
  BasicInfoForm,
  RuntimeConfigForm,
  WorkspaceWizardState,
  WizardStepKey,
  EnvVarItem,
} from '../types';
import { workspaceWizardService } from '../services/workspaceWizardService';
import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import {
  KUBERNETES_ALLOWED_NAMESPACES,
  KUBERNETES_DEFAULT_NAMESPACE,
  DEPLOYED_RUNTIME_PROVISIONER,
} from '../config/runtimeProvisioning';

const logger = createLogger('useWorkspaceWizard');

interface UseWorkspaceWizardOptions {
  onReset?: () => void;
  onCompleted?: (workspaceId: string) => void;
}

type Action =
  | { type: 'SET_STEP'; payload: WizardStepKey }
  | { type: 'SET_BASIC_INFO'; payload: BasicInfoForm }
  | { type: 'SET_RUNTIME_CONFIG'; payload: RuntimeConfigForm }
  | { type: 'SET_CREATED_WORKSPACE'; payload: string }
  | { type: 'SET_SUBMITTING'; payload: boolean }
  | { type: 'SET_POLLING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'RESET'; payload?: WorkspaceWizardState };

const initialState: WorkspaceWizardState = {
  step: 'basicInfo',
  basicInfo: {
    name: '',
    description: '',
    gitUrl: '',
    branch: '',
    cliType: 'claude-code',
  },
  runtimeConfig: {
    runtime: 'universal',
    provisioner: DEPLOYED_RUNTIME_PROVISIONER,
    targetNamespace:
      DEPLOYED_RUNTIME_PROVISIONER === 'kubernetes'
        ? KUBERNETES_DEFAULT_NAMESPACE
        : null,
    setupScript: '',
    envVars: [],
  },
  createdWorkspaceId: null,
  isSubmitting: false,
  isPolling: false,
  error: null,
};

const reducer = (state: WorkspaceWizardState, action: Action): WorkspaceWizardState => {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.payload, error: null };
    case 'SET_BASIC_INFO':
      return { ...state, basicInfo: action.payload };
    case 'SET_RUNTIME_CONFIG':
      return { ...state, runtimeConfig: action.payload };
    case 'SET_CREATED_WORKSPACE':
      return { ...state, createdWorkspaceId: action.payload };
    case 'SET_SUBMITTING':
      return { ...state, isSubmitting: action.payload };
    case 'SET_POLLING':
      return { ...state, isPolling: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'RESET':
      return action.payload ?? initialState;
    default:
      return state;
  }
};

export const useWorkspaceWizard = ({ onReset, onCompleted }: UseWorkspaceWizardOptions = {}) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const pollingRef = useRef<{ interval: NodeJS.Timeout | null; isActive: boolean }>({
    interval: null,
    isActive: false,
  });

  useEffect(() => {
    return () => {
      onReset?.();
    };
  }, [onReset]);

  const setBasicInfo = useCallback((updater: BasicInfoForm | ((prev: BasicInfoForm) => BasicInfoForm)) => {
    dispatch({
      type: 'SET_BASIC_INFO',
      payload: typeof updater === 'function' ? (updater as (prev: BasicInfoForm) => BasicInfoForm)(state.basicInfo) : updater,
    });
  }, [state.basicInfo]);

  const setRuntimeConfig = useCallback((updater: RuntimeConfigForm | ((prev: RuntimeConfigForm) => RuntimeConfigForm)) => {
    dispatch({
      type: 'SET_RUNTIME_CONFIG',
      payload: typeof updater === 'function' ? (updater as (prev: RuntimeConfigForm) => RuntimeConfigForm)(state.runtimeConfig) : updater,
    });
  }, [state.runtimeConfig]);

  const addEnvVar = useCallback(() => {
    const next: EnvVarItem = { id: crypto.randomUUID(), key: '', value: '' };
    setRuntimeConfig((prev) => ({ ...prev, envVars: [...prev.envVars, next] }));
  }, [setRuntimeConfig]);

  const updateEnvVar = useCallback((id: string, patch: Partial<EnvVarItem>) => {
    setRuntimeConfig((prev) => ({
      ...prev,
      envVars: prev.envVars.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  }, [setRuntimeConfig]);

  const removeEnvVar = useCallback((id: string) => {
    setRuntimeConfig((prev) => ({
      ...prev,
      envVars: prev.envVars.filter((item) => item.id !== id),
    }));
  }, [setRuntimeConfig]);

  const goToStep = useCallback((step: WizardStepKey) => {
    dispatch({ type: 'SET_STEP', payload: step });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' });
    onReset?.();
  }, [onReset]);

  const submitBasicInfo = useCallback(() => {
    if (!state.basicInfo.name.trim() || !state.basicInfo.description.trim()) {
      dispatch({ type: 'SET_ERROR', payload: 'validation.basicInfo' });
      return false;
    }

    // Require a branch when a Git URL is provided.
    if (state.basicInfo.gitUrl.trim() && !state.basicInfo.branch.trim()) {
      dispatch({ type: 'SET_ERROR', payload: 'validation.gitBranchRequired' });
      return false;
    }

    dispatch({ type: 'SET_ERROR', payload: null });
    goToStep('runtimeConfig');
    return true;
  }, [goToStep, state.basicInfo]);

  const submitRuntimeConfig = useCallback(async () => {
    dispatch({ type: 'SET_SUBMITTING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const payload = {
        name: state.basicInfo.name,
        description: state.basicInfo.description,
        gitUrl: state.basicInfo.gitUrl || undefined,
        branch: state.basicInfo.branch || undefined,
        runtime: state.runtimeConfig.runtime,
        targetNamespace:
          state.runtimeConfig.provisioner === 'kubernetes'
            ? state.runtimeConfig.targetNamespace || KUBERNETES_DEFAULT_NAMESPACE
            : undefined,
        setupScript: state.runtimeConfig.setupScript,
        envVars: state.runtimeConfig.envVars
          .filter((item) => item.key.trim())
          .map((item) => ({ key: item.key.trim(), value: item.value })),
        cliType: state.basicInfo.cliType,
      };

      const { workspaceId } = await workspaceWizardService.createWorkspace(payload);
      dispatch({ type: 'SET_CREATED_WORKSPACE', payload: workspaceId });
      goToStep('workspaceCreation');
    } catch (error) {
      logger.error('create workspace failed', { error });
      dispatch({ type: 'SET_ERROR', payload: 'error.createWorkspace' });
    } finally {
      dispatch({ type: 'SET_SUBMITTING', payload: false });
    }
  }, [goToStep, state.basicInfo, state.runtimeConfig]);

  useEffect(() => {
    // Start polling only when the wizard is on the creation step and has a workspace ID.
    if (state.step !== 'workspaceCreation' || !state.createdWorkspaceId) {
      // Clean up any active polling state.
      if (pollingRef.current.interval) {
        clearInterval(pollingRef.current.interval);
        pollingRef.current.interval = null;
        pollingRef.current.isActive = false;
        dispatch({ type: 'SET_POLLING', payload: false });
      }
      return;
    }

    // Avoid starting a second polling loop.
    if (pollingRef.current.isActive) {
      return;
    }

    pollingRef.current.isActive = true;
    dispatch({ type: 'SET_POLLING', payload: true });

    const checkStatus = async () => {
      try {
        const workspace = await apiClient.get(`/workspaces/${state.createdWorkspaceId}`);
        const status = (workspace as any).runtimeStatus?.status;

        if (status === 'running' || status === 'stopped') {
          // Stop polling once the workspace reaches a ready state.
          if (pollingRef.current.interval) {
            clearInterval(pollingRef.current.interval);
            pollingRef.current.interval = null;
          }
          pollingRef.current.isActive = false;
          dispatch({ type: 'SET_POLLING', payload: false });
          // Do not auto-advance; let the user move to the next step manually.
          return true;
        }
        return false;
      } catch (error) {
        logger.error('status check failed', { error });
        return false;
      }
    };

    const startPolling = async () => {
      // Check once immediately.
      if (await checkStatus()) {
        return;
      }

      // Start periodic polling.
      pollingRef.current.interval = setInterval(async () => {
        await checkStatus();
      }, 1500); // Check every 1.5 seconds.
    };

    startPolling();

    return () => {
      // Cleanup
      if (pollingRef.current.interval) {
        clearInterval(pollingRef.current.interval);
        pollingRef.current.interval = null;
      }
      pollingRef.current.isActive = false;
      dispatch({ type: 'SET_POLLING', payload: false });
    };
  }, [goToStep, state.createdWorkspaceId, state.step]);

  const completeWizard = useCallback(() => {
    if (!state.createdWorkspaceId) {
      return;
    }
    onCompleted?.(state.createdWorkspaceId);
    reset();
  }, [onCompleted, reset, state.createdWorkspaceId]);

  const runtimeHelpers = useMemo(
    () => ({
      addEnvVar,
      updateEnvVar,
      removeEnvVar,
    }),
    [addEnvVar, updateEnvVar, removeEnvVar]
  );

  return {
    state,
    setBasicInfo,
    setRuntimeConfig,
    kubernetesNamespaceOptions: KUBERNETES_ALLOWED_NAMESPACES,
    submitBasicInfo,
    submitRuntimeConfig,
    goToStep,
    reset,
    completeWizard,
    runtimeHelpers,
  };
};
