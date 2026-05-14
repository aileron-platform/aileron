import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import {
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  FileText,
  MessageSquare,
  Ban,
  AlertCircle,
  X,
} from 'lucide-react';
import { AutomationJob, JobExecution } from '@/features/automation/types';
import { TaskLog } from '@/shared/types/task';
import {
  ExecutionLogDialog,
  ExecutionLogDialogCopy,
  ExecutionLogBuilder,
} from './ExecutionLogDialog';
import { SessionViewerDialog } from '@/features/workspace/components/session-viewer/SessionViewerDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '@/features/automation/services/automationApi';
import { useToast } from '@/shared/components/ui/use-toast';
import { hasActiveExecutions, isCancellableExecution } from '@/features/automation/utils/executionUtils';
import { POLLING_CONFIG } from '@/features/automation/constants';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('JobExecutionsDialog');

export type ExecutionRangeOption = 'all' | 'today' | 'tomorrow' | 'week' | 'month' | 'custom';

export interface CustomDateRange {
  start: string | null;
  end: string | null;
}

interface JobExecutionsDialogProps {
  isOpen: boolean;
  job: AutomationJob | null;
  executions: JobExecution[];
  onClose: () => void;
  onRefresh?: () => void;
  title?: string;
  description?: string;
  runtimeBaseUrl?: string;
}

type Translate = (key: string, params?: Record<string, string | number>) => string;

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
const endOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
const startOfTomorrow = (date: Date) => {
  const tomorrow = new Date(date);
  tomorrow.setDate(tomorrow.getDate() + 1);
  return startOfDay(tomorrow);
};
const endOfTomorrow = (date: Date) => {
  const tomorrow = new Date(date);
  tomorrow.setDate(tomorrow.getDate() + 1);
  return endOfDay(tomorrow);
};
const startOfWeek = (date: Date) => {
  const result = startOfDay(date);
  const day = result.getDay();
  const diff = (day + 6) % 7;
  result.setDate(result.getDate() - diff);
  return result;
};
const endOfWeek = (date: Date) => {
  const result = startOfWeek(date);
  result.setDate(result.getDate() + 6);
  return endOfDay(result);
};
const startOfMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1);
const endOfMonth = (date: Date) => endOfDay(new Date(date.getFullYear(), date.getMonth() + 1, 0));
const parseDateInput = (value: string) => new Date(`${value}T00:00:00`);

