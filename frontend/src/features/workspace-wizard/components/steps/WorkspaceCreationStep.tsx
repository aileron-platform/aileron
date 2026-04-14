import React, { useEffect, useState, useRef } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceCreationStep');
import { ArrowLeft, CheckCircle, Loader2, Server, FileText, AlertCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { workspaceWizardService } from '../../services/workspaceWizardService';
import { apiClient } from '@/shared/api/apiClient';

interface RuntimeLogEntry {
  id: string;
  workspaceId: string;
  stage: string;
  message: string;
  metadata: Record<string, any>;
  createdAt: string;
}

interface WorkspaceCreationStepProps {
  workspaceId: string | null;
  isPolling: boolean;
  errorKey: string | null;
  onPrevious: () => void;
  onRetry: () => void;
  onContinue: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export const WorkspaceCreationStep: React.FC<WorkspaceCreationStepProps> = ({
  workspaceId,
  isPolling,
  errorKey,
  onPrevious,
  onRetry,
  onContinue,
  t,
}) => {
  const [logs, setLogs] = useState<RuntimeLogEntry[]>([]);
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [showLogs, setShowLogs] = useState(true);

  // Health check 狀態
  const [healthCheckPassed, setHealthCheckPassed] = useState(false);
  const [healthCheckError, setHealthCheckError] = useState<string | null>(null);
  const healthCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const isReady = !isPolling && !errorKey && healthCheckPassed;

  // 輪詢日誌
  useEffect(() => {
    if (!workspaceId || isReady) return;

    const fetchLogs = async () => {
      try {
        setIsLogsLoading(true);
        const runtimeLogs = await workspaceWizardService.getRuntimeLogs(workspaceId);
        setLogs(runtimeLogs);
      } catch (error) {
        logger.error('Failed to fetch runtime logs', { error });
      } finally {
        setIsLogsLoading(false);
      }
    };

    fetchLogs();
    const timer = setInterval(fetchLogs, 2000);
    return () => clearInterval(timer);
  }, [workspaceId, isReady]);

  // Health check 輪詢 - 只在容器佈建完成後開始
  useEffect(() => {
    // 只在容器佈建完成（isPolling = false）且尚未通過 health check 時執行
    if (!workspaceId || isPolling || healthCheckPassed || errorKey) {
      return;
    }

    let consecutiveFailures = 0;
    const MAX_CONSECUTIVE_FAILURES = 3; // 連續失敗 3 次才顯示錯誤

    const checkHealth = async () => {
      try {
        // 1. 取得 workspace 資訊以獲取 runtime URL
        const workspace = await apiClient.get<any>(`/workspaces/${workspaceId}`);
        const externalUrl = workspace.runtimeStatus?.externalUrl;

        if (!externalUrl) {
          logger.debug('Runtime URL not available yet');
          consecutiveFailures = 0; // 重置失敗計數
          setHealthCheckError(null);
          return;
        }

        // 2. 直接呼叫 workspace-runtime 的 health endpoint
        const healthResponse = await fetch(`${externalUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000),
        });

        if (healthResponse.ok) {
          const healthData = await healthResponse.json();
          logger.debug('Workspace runtime health check passed', { healthData });
          setHealthCheckPassed(true);
          setHealthCheckError(null);
          consecutiveFailures = 0;

          // 清除輪詢
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
        // 只在連續失敗多次後才顯示錯誤，避免閃爍
        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          setHealthCheckError(t('workspace.wizard.steps.workspaceCreation.health.retrying'));
        }
      }
    };

    // 立即檢查一次
    checkHealth();

    // 每 2 秒檢查一次
    healthCheckIntervalRef.current = setInterval(checkHealth, 2000);

    return () => {
      if (healthCheckIntervalRef.current) {
        clearInterval(healthCheckIntervalRef.current);
        healthCheckIntervalRef.current = null;
      }
    };
  }, [workspaceId, isPolling, healthCheckPassed, errorKey, t]);

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
          {t('workspace.wizard.steps.workspaceCreation.subtitle', { current: 3, total: 4 })}
        </p>
      </div>

      <div className="h-2 w-full rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: '75%' }} />
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
          {/* 狀態顯示區域 */}
          <div className="space-y-4">
            {/* 容器佈建狀態 */}
            <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-4">
              {isPolling ? (
                <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
              ) : errorKey ? (
                <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0" />
              ) : (
                <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0" />
              )}
              <div className="flex-1">
                <p className="text-sm font-medium">{t('workspace.wizard.steps.workspaceCreation.infrastructure.title')}</p>
                <p className="text-xs text-muted-foreground">
                  {isPolling
                    ? t('workspace.wizard.steps.workspaceCreation.infrastructure.pending')
                    : errorKey
                      ? t('workspace.wizard.steps.workspaceCreation.infrastructure.failed')
                      : t('workspace.wizard.steps.workspaceCreation.infrastructure.success')}
                </p>
              </div>
            </div>

            {/* Health Check 狀態 */}
            <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-4">
              {!isPolling && !errorKey && !healthCheckPassed ? (
                <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
              ) : healthCheckPassed ? (
                <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0" />
              ) : (
                <div className="h-5 w-5 rounded-full border-2 border-muted flex-shrink-0" />
              )}
              <div className="flex-1">
                <p className="text-sm font-medium">{t('workspace.wizard.steps.workspaceCreation.health.title')}</p>
                <p className="text-xs text-muted-foreground">
                  {!isPolling && !errorKey && !healthCheckPassed
                    ? healthCheckError || t('workspace.wizard.steps.workspaceCreation.health.pending')
                    : healthCheckPassed
                      ? t('workspace.wizard.steps.workspaceCreation.health.success')
                      : t('workspace.wizard.steps.workspaceCreation.health.waiting')}
                </p>
              </div>
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
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
                        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
                      </svg>
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

          {/* 日誌顯示區域 */}
          {workspaceId && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  <span className="text-sm font-medium">{t('workspace.wizard.steps.workspaceCreation.logs.title')}</span>
                  {isLogsLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowLogs(!showLogs)}
                >
                  {(showLogs
                    ? t('workspace.wizard.steps.workspaceCreation.logs.hide')
                    : t('workspace.wizard.steps.workspaceCreation.logs.show'))} ({logs.length})
                </Button>
              </div>

              {showLogs && (
                <div className="max-h-64 overflow-y-auto rounded-md border bg-muted/20 p-3">
                  {logs.length === 0 ? (
                    <div className="text-center text-sm text-muted-foreground py-4">
                      {isLogsLoading
                        ? t('workspace.wizard.steps.workspaceCreation.logs.loading')
                        : t('workspace.wizard.steps.workspaceCreation.logs.empty')}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {[...logs].reverse().map((log) => (
                        <div key={log.id} className="text-xs">
                          <div className="flex items-center gap-2 text-muted-foreground">
                            <span className="font-mono">
                              {new Date(log.createdAt).toLocaleTimeString()}
                            </span>
                            <span className="px-1.5 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-medium">
                              {log.stage}
                            </span>
                          </div>
                          <div className="text-foreground mt-1">{log.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between border-t pt-4">
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={onPrevious} className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                {t('workspace.wizard.buttons.previous')}
              </Button>
              <Button type="button" variant="ghost" disabled={isPolling} onClick={onRetry}>
                {t('workspace.wizard.buttons.retry')}
              </Button>
            </div>
            <Button type="button" onClick={onContinue} disabled={!isReady} className="bg-primary text-primary-foreground">
              {isReady ? t('workspace.wizard.buttons.next') : t('common.messages.waitingComplete')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default WorkspaceCreationStep;
