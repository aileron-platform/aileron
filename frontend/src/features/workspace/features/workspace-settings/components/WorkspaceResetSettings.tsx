/**
 * WorkspaceResetSettings - 工作區生命週期與刪除操作
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { AlertTriangle, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { workspaceLifecycleApi } from '../../../services/workspaceLifecycleApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { apiClient } from '@/shared/api/apiClient';
import { useWorkspaceDeleteFallback } from '../../../hooks/useWorkspaceDeleteFallback';
import type {
  WorkspaceComponentStatusResponse,
  WorkspaceDetailResponse,
} from '@/features/workspace/providers/workspaceState.types';

const logger = createLogger('WorkspaceResetSettings');

interface WorkspaceLifecycleAction {
  key: 'runtime' | 'browser' | 'canvas' | 'workspace';
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
  const { workspaceRuntime } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId || '';
  const resolveDeleteFallback = useWorkspaceDeleteFallback();

  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetailResponse | null>(null);
  const [workspaceName, setWorkspaceName] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [loadingAction, setLoadingAction] = useState<WorkspaceLifecycleAction['key'] | null>(null);
  const [operationState, setOperationState] = useState<LifecycleOperationState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
        logger.error('載入 workspace 失敗', { error, workspaceId });
        setWorkspaceDetail(null);
        setWorkspaceName(t('workspace.workspaceSettings.reset.delete.unknownWorkspaceName'));
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
        case 'runtime':
          return detail?.components?.runtime?.phase;
        case 'browser':
          return detail?.components?.browser?.phase;
        case 'canvas':
          return detail?.components?.canvas?.phase;
        case 'workspace':
          return detail?.overallPhase;
        default:
          return undefined;
      }
    },
    [],
  );

  const isPhaseInFlight = useCallback((phase?: string | null) => {
    return ['starting', 'restarting', 'reconciling', 'pending'].includes(
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
      logger.error('生命週期操作失敗', { error, workspaceId, actionKey });
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
        logger.error('輪詢 workspace 狀態失敗', {
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
    const overallPhase = workspaceDetail?.overallPhase;

    return [
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
            () => workspaceLifecycleApi.restartRuntime(workspaceId),
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
            () => workspaceLifecycleApi.restartBrowserContainer(workspaceId),
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
            () => workspaceLifecycleApi.restartCanvasContainer(workspaceId),
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.canvas.errorDescription',
          ),
      },
      {
        key: 'workspace',
        title: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.title'),
        description: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.description'),
        label: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.label'),
        loadingLabel: t('workspace.workspaceSettings.reset.lifecycle.actions.workspace.loading'),
        phase: overallPhase,
        onExecute: async () =>
          executeLifecycleAction(
            'workspace',
            () => workspaceLifecycleApi.restartWorkspace(workspaceId),
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successDescription',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorTitle',
            'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorDescription',
          ),
      },
    ];
  }, [executeLifecycleAction, t, workspaceDetail, workspaceId]);

  const handleDelete = async () => {
    if (confirmText !== workspaceName) {
      return;
    }

    setIsDeleting(true);
    try {
      await workspaceLifecycleApi.deleteWorkspace(workspaceId);
      await resolveDeleteFallback({
        deletedWorkspaceId: workspaceId,
        deletedRuntimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
      });
      toast({
        title: t('workspace.workspaceSettings.reset.delete.success.title'),
        description: t('workspace.workspaceSettings.reset.delete.success.description'),
        variant: 'default',
      });
    } catch (error) {
      logger.error('刪除工作區失敗', { error, workspaceId });
      toast({
        title: t('workspace.workspaceSettings.reset.delete.error.title'),
        description: error instanceof Error ? error.message : t('workspace.workspaceSettings.reset.delete.error.description'),
        variant: 'destructive',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const isConfirmValid = confirmText === workspaceName;

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
                      disabled={loadingAction !== null}
                    >
                      {loadingAction === action.key ? (
                        <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
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

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" className="h-7 px-2 text-xs bg-red-600 hover:bg-red-700 text-white">
                    <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                    {t('workspace.workspaceSettings.reset.delete.trigger')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5 text-destructive" />
                      {t('workspace.workspaceSettings.reset.delete.dialog.title', { workspaceName })}
                    </AlertDialogTitle>
                    <AlertDialogDescription className="space-y-3">
                      <p>
                        {t('workspace.workspaceSettings.reset.delete.dialog.intro', { workspaceName })}
                      </p>
                      <p>
                        {t('workspace.workspaceSettings.reset.delete.dialog.impactTitle')}
                      </p>
                      <ul className="list-disc list-inside space-y-1 text-sm">
                        <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.settings')}</li>
                        <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.projects')}</li>
                        <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.variables')}</li>
                        <li>{t('workspace.workspaceSettings.reset.delete.dialog.impactItems.history')}</li>
                      </ul>
                      <p className="font-medium text-destructive">
                        {t('workspace.workspaceSettings.reset.delete.dialog.warning')}
                      </p>
                    </AlertDialogDescription>
                  </AlertDialogHeader>

                  <div className="space-y-2">
                    <Label htmlFor="confirm-text" className="text-sm">
                      {t('workspace.workspaceSettings.reset.delete.dialog.confirmLabel.prefix')}{' '}
                      <code className="bg-muted px-1 py-0.5 rounded text-xs">{workspaceName}</code>{' '}
                      {t('workspace.workspaceSettings.reset.delete.dialog.confirmLabel.suffix')}
                    </Label>
                    <Input
                      id="confirm-text"
                      value={confirmText}
                      onChange={(e) => setConfirmText(e.target.value)}
                      placeholder={workspaceName}
                      className="h-9 text-sm"
                    />
                  </div>

                  <AlertDialogFooter>
                    <AlertDialogCancel
                      onClick={() => setConfirmText('')}
                      className="h-7 px-2 text-xs border-border text-muted-foreground hover:bg-muted"
                    >
                      {t('workspace.workspaceSettings.reset.delete.dialog.cancel')}
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDelete}
                      disabled={!isConfirmValid || isDeleting}
                      className="h-7 px-2 text-xs bg-red-600 hover:bg-red-700 text-white"
                    >
                      {isDeleting
                        ? t('workspace.workspaceSettings.reset.delete.dialog.confirming')
                        : t('workspace.workspaceSettings.reset.delete.dialog.confirm')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
