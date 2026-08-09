/**
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { AlertTriangle, PowerOff, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { workspaceLifecycleApi } from '../../../api/workspaceLifecycleApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { apiClient } from '@/shared/api/apiClient';
import { useWorkspaceDeletion } from '../../../hooks/useWorkspaceDeletion';
import { WorkspaceDeletionAction } from '../../../components/WorkspaceDeletionProgress';
import type {
  WorkspaceComponentStatusResponse,
  WorkspaceDetailResponse,
} from '@/features/workspace/api/workspaceApiTypes';

const logger = createLogger('WorkspaceResetSettings');

interface WorkspaceLifecycleAction {
  key: 'workspace' | 'runtime' | 'browser' | 'canvas';
  title: string;
  description: string;
  label: string;
  loadingLabel: string;
  phase?: string;
  onExecute: () => Promise<void>;
}

type LifecycleOperationPhase = 'submitted' | 'processing' | 'completed';

interface LifecycleOperationState {
  actionKey: WorkspaceLifecycleAction['key'];
  phase: LifecycleOperationPhase;
  startedAt: number;
}

export const WorkspaceResetSettings: React.FC = () => {
  const { t } = useI18n();
  const { toast } = useToast();
  const { workspaceRuntime, permissions } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId || '';

  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetailResponse | null>(null);
  const [workspaceName, setWorkspaceName] = useState('');
  const [loadingAction, setLoadingAction] = useState<WorkspaceLifecycleAction['key'] | null>(null);
  const [operationState, setOperationState] = useState<LifecycleOperationState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const deletion = useWorkspaceDeletion({
    workspaceId: workspaceId || null,
    workspaceName: workspaceName || null,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    canDelete: permissions.canDelete,
    shouldDiscoverExistingJob: false,
    isDeletionInProgress: false,
  });

  const loadWorkspace = async (targetWorkspaceId: string) => {
    const data = await apiClient.get<WorkspaceDetailResponse>(
      `/workspaces/${encodeURIComponent(targetWorkspaceId)}`
    );
    setWorkspaceDetail(data);
    setWorkspaceName(data.name ?? '');
  };

  useEffect(() => {
    let isActive = true;

    const run = async () => {
      if (!workspaceId) {
        setWorkspaceDetail(null);
        setWorkspaceName('');
        setIsLoading(false);
        return;
      }

      setIsLoading(true);

      try {
        const data = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`
        );
        if (!isActive) {
          return;
        }
        setWorkspaceDetail(data);
        setWorkspaceName(data.name ?? '');
      } catch (error) {
        if (!isActive) {
          return;
        }
        logger.error('Failed to load workspace', { error, workspaceId });
        setWorkspaceDetail(null);
        setWorkspaceName('');
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void run();

    return () => {
      isActive = false;
    };
  }, [workspaceId, t]);

  const getPhaseLabel = (phase?: string | null) => {
    if (!phase) {
      return t('workspace.workspaceSettings.reset.lifecycle.phases.unknown');
    }
    const phaseKey = phase.toLowerCase();
    const localized = t(`workspace.workspaceSettings.reset.lifecycle.phases.${phaseKey}`);
    return localized === `workspace.workspaceSettings.reset.lifecycle.phases.${phaseKey}`
      ? phase
      : localized;
  };

  const getPhaseBadgeClassName = (phase?: string | null) => {
    switch (phase?.toLowerCase()) {
      case 'running':
        return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700';
      case 'starting':
      case 'stopping':
      case 'restarting':
      case 'reconciling':
      case 'pending':
        return 'border-amber-500/20 bg-amber-500/10 text-amber-700';
      case 'failed':
      case 'error':
        return 'border-destructive/20 bg-destructive/10 text-destructive';
      case 'disabled':
      case 'stopped':
        return 'border-slate-500/20 bg-slate-500/10 text-slate-700';
      default:
        return 'border-primary/20 bg-primary/10 text-primary';
    }
  };

  const showRestartToast = useCallback((titleKey: string, descriptionKey: string) => {
    toast({
      title: t(titleKey),
      description: t(descriptionKey),
      variant: 'default',
    });
  }, [t, toast]);

  const showRestartErrorToast = useCallback((titleKey: string, fallbackKey: string, error: unknown) => {
    toast({
      title: t(titleKey),
      description: error instanceof Error ? error.message : t(fallbackKey),
      variant: 'destructive',
    });
  }, [t, toast]);

  const getOperationPhaseLabel = useCallback((phase: LifecycleOperationPhase) => {
    return t(`workspace.workspaceSettings.reset.lifecycle.operationState.${phase}`);
  }, [t]);

  const getOperationPhaseClassName = useCallback((phase: LifecycleOperationPhase) => {
    switch (phase) {
      case 'submitted':
        return 'border-primary/20 bg-primary/10 text-primary';
      case 'processing':
        return 'border-amber-500/20 bg-amber-500/10 text-amber-700';
      case 'completed':
        return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700';
      default:
        return 'border-primary/20 bg-primary/10 text-primary';
    }
  }, []);

  const getTrackedPhase = useCallback(
    (
      actionKey: WorkspaceLifecycleAction['key'],
      detail: WorkspaceDetailResponse | null,
    ): string | undefined => {
      switch (actionKey) {
        case 'workspace':
          return detail?.runtimeStatus?.status ?? detail?.overallPhase;
        case 'runtime':
          return detail?.components?.runtime?.phase;
        case 'browser':
          return detail?.components?.browser?.phase;
        case 'canvas':
          return detail?.components?.canvas?.phase;
        default:
          return undefined;
      }
    },
    [],
  );

  const isPhaseInFlight = useCallback((phase?: string | null) => {
    return ['starting', 'stopping', 'restarting', 'reconciling', 'pending'].includes(
      phase?.toLowerCase() ?? '',
    );
  }, []);

  const executeLifecycleAction = useCallback(async (
    actionKey: WorkspaceLifecycleAction['key'],
    request: () => Promise<unknown>,
    successTitleKey: string,
    successDescriptionKey: string,
    errorTitleKey: string,
    errorDescriptionKey: string,
  ) => {
    if (!workspaceId) {
      return;
    }

    setLoadingAction(actionKey);
    try {
      await request();
      showRestartToast(successTitleKey, successDescriptionKey);
      await loadWorkspace(workspaceId);
      await workspaceRuntime.reload();
      setOperationState({
        actionKey,
        phase: 'submitted',
        startedAt: Date.now(),
      });
    } catch (error) {
      logger.error('Workspace lifecycle action failed', { error, workspaceId, actionKey });
      showRestartErrorToast(errorTitleKey, errorDescriptionKey, error);
    } finally {
      setLoadingAction(null);
    }
  }, [showRestartErrorToast, showRestartToast, workspaceId, workspaceRuntime]);

  useEffect(() => {
    if (!operationState || !workspaceId) {
      return undefined;
    }

    let isCancelled = false;

    const pollStatus = async () => {
      try {
        const detail = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(workspaceId)}`,
        );
        if (isCancelled) {
          return;
        }

        setWorkspaceDetail(detail);
        setWorkspaceName(detail.name ?? '');
        await workspaceRuntime.reload();

        const trackedPhase = getTrackedPhase(operationState.actionKey, detail);
        if (isPhaseInFlight(trackedPhase)) {
          setOperationState((current) =>
            current && current.actionKey === operationState.actionKey
              ? { ...current, phase: 'processing' }
              : current,
          );
          return;
        }

        setOperationState((current) =>
          current && current.actionKey === operationState.actionKey
            ? { ...current, phase: 'completed' }
            : current,
        );
      } catch (error) {
        if (isCancelled) {
          return;
        }
        logger.error('Failed to poll workspace status', {
          error,
          workspaceId,
          actionKey: operationState.actionKey,
        });
      }
    };

    const timer = window.setInterval(() => {
      void pollStatus();
    }, 3000);

    void pollStatus();

    return () => {
      isCancelled = true;
      window.clearInterval(timer);
    };
  }, [getTrackedPhase, isPhaseInFlight, operationState, workspaceId, workspaceRuntime]);

  useEffect(() => {
    if (!operationState || operationState.phase !== 'completed') {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setOperationState((current) =>
        current?.phase === 'completed' ? null : current,
      );
    }, 4000);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [operationState]);

  const lifecycleActions = useMemo<WorkspaceLifecycleAction[]>(() => {
    const runtimePhase = workspaceDetail?.components?.runtime?.phase;
    const browserPhase = workspaceDetail?.components?.browser?.phase;
    const canvasPhase = workspaceDetail?.components?.canvas?.phase;
    const workspacePhase = workspaceDetail?.runtimeStatus?.status ?? workspaceDetail?.overallPhase;
    return [
      {
        key: 'workspace',
        title: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.title'),
        description: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.description'),
        label: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.label'),
        loadingLabel: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.loading'),
        phase: workspacePhase,
        onExecute: async () =>
          executeLifecycleAction(
            'workspace',
            () => workspaceLifecycleApi.stopWorkspace(workspaceId),
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorDescription',
          ),
      },
      {
        key: 'runtime',
        title: t('workspace.workspaceSettings.reset.lifecycle.actions.runtime.title'),
        description: t('workspace.workspaceSettings.reset.lifecycle.actions.runtime.description'),
        label: t('workspace.workspaceSettings.reset.lifecycle.actions.runtime.label'),
        loadingLabel: t('workspace.workspaceSettings.reset.lifecycle.actions.runtime.loading'),
        phase: runtimePhase,
        onExecute: async () =>
          executeLifecycleAction(
            'runtime',
            () => workspaceLifecycleApi.restartComponent(workspaceId, 'runtime'),
            'workspace.workspaceSettings.reset.lifecycle.actions.runtime.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.runtime.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.runtime.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.runtime.errorDescription',
          ),
      },
      {
        key: 'browser',
        title: t('workspace.workspaceSettings.reset.lifecycle.actions.browser.title'),
        description: t('workspace.workspaceSettings.reset.lifecycle.actions.browser.description'),
        label: t('workspace.workspaceSettings.reset.lifecycle.actions.browser.label'),
        loadingLabel: t('workspace.workspaceSettings.reset.lifecycle.actions.browser.loading'),
        phase: browserPhase,
        onExecute: async () =>
          executeLifecycleAction(
            'browser',
            () => workspaceLifecycleApi.restartComponent(workspaceId, 'browser'),
            'workspace.workspaceSettings.reset.lifecycle.actions.browser.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.browser.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.browser.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.browser.errorDescription',
          ),
      },
      {
        key: 'canvas',
        title: t('workspace.workspaceSettings.reset.lifecycle.actions.canvas.title'),
        description: t('workspace.workspaceSettings.reset.lifecycle.actions.canvas.description'),
        label: t('workspace.workspaceSettings.reset.lifecycle.actions.canvas.label'),
        loadingLabel: t('workspace.workspaceSettings.reset.lifecycle.actions.canvas.loading'),
        phase: canvasPhase,
        onExecute: async () =>
          executeLifecycleAction(
            'canvas',
            () => workspaceLifecycleApi.restartComponent(workspaceId, 'canvas'),
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.errorDescription',
          ),
      },
    ];
  }, [executeLifecycleAction, t, workspaceDetail, workspaceId]);

  if (isLoading) {
    return (
      <div className="h-full flex flex-col">
        <FeatureHeader
          title={t('workspace.workspaceSettings.reset.header.title')}
          icon={AlertTriangle}
        />
        <div className="flex-1 overflow-y-auto">
          <div className="p-6 space-y-8 bg-background">
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-muted rounded w-3/4"></div>
              <div className="h-4 bg-muted rounded w-1/2"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <FeatureHeader
        title={t('workspace.workspaceSettings.reset.header.title')}
        icon={AlertTriangle}
      />

      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-8 bg-background">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 dark:bg-red-900/20 rounded-lg">
                <AlertTriangle className="h-4 w-4 text-red-600" />
              </div>
              <h3 className="text-sm font-semibold text-foreground">
                {t('workspace.workspaceSettings.reset.danger.title')}
              </h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {t('workspace.workspaceSettings.reset.danger.description')}
            </p>
          </div>

          {permissions.canDelete ? (
          <div className="p-4 bg-card border border-border rounded-lg shadow-sm">
            <div className="space-y-4">
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-foreground">
                  {t('workspace.workspaceSettings.reset.lifecycle.title')}
                </h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {t('workspace.workspaceSettings.reset.lifecycle.description')}
                </p>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                {lifecycleActions.map((action) => (
                  <div
                    key={action.key}
                    className="space-y-3 rounded-md border border-border/60 bg-background/70 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="space-y-1">
                        <h5 className="text-sm font-medium text-foreground">{action.title}</h5>
                        <p className="text-xs text-muted-foreground">{action.description}</p>
                      </div>
                      <Badge
                        variant="outline"
                        className={`shrink-0 whitespace-nowrap text-[11px] ${getPhaseBadgeClassName(action.phase)}`}
                      >
                        {getPhaseLabel(action.phase)}
                      </Badge>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 px-3 text-xs"
                      onClick={action.onExecute}
                      disabled={
                        loadingAction !== null
                        || deletion.isDeleting
                        || (action.key === 'workspace'
                          && ['stopped', 'stopping'].includes(action.phase?.toLowerCase() ?? ''))
                      }
                    >
                      {loadingAction === action.key ? (
                        <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : action.key === 'workspace' ? (
                        <PowerOff className="mr-1.5 h-3.5 w-3.5" />
                      ) : (
                        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      {loadingAction === action.key ? action.loadingLabel : action.label}
                    </Button>
                    {operationState?.actionKey === action.key && (
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={`shrink-0 whitespace-nowrap text-[11px] ${getOperationPhaseClassName(operationState.phase)}`}
                        >
                          {getOperationPhaseLabel(operationState.phase)}
                        </Badge>
                        <p className="text-xs text-muted-foreground">
                          {t('workspace.workspaceSettings.reset.lifecycle.operationState.description', {
                            phase: getOperationPhaseLabel(operationState.phase),
                          })}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
          ) : null}

          <div className="p-4 bg-card border border-border rounded-lg shadow-sm">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Trash2 className="h-4 w-4 text-red-600" />
                <h4 className="text-sm font-semibold text-foreground">
                  {t('workspace.workspaceSettings.reset.delete.title')}
                </h4>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('workspace.workspaceSettings.reset.delete.description')}
              </p>

              <WorkspaceDeletionAction
                workspaceName={workspaceName || null}
                canDelete={permissions.canDelete}
                isDeleting={deletion.isDeleting}
                progress={deletion.progress}
                requestDelete={deletion.requestDelete}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