export const JobExecutionsDialog: React.FC<JobExecutionsDialogProps> = ({
  isOpen,
  job,
  executions,
  onClose,
  onRefresh,
  title,
  description,
  runtimeBaseUrl,
}) => {
  const { t, state } = useI18n();
  const { toast } = useToast();
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';
  const [executionRangeOption, setExecutionRangeOption] = useState<ExecutionRangeOption>('all');
  const [customRange, setCustomRange] = useState<CustomDateRange>({ start: null, end: null });
  const [selectedExecution, setSelectedExecution] = useState<JobExecution | null>(null);
  const [isLogDialogOpen, setIsLogDialogOpen] = useState(false);
  const [isSessionDialogOpen, setIsSessionDialogOpen] = useState(false);
  const [cancellingExecutionId, setCancellingExecutionId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const executionDialogCopy = useMemo<ExecutionLogDialogCopy<JobExecution>>(
    () => ({
      description: t('workspace.automation.dialogs.executionLog.description'),
      fields: {
        executionId: t('workspace.automation.dialogs.executionLog.fields.executionId'),
        jobId: t('workspace.automation.dialogs.executionLog.fields.jobId'),
        startedAt: t('workspace.automation.dialogs.executionLog.fields.startedAt'),
        finishedAt: t('workspace.automation.dialogs.executionLog.fields.finishedAt'),
        trigger: t('workspace.automation.dialogs.executionLog.fields.trigger'),
        duration: t('workspace.automation.dialogs.executionLog.fields.duration'),
      },
      statusLabel: status =>
        t(`workspace.automation.dialogs.executions.status.${status}`, { status }),
      formatTrigger: execution => t(`workspace.automation.triggers.${execution.trigger}`),
      formatDuration: execution =>
        typeof execution.duration === 'number'
          ? t('workspace.automation.dialogs.executionLog.durationSeconds', { seconds: execution.duration })
          : null,
      logs: {
        title: t('workspace.automation.dialogs.executionLog.logs.title'),
        empty: t('workspace.automation.dialogs.executionLog.logs.empty'),
        loading: t('workspace.automation.dialogs.executionLog.logs.loading'),
        reload: t('workspace.automation.dialogs.executionLog.logs.reload'),
        filters: {
          all: t('workspace.automation.dialogs.executionLog.logs.filters.all'),
          info: t('workspace.automation.dialogs.executionLog.logs.filters.info'),
          error: t('workspace.automation.dialogs.executionLog.logs.filters.error'),
          warning: t('workspace.automation.dialogs.executionLog.logs.filters.warning'),
          success: t('workspace.automation.dialogs.executionLog.logs.filters.success'),
        },
      },
    }),
    [t]
  );

  const buildExecutionLogs = useCallback<ExecutionLogBuilder<JobExecution>>(
    execution => {
      const startTime = new Date(execution.startedAt).getTime();
      const offset = (minutes: number) => new Date(startTime + minutes * 60_000).toISOString();

      const logSummary = execution.summary.length > 150
        ? `${execution.summary.substring(0, 150)}...`
        : execution.summary;

      const baseLogs: TaskLog[] = [
        {
          timestamp: offset(0),
          level: 'INFO',
          message: t('workspace.automation.dialogs.executionLog.mock.start', {
            taskId: execution.jobId,
            trigger: t(`workspace.automation.triggers.${execution.trigger}`),
          }),
        },
        {
          timestamp: offset(0.5),
          level: 'INFO',
          message: t('workspace.automation.dialogs.executionLog.mock.loadEnvironment'),
        },
        {
          timestamp: offset(1.2),
          level: 'INFO',
          message: logSummary,
        },
      ];

      if (execution.status === 'failed') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'ERROR',
          message: t('workspace.automation.dialogs.executionLog.mock.failureDetected'),
        });
      }

      if (execution.status === 'success') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'SUCCESS',
          message: t('workspace.automation.dialogs.executionLog.mock.completed'),
        });
      }

      if (execution.status === 'running' || execution.status === 'queued') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'INFO',
          message:
            execution.status === 'running'
              ? t('workspace.automation.dialogs.executionLog.mock.running')
              : t('workspace.automation.dialogs.executionLog.mock.queued'),
        });
      }

      return baseLogs;
    },
    [t]
  );

  const executionFilterRange = useMemo(() => {
    const now = new Date();

    if (executionRangeOption === 'all') {
      return { start: null, end: null };
    }

    if (executionRangeOption === 'today') {
      return { start: startOfDay(now), end: endOfDay(now) };
    }

    if (executionRangeOption === 'tomorrow') {
      return { start: startOfTomorrow(now), end: endOfTomorrow(now) };
    }

    if (executionRangeOption === 'week') {
      return { start: startOfWeek(now), end: endOfWeek(now) };
    }

    if (executionRangeOption === 'month') {
      return { start: startOfMonth(now), end: endOfMonth(now) };
    }

    const hasStart = customRange.start && customRange.start.trim().length > 0;
    const hasEnd = customRange.end && customRange.end.trim().length > 0;

    let start = hasStart ? startOfDay(parseDateInput(customRange.start!)) : null;
    let end = hasEnd ? endOfDay(parseDateInput(customRange.end!)) : null;

    if (start && end && start.getTime() > end.getTime()) {
      const temp = start;
      start = end;
      end = temp;
    }

    return { start, end };
  }, [executionRangeOption, customRange.start, customRange.end]);

  const filteredExecutions = useMemo(() => {
    const { start, end } = executionFilterRange;

    return executions.filter(execution => {
      const startedAt = new Date(execution.startedAt);
      const timestamp = startedAt.getTime();
      if (!Number.isNaN(timestamp)) {
        if (start && timestamp < start.getTime()) {
          return false;
        }
        if (end && timestamp > end.getTime()) {
          return false;
        }
      }
      return true;
    });
  }, [executions, executionFilterRange]);

  const handleCustomRangeChange = useCallback((key: keyof CustomDateRange, value: string) => {
    setCustomRange(prev => ({
      ...prev,
      [key]: value.trim().length > 0 ? value : null,
    }));
  }, []);

  const handleViewLog = useCallback((execution: JobExecution) => {
    setSelectedExecution(execution);
    setIsLogDialogOpen(true);
  }, []);

  const handleCloseLog = useCallback(() => {
    setIsLogDialogOpen(false);
    setSelectedExecution(null);
  }, []);

  const handleViewSession = useCallback((execution: JobExecution) => {
    setSelectedExecution(execution);
    setIsSessionDialogOpen(true);
  }, []);

  const handleCloseSession = useCallback(() => {
    setIsSessionDialogOpen(false);
    setSelectedExecution(null);
  }, []);

  const handleCancelExecution = useCallback(async (execution: JobExecution) => {
    if (!isCancellableExecution(execution)) {
      toast({
        title: t('workspace.automation.dialogs.executions.cancel.invalidStatus.title'),
        description: t('workspace.automation.dialogs.executions.cancel.invalidStatus.description'),
        variant: 'destructive',
      });
      return;
    }

    setCancellingExecutionId(execution.id);
    try {
      const result = await automationApi.cancelExecution(execution.id);

      if (result.cancelled) {
        toast({
          title: t('workspace.automation.dialogs.executions.cancel.success.title'),
          description: t('workspace.automation.dialogs.executions.cancel.success.description'),
          variant: 'success',
        });

        onRefresh?.();
      } else {
        toast({
          title: t('workspace.automation.dialogs.executions.cancel.failed.title'),
          description: result.message || t('workspace.automation.dialogs.executions.cancel.failed.description'),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('Failed to cancel execution', { error });
      toast({
        title: t('workspace.automation.dialogs.executions.cancel.error.title'),
        description: error instanceof Error ? error.message : t('workspace.automation.dialogs.executions.cancel.error.description'),
        variant: 'destructive',
      });
    } finally {
      setCancellingExecutionId(null);
    }
  }, [toast, t, onRefresh]);

  const handleManualRefresh = useCallback(() => {
    setIsRefreshing(true);
    try {
      onRefresh?.();
    } finally {
      setTimeout(() => setIsRefreshing(false), POLLING_CONFIG.REFRESH_ANIMATION_DURATION_MS);
    }
  }, [onRefresh]);

  useEffect(() => {
    if (!isOpen || !onRefresh) {
      return;
    }

    if (!hasActiveExecutions(executions)) {
      return;
    }

    const intervalId = setInterval(() => {
      if (document.visibilityState === 'visible') {
        onRefresh();
      }
    }, POLLING_CONFIG.INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  }, [isOpen, executions, onRefresh]);

  if (!job) return null;

  const dialogTitle = title || t('workspace.automation.dialogs.executions.recordTitle', { name: job.name });
  const dialogDescription = description ?? job.description ?? t('workspace.automation.dialogs.executions.recordDescription');

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
        <DialogContent className="max-w-4xl h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader className="flex-shrink-0">
            <DialogHeading icon={Clock} className="text-lg font-semibold">
              {dialogTitle}
            </DialogHeading>
            <DialogDescription className="text-sm text-muted-foreground">{dialogDescription}</DialogDescription>
          </DialogHeader>

          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="pb-4 mb-4 border-b border-border flex-shrink-0">
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">{t('workspace.automation.dialogs.executions.filter.title')}</h3>
                    <p className="text-xs text-muted-foreground">{t('workspace.automation.dialogs.executions.filter.description')}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleManualRefresh}
                    disabled={isRefreshing}
                    className="h-8 px-3"
                  >
                    <RefreshCw className={`h-4 w-4 mr-1.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                    {t('workspace.automation.dialogs.executions.refresh')}
                  </Button>
                </div>

                <Tabs value={executionRangeOption} onValueChange={value => setExecutionRangeOption(value as ExecutionRangeOption)}>
                  <TabsList className="grid w-full grid-cols-6">
                    <TabsTrigger value="all" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.all')}</TabsTrigger>
                    <TabsTrigger value="today" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.today')}</TabsTrigger>
                    <TabsTrigger value="tomorrow" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.tomorrow')}</TabsTrigger>
                    <TabsTrigger value="week" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.week')}</TabsTrigger>
                    <TabsTrigger value="month" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.month')}</TabsTrigger>
                    <TabsTrigger value="custom" className="text-xs">{t('workspace.automation.dialogs.executions.rangeTabs.custom')}</TabsTrigger>
                  </TabsList>
                </Tabs>

                {executionRangeOption === 'custom' && (
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2 pt-2">
                    <Input
                      type="date"
                      value={customRange.start ?? ''}
                      onChange={event => handleCustomRangeChange('start', event.target.value)}
                      className="h-9 w-full text-xs sm:w-40"
                      placeholder={t('workspace.automation.dialogs.executions.customRange.startPlaceholder')}
                    />
                    <span className="hidden text-xs text-muted-foreground sm:block">{t('workspace.automation.dialogs.executions.customRange.separator')}</span>
                    <Input
                      type="date"
                      value={customRange.end ?? ''}
                      onChange={event => handleCustomRangeChange('end', event.target.value)}
                      className="h-9 w-full text-xs sm:w-40"
                      placeholder={t('workspace.automation.dialogs.executions.customRange.endPlaceholder')}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-9 px-3 text-xs"
                      onClick={() => setCustomRange({ start: null, end: null })}
                      disabled={!customRange.start && !customRange.end}
                    >
                      {t('workspace.automation.dialogs.executions.customRange.clear')}
                    </Button>
                  </div>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              <div className="space-y-4">
                {filteredExecutions.map(execution => (
                  <ExecutionCard
                    key={execution.id}
                    execution={execution}
                    onViewLog={handleViewLog}
                    onViewSession={handleViewSession}
                    onCancel={handleCancelExecution}
                    hasSession={!!execution.sessionId && !!runtimeBaseUrl && !!job?.workspaceId}
                    isCancelling={cancellingExecutionId === execution.id}
                    t={t}
                    locale={locale}
                  />
                ))}
                {filteredExecutions.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">{t('workspace.automation.dialogs.executions.empty')}</p>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ExecutionLogDialog
        isOpen={isLogDialogOpen}
        execution={selectedExecution}
        onClose={handleCloseLog}
        locale={locale}
        copy={executionDialogCopy}
        createLogs={buildExecutionLogs}
      />

      {selectedExecution?.sessionId && job?.workspaceId && runtimeBaseUrl && (
        <SessionViewerDialog
          isOpen={isSessionDialogOpen}
          onClose={handleCloseSession}
          sessionId={selectedExecution.sessionId}
          workspaceId={job.workspaceId}
          runtimeBaseUrl={runtimeBaseUrl}
        />
      )}
    </>
  );
};

interface ExecutionCardProps {
  execution: JobExecution;
  onViewLog: (execution: JobExecution) => void;
  onViewSession: (execution: JobExecution) => void;
  onCancel: (execution: JobExecution) => void;
  hasSession: boolean;
  isCancelling: boolean;
  t: Translate;
  locale: string;
}

const executionStatusIconMap: Record<JobExecution['status'], React.ReactNode> = {
  queued: <Clock className="h-4 w-4 text-amber-500" />,
  waiting: <Clock className="h-4 w-4 text-purple-500" />,
  running: <RefreshCw className="h-4 w-4 text-sky-500 animate-spin" />,
  success: <CheckCircle2 className="h-4 w-4 text-primary" />,
  failed: <XCircle className="h-4 w-4 text-rose-500" />,
  cancelled: <Ban className="h-4 w-4 text-gray-500" />,
  timeout: <AlertCircle className="h-4 w-4 text-orange-500" />,
};

const executionStatusBadgeClass: Record<JobExecution['status'], string> = {
  queued: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-500/15 dark:text-amber-200 dark:border-amber-400/40',
  waiting: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-500/15 dark:text-purple-200 dark:border-purple-400/40',
  running: 'bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-500/15 dark:text-sky-200 dark:border-sky-400/40',
  success: 'bg-primary/10 text-primary border-primary/20 dark:bg-primary/15 dark:text-primary-foreground dark:border-primary/30',
  failed: 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-500/15 dark:text-rose-200 dark:border-rose-400/40',
  cancelled: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-500/15 dark:text-gray-200 dark:border-gray-400/40',
  timeout: 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-500/15 dark:text-orange-200 dark:border-orange-400/40',
};

const ExecutionCard: React.FC<ExecutionCardProps> = ({
  execution,
  onViewLog,
  onViewSession,
  onCancel,
  hasSession,
  isCancelling,
  t,
  locale
}) => {
  const statusLabel = t(`workspace.automation.dialogs.executions.status.${execution.status}`, { status: execution.status });
  const statusBadgeClass = executionStatusBadgeClass[execution.status] ?? 'bg-gray-100 text-gray-700';
  const statusIcon = executionStatusIconMap[execution.status] ?? <Clock className="h-4 w-4 text-gray-500" />;
  const triggerLabel = t('workspace.automation.dialogs.executions.triggerLabel', {
    trigger: t(`workspace.automation.triggers.${execution.trigger}`),
  });

  const truncatedSummary = execution.summary.length > 100
    ? `${execution.summary.substring(0, 100)}...`
    : execution.summary;

  return (
    <div className="rounded-lg border border-border/40 bg-background/70 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {statusIcon}
          <Badge className={`text-xs ${statusBadgeClass}`}>
            {statusLabel}
          </Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {t('workspace.automation.dialogs.executions.startedAt', {
            time: new Date(execution.startedAt).toLocaleString(locale),
          })}
        </div>
      </div>

      <p className="mt-2 text-sm text-foreground" title={execution.summary}>{truncatedSummary}</p>

      <div className="mt-3 flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>{triggerLabel}</span>
          {execution.duration && (
            <span>{t('workspace.automation.dialogs.executions.durationLabel', { seconds: execution.duration })}</span>
          )}
          {execution.status === 'waiting' && execution.queuePosition && (
            <span className="text-amber-600 dark:text-amber-400">
              {t('workspace.automation.dialogs.executions.queuePosition', { position: execution.queuePosition })}
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {execution.status === 'waiting' && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-3 text-xs font-medium text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => onCancel(execution)}
              disabled={isCancelling}
            >
              {isCancelling ? (
                <RefreshCw className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <X className="mr-1.5 h-3.5 w-3.5" />
              )}
              {t('workspace.automation.dialogs.executions.cancelButton')}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-3 text-xs font-medium text-primary"
            onClick={() => onViewLog(execution)}
          >
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            {t('workspace.automation.dialogs.executions.viewLog')}
          </Button>
          {hasSession && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-3 text-xs font-medium text-primary"
              onClick={() => onViewSession(execution)}
            >
              <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
              {t('workspace.automation.dialogs.executions.viewSession')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default JobExecutionsDialog;
