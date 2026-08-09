import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useMemo, useState, useRef } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceCreationStep');
import { ArrowLeft, CheckCircle, Copy, Loader2, Server, FileText, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { Progress } from '@/shared/components/ui/progress';
import { workspaceWizardService } from '../../services/workspaceWizardService';
import { apiClient } from '@/shared/api/apiClient';

interface RuntimeLogEntry {
  id: string;
  workspaceId: string;
  stage: string;
  message: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

interface WorkspaceRuntimeResponse {
  runtimeStatus: {
    runtimeUrl: string;
  };
}

interface WorkspaceCreationStepProps {
  workspaceId: string | null;
  isPolling: boolean;
  errorKey: string | null;
  onPrevious: () => void;
  onRetry: () => void | Promise<void>;
  onComplete: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const areLogEntriesEqual = (current: RuntimeLogEntry[], next: RuntimeLogEntry[]) => {
  if (current.length !== next.length) {
    return false;
  }

  return current.every((entry, index) => {
    const nextEntry = next[index];
    return nextEntry
      && entry.id === nextEntry.id
      && entry.stage === nextEntry.stage
      && entry.message === nextEntry.message
      && entry.createdAt === nextEntry.createdAt;
  });
};

const WorkspaceCreationStep: React.FC<WorkspaceCreationStepProps> = ({
  workspaceId,
  isPolling,
  errorKey,
  onPrevious,
  onRetry,
  onComplete,
  t,
}) => {
  const [logs, setLogs] = useState<RuntimeLogEntry[]>([]);
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const logsRef = useRef<RuntimeLogEntry[]>([]);

  const [healthCheckPassed, setHealthCheckPassed] = useState(false);
  const [healthCheckError, setHealthCheckError] = useState<string | null>(null);
  const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const isReady = !isPolling && !errorKey && healthCheckPassed;
  const isHealthCheckActive = !isPolling && !errorKey && !healthCheckPassed;

  const progressState = useMemo(() => {
    if (errorKey) {
      return {
        value: 100,
        title: t('workspace.wizard.steps.workspaceCreation.progress.failedTitle'),
        description: t('workspace.wizard.steps.workspaceCreation.progress.failedDescription'),
      };
    }

    if (isReady) {
      return {
        value: 100,
        title: t('workspace.wizard.steps.workspaceCreation.progress.readyTitle'),
        description: t('workspace.wizard.steps.workspaceCreation.progress.readyDescription'),
      };
    }

    if (isPolling) {
      return {
        value: 35,
        title: t('workspace.wizard.steps.workspaceCreation.progress.provisioningTitle'),
        description: t('workspace.wizard.steps.workspaceCreation.progress.provisioningDescription'),
      };
    }

    return {
      value: 72,
      title: t('workspace.wizard.steps.workspaceCreation.progress.healthTitle'),
      description: healthCheckError || t('workspace.wizard.steps.workspaceCreation.progress.healthDescription'),
    };
  }, [errorKey, healthCheckError, isPolling, isReady, t]);

  const progressPhases = useMemo(() => [
    {
      key: 'infrastructure',
      title: t('workspace.wizard.steps.workspaceCreation.infrastructure.title'),
      description: isPolling
        ? t('workspace.wizard.steps.workspaceCreation.infrastructure.pending')
        : errorKey
          ? t('workspace.wizard.steps.workspaceCreation.infrastructure.failed')
          : t('workspace.wizard.steps.workspaceCreation.infrastructure.success'),
      status: errorKey ? 'failed' : isPolling ? 'active' : 'complete',
    },
    {
      key: 'health',
      title: t('workspace.wizard.steps.workspaceCreation.health.title'),
      description: isHealthCheckActive
        ? healthCheckError || t('workspace.wizard.steps.workspaceCreation.health.pending')
        : healthCheckPassed
          ? t('workspace.wizard.steps.workspaceCreation.health.success')
          : t('workspace.wizard.steps.workspaceCreation.health.waiting'),
      status: errorKey ? 'pending' : healthCheckPassed ? 'complete' : isHealthCheckActive ? 'active' : 'pending',
    },
  ], [errorKey, healthCheckError, healthCheckPassed, isHealthCheckActive, isPolling, t]);

  useEffect(() => {
    if (!workspaceId || isReady) return;

    const fetchLogs = async () => {
      const shouldShowLoading = logsRef.current.length === 0;

      try {
        if (shouldShowLoading) {
          setIsLogsLoading(true);
        }

        const runtimeLogs = await workspaceWizardService.getRuntimeLogs(workspaceId);

        setLogs((currentLogs) => {
          if (areLogEntriesEqual(currentLogs, runtimeLogs)) {
            return currentLogs;
          }

          logsRef.current = runtimeLogs;
          return runtimeLogs;
        });
      } catch (error) {
        logger.error('Failed to fetch runtime logs', { error });
      } finally {
        if (shouldShowLoading) {
          setIsLogsLoading(false);
        }
      }
    };

    void fetchLogs();
    if (errorKey) {
      return;
    }

    const timer = setInterval(fetchLogs, 2000);
    return () => clearInterval(timer);
  }, [errorKey, workspaceId, isReady]);

  useEffect(() => {
    if (!workspaceId || isPolling || healthCheckPassed || errorKey) {
      return;
    }

    let consecutiveFailures = 0;
    const MAX_CONSECUTIVE_FAILURES = 3;

    const checkHealth = async () => {
      try {
        const workspace = await apiClient.get<WorkspaceRuntimeResponse>(`/workspaces/${workspaceId}`);
        const healthResponse = await fetch(`${workspace.runtimeStatus.runtimeUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        });

        if (healthResponse.ok) {
          const healthData = await healthResponse.json();
          logger.debug('Workspace runtime health check passed', { healthData });
          setHealthCheckPassed(true);
          setHealthCheckError(null);
          consecutiveFailures = 0;

          if (healthCheckIntervalRef.current) {
            clearInterval(healthCheckIntervalRef.current);
            healthCheckIntervalRef.current = null;
          }
        } else {
          logger.debug('Health check failed with status', { status: healthResponse.status });
          consecutiveFailures++;
          if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
            setHealthCheckError(t('workspace.wizard.steps.workspaceCreation.health.retrying'));
          }
        }
      } catch (error) {
        logger.debug('Health check failed, will retry', { error });
        consecutiveFailures++;
        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          setHealthCheckError(t('workspace.wizard.steps.workspaceCreation.health.retrying'));
        }
      }
    };

    checkHealth();

    healthCheckIntervalRef.current = setInterval(checkHealth, 2000);

    return () => {
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
        healthCheckIntervalRef.current = null;
      }
    };
  }, [workspaceId, isPolling, healthCheckPassed, errorKey, t]);

  const renderPhaseIcon = (status: string) => {
    if (status === 'complete') {
      return <CheckCircle className="h-4 w-4 text-emerald-500" />;
    }

    if (status === 'active') {
      return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
    }

    if (status === 'failed') {
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    }

    return <div className="h-4 w-4 rounded-full border-2 border-muted" />;
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <div className="flex items-center justify-center gap-2 text-primary">
          <Server className="h-8 w-8" />
          <h1 className="text-2xl font-semibold text-foreground">
            {t('workspace.wizard.steps.workspaceCreation.title')}
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('workspace.wizard.steps.workspaceCreation.subtitle', { current: 3, total: 3 })}
        </p>
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Server className="h-5 w-5" />
            {t('workspace.wizard.steps.workspaceCreation.cardTitle')}
          </CardTitle>
          <CardDescription>
            {t('workspace.wizard.steps.workspaceCreation.cardDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-5 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">{progressState.title}</p>
                <p className="text-sm text-muted-foreground">{progressState.description}</p>
              </div>
              {workspaceId && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-fit gap-2"
                  onClick={() => setLogsDialogOpen(true)}
                >
                  <FileText className="h-4 w-4" />
                  {t('workspace.wizard.steps.workspaceCreation.logs.open', { count: logs.length })}
                </Button>
              )}
            </div>

            <div className="space-y-2">
              <Progress value={progressState.value} className="h-2" />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{t('workspace.wizard.steps.workspaceCreation.progress.label')}</span>
                <span>{t('workspace.wizard.steps.workspaceCreation.progress.percent', { value: progressState.value })}</span>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {progressPhases.map((phase) => (
                <div key={phase.key} className="flex min-w-0 items-start gap-3 rounded-md bg-background p-3">
                  <div className="mt-0.5 flex h-5 w-5 items-center justify-center">
                    {renderPhaseIcon(phase.status)}
                  </div>
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium text-foreground">{phase.title}</p>
                    <p className="text-xs text-muted-foreground">{phase.description}</p>
                  </div>
                </div>
              ))}
            </div>

            {workspaceId && (
              <div className="rounded-lg border bg-background p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">{t('workspace.wizard.steps.workspaceCreation.workspaceId.label')}</span>
                  <div className="flex items-center gap-2">
                    <code className="text-xs font-mono text-foreground bg-muted px-2 py-1 rounded">
                      {workspaceId.slice(0, 8)}...{workspaceId.slice(-8)}
                    </code>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => {
                        navigator.clipboard.writeText(workspaceId);
                      }}
                      title={t('workspace.wizard.steps.workspaceCreation.workspaceId.copyTitle')}
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {errorKey && (
              <div className="rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
                {t(`workspace.wizard.${errorKey}`)}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between border-t pt-4">
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={onPrevious} className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                {t('workspace.wizard.buttons.previous')}
              </Button>
              <Button type="button" variant="ghost" disabled={isPolling || !errorKey} onClick={onRetry}>
                {t('workspace.wizard.buttons.retry')}
              </Button>
            </div>
            <Button type="button" onClick={onComplete} disabled={!isReady} className="bg-primary text-primary-foreground">
              {isReady ? t('workspace.wizard.buttons.finish') : t('common.messages.waitingComplete')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={logsDialogOpen} onOpenChange={setLogsDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-2xl overflow-hidden">
          <DialogHeader>
            <DialogHeading icon={FileText}>
              {t('workspace.wizard.steps.workspaceCreation.logs.dialogTitle')}
            </DialogHeading>
            <DialogDescription>
              {t('workspace.wizard.steps.workspaceCreation.logs.dialogDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[52vh] overflow-y-auto rounded-md border bg-muted/20 p-3">
            {logs.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {isLogsLoading
                  ? t('workspace.wizard.steps.workspaceCreation.logs.loading')
                  : t('workspace.wizard.steps.workspaceCreation.logs.empty')}
              </div>
            ) : (
              <div className="space-y-3">
                {[...logs].reverse().map((log) => (
                  <div key={log.id} className="rounded-md bg-background p-3 text-xs">
                    <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
                      <span className="font-mono">
                        {new Date(log.createdAt).toLocaleTimeString()}
                      </span>
                      <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                        {log.stage}
                      </span>
                    </div>
                    <div className="mt-2 text-foreground">{log.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WorkspaceCreationStep;
