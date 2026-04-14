import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('SettingsSyncStep');
import {
  ArrowLeft,
  CheckCircle,
  Loader2,
  Settings,
  Key,
  GitBranch,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { useToast } from '@/shared/components/ui/use-toast';
import { useApp } from '@/app/providers/AppProvider';
import {
  WorkspaceSetupService,
  type WorkspaceSetupStatus,
  type WorkspaceSetupTaskState,
  type WorkspaceSetupTaskStatus,
} from '@/shared/services/workspaceSetupService';
import { apiClient } from '@/shared/api/apiClient';

const TASK_ITEMS = [
  { key: 'ssh', label: 'SSH Keys', icon: Key },
  { key: 'git', label: 'Git', icon: GitBranch },
] as const;

const TASK_KEYS = TASK_ITEMS.map(item => item.key);

type TaskKey = (typeof TASK_ITEMS)[number]['key'];
type OverallStatus = 'idle' | 'running' | 'success' | 'partial' | 'failed';

type NormalizedTaskMap = Record<TaskKey, WorkspaceSetupTaskStatus>;

const deriveOverallStatus = (tasks: WorkspaceSetupTaskStatus[]): OverallStatus => {
  if (!tasks.length) {
    return 'idle';
  }

  const statuses = tasks.map(task => task.status);
  if (statuses.every(status => status === 'success' || status === 'skipped')) {
    return 'success';
  }

  if (statuses.some(status => status === 'failed')) {
    return statuses.some(status => status === 'success' || status === 'skipped') ? 'partial' : 'failed';
  }

  if (statuses.some(status => status === 'running' || status === 'pending')) {
    return 'running';
  }

  return 'idle';
};

const createPlaceholderStatus = (
  workspaceId: string,
  status: WorkspaceSetupTaskState,
  message: string,
): WorkspaceSetupStatus => ({
  workspaceId,
  completed: status === 'success' || status === 'skipped',
  tasks: TASK_ITEMS.map(item => ({
    taskKey: item.key,
    taskName: item.label,
    status,
    message,
  })),
});

const normalizeStatus = (
  workspaceId: string,
  status: WorkspaceSetupStatus | null,
): WorkspaceSetupStatus => {
  const base = status ?? { workspaceId, completed: false, tasks: [] };
  const taskMap: NormalizedTaskMap = TASK_KEYS.reduce((acc, key) => {
    acc[key] = {
      taskKey: key,
      taskName: TASK_ITEMS.find(item => item.key === key)?.label ?? key,
      status: 'pending',
      message: '等待同步結果',
    };
    return acc;
  }, {} as NormalizedTaskMap);

  for (const task of base.tasks) {
    const key = task.taskKey as TaskKey;
    if (TASK_KEYS.includes(key)) {
      taskMap[key] = {
        taskKey: key,
        taskName: TASK_ITEMS.find(item => item.key === key)?.label ?? task.taskName,
        status: task.status,
        message: task.message,
      };
    }
  }

  return {
    workspaceId: base.workspaceId || workspaceId,
    completed: base.completed,
    tasks: TASK_KEYS.map(key => taskMap[key]),
  };
};

const hasPendingTasks = (tasks: WorkspaceSetupTaskStatus[]): boolean =>
  tasks.some(task => task.status === 'pending' || task.status === 'running');

interface UserSettings {
  ssh?: {
    privateKey?: string;
    publicKey?: string;
  };
  git?: {
    userName?: string;
    userEmail?: string;
  };
}

interface SettingsSyncStepProps {
  workspaceId: string;
  onPrevious: () => void;
  onComplete: () => void;
  isSubmitting: boolean;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const SettingsSyncStep: React.FC<SettingsSyncStepProps> = ({
  workspaceId,
  onPrevious,
  onComplete,
  isSubmitting,
  t,
}) => {
  const { toast } = useToast();
  const { state: appState } = useApp();
  const user = appState.user;
  const [loading, setLoading] = useState(true);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [setupStatus, setSetupStatus] = useState<WorkspaceSetupStatus | null>(null);
  const [overallStatus, setOverallStatus] = useState<OverallStatus>('idle');
  const [isPolling, setIsPolling] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const hasTriggeredSyncRef = useRef(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const announcedStatusRef = useRef<OverallStatus>('idle');

  const hasAnySettings = useMemo(
    () =>
      Boolean(
        userSettings?.ssh?.privateKey ||
          userSettings?.git?.userName,
      ),
    [userSettings?.git?.userName, userSettings?.ssh?.privateKey],
  );

  const announceStatus = useCallback(
    (status: OverallStatus, message?: string) => {
      if (announcedStatusRef.current === status) {
        return;
      }

      if (status === 'success') {
        toast({
          title: t('workspace.wizard.steps.settingsSync.notifications.successTitle'),
          description: t('workspace.wizard.steps.settingsSync.notifications.successDescription'),
        });
      } else if (status === 'partial') {
        toast({
          title: t('workspace.wizard.steps.settingsSync.notifications.partialTitle'),
          description: message || t('workspace.wizard.steps.settingsSync.notifications.partialDescription'),
        });
      } else if (status === 'failed') {
        toast({
          title: t('workspace.wizard.steps.settingsSync.notifications.failedTitle'),
          description: message || t('workspace.wizard.steps.settingsSync.notifications.failedDescription'),
          variant: 'destructive',
        });
      }

      announcedStatusRef.current = status;
    },
    [toast],
  );

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const status = await WorkspaceSetupService.getStatus(workspaceId);
      const normalized = normalizeStatus(workspaceId, status);
      setSetupStatus(normalized);

      const derived = deriveOverallStatus(normalized.tasks);
      setOverallStatus(derived);

      if (derived === 'success') {
        announceStatus('success');
        stopPolling();
      } else if (derived === 'failed' || derived === 'partial') {
        announceStatus(derived, normalized.tasks.find(task => task.status === 'failed')?.message);
        stopPolling();
      }
    } catch (error) {
      logger.error('輪詢同步狀態失敗', { error });
      const message = error instanceof Error ? error.message : t('workspace.wizard.steps.settingsSync.status.unavailable');
      setLastError(message);
      setOverallStatus('failed');
      announceStatus('failed', message);
      stopPolling();
    }
  }, [announceStatus, stopPolling, workspaceId]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) {
      return;
    }
    setIsPolling(true);
    void pollStatus();
    pollingRef.current = setInterval(() => {
      void pollStatus();
    }, 3000);
  }, [pollStatus]);

  const triggerSync = useCallback(async () => {
    setLastError(null);
    announcedStatusRef.current = 'running';
    setOverallStatus('running');
    setSetupStatus(createPlaceholderStatus(workspaceId, 'running', t('workspace.wizard.steps.settingsSync.status.preparing')));
    stopPolling();

    try {
      const result = await WorkspaceSetupService.startInitialSync(workspaceId);
      const normalized = normalizeStatus(workspaceId, result);
      setSetupStatus(normalized);

      const derived = deriveOverallStatus(normalized.tasks);
      setOverallStatus(derived);

      if (derived === 'success') {
        announceStatus('success');
        stopPolling();
      } else if (derived === 'failed' || derived === 'partial') {
        const failureMessage =
          normalized.tasks.find(task => task.status === 'failed')?.message || t('workspace.wizard.steps.settingsSync.notifications.failedDescription');
        setLastError(failureMessage);
        announceStatus(derived, failureMessage);
        stopPolling();
      } else if (hasPendingTasks(normalized.tasks)) {
        startPolling();
      }
    } catch (error) {
      logger.error('啟動同步流程失敗', { error });
      const message = error instanceof Error ? error.message : t('workspace.wizard.steps.settingsSync.notifications.failedTitle');
      setOverallStatus('failed');
      setLastError(message);
      setSetupStatus(createPlaceholderStatus(workspaceId, 'failed', message));
      announceStatus('failed', message);
      stopPolling();
    }
  }, [announceStatus, startPolling, stopPolling, workspaceId]);

  useEffect(() => {
    let mounted = true;
    const loadSettings = async () => {
      setLoading(true);
      try {
        if (!user?.id) {
          logger.warn('用戶未登入，無法載入設定');
          if (mounted) {
            setUserSettings(null);
            setLoading(false);
          }
          return;
        }

        const response = await apiClient.get<{ data: UserSettings }>(`/users/${user.id}/settings`);
        if (mounted) {
          setUserSettings(response.data);
        }
      } catch (error: any) {
        logger.error('載入用戶設定失敗', { error });
        if (error?.message?.includes('User not found') || error?.message?.includes('404')) {
          logger.info('用戶設定不存在，將顯示為無設定');
        }
        if (mounted) {
          setUserSettings(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void loadSettings();
    return () => {
      mounted = false;
    };
  }, [user]);

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!hasAnySettings) {
      stopPolling();
      setOverallStatus('success');
      setSetupStatus(createPlaceholderStatus(workspaceId, 'skipped', t('workspace.wizard.steps.settingsSync.empty.title')));
      announcedStatusRef.current = 'success';
      return;
    }

    if (!hasTriggeredSyncRef.current) {
      hasTriggeredSyncRef.current = true;
      void triggerSync();
    }
  }, [hasAnySettings, loading, stopPolling, triggerSync, workspaceId]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const currentTasks = setupStatus?.tasks ?? [];

  const renderStatusIcon = (status: WorkspaceSetupTaskState) => {
    if (status === 'success' || status === 'skipped') {
      return <CheckCircle className="h-4 w-4 text-emerald-500" />;
    }
    if (status === 'failed') {
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    }
    return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <div className="flex items-center justify-center gap-2">
          <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary">
            <Settings className="h-3.5 w-3.5" />
            {t('workspace.wizard.steps.settingsSync.badge')}
          </Badge>
        </div>
        <h1 className="text-2xl font-semibold text-foreground">{t('workspace.wizard.steps.settingsSync.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('workspace.wizard.steps.settingsSync.subtitle', { current: 4, total: 4 })}</p>
      </div>

      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: '100%' }} />
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            {t('workspace.wizard.steps.settingsSync.cardTitle')}
          </CardTitle>
          <CardDescription>
            {t('workspace.wizard.steps.settingsSync.cardDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {loading ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border/60 bg-muted/30 p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">{t('workspace.wizard.steps.settingsSync.loading')}</p>
            </div>
          ) : !hasAnySettings ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border/60 bg-muted/30 p-8 text-center">
              <AlertCircle className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">{t('workspace.wizard.steps.settingsSync.empty.title')}</p>
              <p className="text-xs text-muted-foreground">
                {t('workspace.wizard.steps.settingsSync.empty.description')}
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-foreground">{t('workspace.wizard.steps.settingsSync.currentSettings')}</h3>

                <div className="flex items-start gap-3 rounded-lg border bg-muted/30 p-4">
                  <Key className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">SSH Keys</p>
                    {userSettings?.ssh?.privateKey ? (
                      <p className="text-xs text-muted-foreground mt-1">{t('workspace.wizard.steps.settingsSync.settings.ssh.configured')}</p>
                    ) : (
                      <p className="text-xs text-muted-foreground mt-1">{t('workspace.wizard.steps.settingsSync.settings.notConfigured')}</p>
                    )}
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-lg border bg-muted/30 p-4">
                  <GitBranch className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{t('workspace.wizard.steps.settingsSync.settings.git.title')}</p>
                    {userSettings?.git?.userName ? (
                      <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                        <p>{t('workspace.wizard.steps.settingsSync.settings.git.userName', { value: userSettings.git.userName })}</p>
                        <p>{t('workspace.wizard.steps.settingsSync.settings.git.userEmail', { value: userSettings.git.userEmail || t('workspace.wizard.steps.settingsSync.settings.notConfigured') })}</p>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground mt-1">{t('workspace.wizard.steps.settingsSync.settings.notConfigured')}</p>
                    )}
                  </div>
                </div>

              </div>

              <div className="rounded-lg border bg-muted/20 p-4 space-y-3">
                <p className="text-sm font-medium text-foreground">{t('workspace.wizard.steps.settingsSync.syncStatus')}</p>
                <div className="space-y-2">
                  {TASK_ITEMS.map(item => {
                    const task = currentTasks.find(t => t.taskKey === item.key);
                    const Icon = item.icon;
                    return (
                      <div key={item.key} className="flex items-start gap-3 rounded-md bg-background/60 p-3">
                        <Icon className="h-4 w-4 text-primary mt-0.5" />
                        <div className="flex-1">
                          <div className="flex items-center gap-2 text-sm font-medium">
                            <span>{item.label}</span>
                            {task && renderStatusIcon(task.status)}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {task?.message || t('workspace.wizard.steps.settingsSync.status.pending')}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-col items-center gap-3 rounded-lg border bg-primary/5 p-6">
                {overallStatus === 'running' || isPolling ? (
                  <>
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">
                      {isPolling
                        ? t('workspace.wizard.steps.settingsSync.status.polling')
                        : t('workspace.wizard.steps.settingsSync.status.syncing')}
                    </p>
                  </>
                ) : overallStatus === 'success' ? (
                  <>
                    <CheckCircle className="h-8 w-8 text-emerald-500" />
                    <p className="text-sm font-medium text-emerald-600">{t('workspace.wizard.steps.settingsSync.status.success')}</p>
                  </>
                ) : overallStatus === 'partial' ? (
                  <>
                    <AlertCircle className="h-8 w-8 text-yellow-500" />
                    <p className="text-sm font-medium text-yellow-600">{t('workspace.wizard.steps.settingsSync.status.partial')}</p>
                    <Button onClick={() => triggerSync()} variant="outline" size="sm">
                      <RefreshCw className="h-4 w-4 mr-2" />
                      {t('workspace.wizard.steps.settingsSync.actions.resync')}
                    </Button>
                  </>
                ) : overallStatus === 'failed' ? (
                  <>
                    <AlertCircle className="h-8 w-8 text-destructive" />
                    <p className="text-sm font-medium text-destructive">{t('workspace.wizard.steps.settingsSync.status.failed')}</p>
                    {lastError && <p className="text-xs text-muted-foreground text-center">{lastError}</p>}
                    <Button onClick={() => triggerSync()} variant="outline" size="sm">
                      <RefreshCw className="h-4 w-4 mr-2" />
                      {t('workspace.wizard.steps.settingsSync.actions.retry')}
                    </Button>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-muted-foreground">{t('workspace.wizard.steps.settingsSync.status.idle')}</p>
                    <Button onClick={() => triggerSync()} className="w-full max-w-xs">
                      <RefreshCw className="h-4 w-4 mr-2" />
                      {t('workspace.wizard.steps.settingsSync.actions.start')}
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between items-center pt-6 border-t">
        <Button
          variant="outline"
          onClick={onPrevious}
          disabled={isSubmitting || overallStatus === 'running'}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('workspace.wizard.buttons.previous')}
        </Button>

        <Button
          onClick={onComplete}
          disabled={isSubmitting || overallStatus === 'running'}
          className="bg-primary text-primary-foreground"
        >
          {overallStatus === 'running'
            ? t('workspace.wizard.steps.settingsSync.status.syncing')
            : t('workspace.wizard.buttons.finish')}
        </Button>
      </div>
    </div>
  );
};

export default SettingsSyncStep;
