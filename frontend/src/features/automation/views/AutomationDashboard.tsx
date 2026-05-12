/**
 * AutomationDashboard - Scheduler center main view
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AutomationDashboard');
import {
  Clock,
  RefreshCw,
  Plus,
  Search,
  ShieldAlert,
  UserCircle,
  Tag,
  AlarmClock,
  CheckCircle2,
  PauseCircle,
  AlertTriangle,
  Timer,
  FileText,
  MoreHorizontal,
  Pencil,
  Trash2,
  PlayCircle,
  History,
  MessageSquare,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { useAutomation } from '../providers/AutomationProvider';
import { AutomationJob, JobExecution } from '../types';
import {
  ExecutionLogDialog as SharedExecutionLogDialog,
  ExecutionLogDialogCopy,
  ExecutionLogBuilder,
} from '@/features/automation/components/ExecutionLogDialog';
import { JobExecutionsDialog as SharedJobExecutionsDialog } from '@/features/automation/components/JobExecutionsDialog';
import { SessionViewerDialog } from '@/features/workspace/components/session-viewer/SessionViewerDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { getExecutionStatusLabelKey } from '../constants';
import { TaskLog } from '@/shared/types/task';
import { resolvePreferredWorkspaceUrl } from '@/features/workspace/services/workspacePublicUrl';

const STATUS_COLORS: Record<string, string> = {
  active: 'text-emerald-500',
  paused: 'text-amber-500',
  failed: 'text-rose-500',
  draft: 'text-muted-foreground',
};

const JOBS_PER_PAGE = 6;
const EXECUTIONS_PER_PAGE = 6;

export const AutomationDashboard: React.FC = () => {
  const { state, setSearch, refresh, openCreateDialog, openEditDialog, executeTask, deleteTask } = useAutomation();
  const [selectedExecution, setSelectedExecution] = useState<JobExecution | null>(null);
  const [isLogDialogOpen, setIsLogDialogOpen] = useState(false);
  const [isSessionDialogOpen, setIsSessionDialogOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<AutomationJob | null>(null);
  const [isJobExecutionsDialogOpen, setIsJobExecutionsDialogOpen] = useState(false);
  const [runtimeBaseUrl, setRuntimeBaseUrl] = useState<string | undefined>(undefined);
  const [jobPage, setJobPage] = useState(1);
  const [executionPage] = useState(1);

  const {
    t,
    state: { currentLanguage },
  } = useI18n();

  const locale = currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';

  const executionLogDialogCopy = useMemo<ExecutionLogDialogCopy<JobExecution>>(
    () => ({
      description: t('automation.dashboard.dialogs.executionLog.description'),
      fields: {
        executionId: t('automation.dashboard.dialogs.executionLog.fields.executionId'),
        jobId: t('automation.dashboard.dialogs.executionLog.fields.jobId'),
        startedAt: t('automation.dashboard.dialogs.executionLog.fields.startedAt'),
        finishedAt: t('automation.dashboard.dialogs.executionLog.fields.finishedAt'),
        trigger: t('automation.dashboard.dialogs.executionLog.fields.trigger'),
        duration: t('automation.dashboard.dialogs.executionLog.fields.duration'),
      },
      statusLabel: status => t(getExecutionStatusLabelKey(status)),
      formatTrigger: executionItem => t(`automation.form.trigger.${executionItem.trigger}`),
      formatDuration: executionItem =>
        typeof executionItem.duration === 'number'
          ? t('automation.dashboard.dialogs.executionLog.durationSeconds', { seconds: executionItem.duration })
          : null,
      logs: {
        title: t('automation.dashboard.dialogs.executionLog.logs.title'),
        empty: t('automation.dashboard.dialogs.executionLog.logs.empty'),
        loading: t('automation.dashboard.dialogs.executionLog.logs.loading'),
        reload: t('automation.dashboard.dialogs.executionLog.logs.reload'),
        filters: {
          all: t('automation.dashboard.dialogs.executionLog.logs.filters.all'),
          info: t('automation.dashboard.dialogs.executionLog.logs.filters.info'),
          error: t('automation.dashboard.dialogs.executionLog.logs.filters.error'),
          warning: t('automation.dashboard.dialogs.executionLog.logs.filters.warning'),
          success: t('automation.dashboard.dialogs.executionLog.logs.filters.success'),
        },
      },
    }),
    [t]
  );

  const buildExecutionLogs = useCallback<ExecutionLogBuilder<JobExecution>>(
    executionItem => {
      const startTime = executionItem.startedAt
        ? new Date(executionItem.startedAt).getTime()
        : Date.now();
      const offset = (minutes: number) => new Date(startTime + minutes * 60_000).toISOString();

      const baseLogs: TaskLog[] = [
        {
          timestamp: offset(0),
          level: 'INFO',
          message: t('automation.dashboard.dialogs.executionLog.mock.start', {
            taskId: executionItem.jobId,
            trigger: executionItem.trigger,
          }),
        },
        {
          timestamp: offset(0.5),
          level: 'INFO',
          message: t('automation.dashboard.dialogs.executionLog.mock.loadEnvironment'),
        },
        {
          timestamp: offset(1.2),
          level: 'INFO',
          message: executionItem.summary,
        },
      ];

      if (executionItem.status === 'failed') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'ERROR',
          message: t('automation.dashboard.dialogs.executionLog.mock.failureDetected'),
        });
      }

      if (executionItem.status === 'success') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'SUCCESS',
          message: t('automation.dashboard.dialogs.executionLog.mock.completed'),
        });
      }

      if (executionItem.status === 'running' || executionItem.status === 'queued') {
        baseLogs.push({
          timestamp: offset(1.5),
          level: 'INFO',
          message:
            executionItem.status === 'running'
              ? t('automation.dashboard.dialogs.executionLog.mock.running')
              : t('automation.dashboard.dialogs.executionLog.mock.queued'),
        });
      }

      return baseLogs;
    },
    [t]
  );

  const handleViewLog = useCallback((execution: JobExecution) => {
    setSelectedExecution(execution);
    setIsLogDialogOpen(true);
  }, []);

  const handleCloseLog = useCallback(() => {
    setIsLogDialogOpen(false);
    setSelectedExecution(null);
  }, []);

  const handleViewSession = useCallback(async (execution: JobExecution) => {
    setSelectedExecution(execution);

    // 獲取 workspace runtime URL
    const job = state.automationJobs.find(j => j.id === execution.jobId);
    if (!job?.workspaceId) {
      logger.warn('Execution has no workspaceId', { execution });
      alert(t('common.messages.executionNoWorkspace'));
      return;
    }

    try {
      logger.debug('Fetching workspace detail for session', { workspaceId: job.workspaceId });
      interface WorkspaceRuntimeStatus {
        internalUrl?: string | null;
        externalUrl?: string | null;
      }

      interface WorkspaceDetailResponse {
        id: string;
        name: string;
        runtimeStatus?: WorkspaceRuntimeStatus;
      }

      const detail = await apiClient.get<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(job.workspaceId)}`
      );

      logger.debug('Runtime Status for session', { runtimeStatus: detail.runtimeStatus });

      const url = resolvePreferredWorkspaceUrl(
        detail.runtimeStatus?.externalUrl,
        detail.runtimeStatus?.internalUrl
      );

      logger.debug('Final Runtime URL for session', { url });

      if (!url) {
        throw new Error(t('common.messages.workspaceRuntimeNotStarted'));
      }

      setRuntimeBaseUrl(url);
      setIsSessionDialogOpen(true);
    } catch (error) {
      logger.error('Failed to fetch workspace runtime URL for session', { error });
      const errorMsg = error instanceof Error ? error.message : t('common.messages.unknownError');
      alert(t('common.messages.cannotViewSession', { error: errorMsg }));
      setRuntimeBaseUrl(undefined);
    }
  }, [state.automationJobs, t]);

  const handleCloseSession = useCallback(() => {
    setIsSessionDialogOpen(false);
    setSelectedExecution(null);
  }, []);

  const handleViewJobExecutions = useCallback(async (job: AutomationJob) => {
    setSelectedJob(job);
    setIsJobExecutionsDialogOpen(true);

    // 獲取 workspace runtime URL（參考 WorkspaceProvider 的實作）
    if (job.workspaceId) {
      try {
        logger.debug('Fetching workspace detail for', { workspaceId: job.workspaceId });
        interface WorkspaceRuntimeStatus {
          internalUrl?: string | null;
          externalUrl?: string | null;
        }

        interface WorkspaceDetailResponse {
          id: string;
          name: string;
          runtimeStatus?: WorkspaceRuntimeStatus;
        }

        const detail = await apiClient.get<WorkspaceDetailResponse>(
          `/workspaces/${encodeURIComponent(job.workspaceId)}`
        );

        logger.debug('Runtime Status', { runtimeStatus: detail.runtimeStatus });

        const url = resolvePreferredWorkspaceUrl(
          detail.runtimeStatus?.externalUrl,
          detail.runtimeStatus?.internalUrl
        );

        logger.debug('Final Runtime URL', { url });

        if (!url) {
          throw new Error('Workspace Runtime 尚未啟動或尚未提供 URL');
        }

        setRuntimeBaseUrl(url);
      } catch (error) {
        logger.error('Failed to fetch workspace runtime URL', { error });
        setRuntimeBaseUrl(undefined);
      }
    } else {
      logger.warn('Job has no workspaceId', { job });
      setRuntimeBaseUrl(undefined);
    }
  }, []);

  const handleCloseJobExecutions = useCallback(() => {
    setIsJobExecutionsDialogOpen(false);
    setSelectedJob(null);
    setRuntimeBaseUrl(undefined);
  }, []);

  const filteredJobs = useMemo(() => {
    return state.automationJobs.filter(job => {
      const matchFilter = state.filter === 'all' ? true : job.status === state.filter;
      const matchSearch = state.search.trim().length === 0
        ? true
        : job.name.toLowerCase().includes(state.search.toLowerCase())
          || job.description.toLowerCase().includes(state.search.toLowerCase())
          || job.owner.toLowerCase().includes(state.search.toLowerCase());
      return matchFilter && matchSearch;
    });
  }, [state.automationJobs, state.filter, state.search]);

  const jobTotalItems = filteredJobs.length;
  const jobTotalPages = Math.max(1, Math.ceil(jobTotalItems / JOBS_PER_PAGE));

  useEffect(() => {
    setJobPage(1);
  }, [state.filter, state.search]);

  useEffect(() => {
    if (jobPage > jobTotalPages) {
      setJobPage(jobTotalPages);
    }
  }, [jobPage, jobTotalPages]);

  const paginatedJobs = useMemo(() => {
    const start = (jobPage - 1) * JOBS_PER_PAGE;
    return filteredJobs.slice(start, start + JOBS_PER_PAGE);
  }, [filteredJobs, jobPage]);

  const handleJobPageChange = useCallback((page: number) => {
    setJobPage(Math.min(Math.max(page, 1), jobTotalPages));
  }, [jobTotalPages]);

  const handleEditJob = useCallback((jobId: string) => {
    openEditDialog(jobId);
  }, [openEditDialog]);

  const handleExecuteJob = useCallback(async (job: AutomationJob) => {
    try {
      await executeTask(job.id);
    } catch (error) {
      logger.error('Failed to execute scheduler job immediately', { error, jobId: job.id });
    }
  }, [executeTask]);

  const handleDeleteJob = useCallback(async (job: AutomationJob) => {
    const confirmed = window.confirm(t('automation.dashboard.table.confirmDelete', { name: job.name }));
    if (!confirmed) {
      return;
    }
    await deleteTask(job.id);
  }, [deleteTask, t]);

  const groupedExecutions = useMemo(() => {
    const running = state.jobExecutions.filter(exec => exec.status === 'running');
    const upcoming = state.jobExecutions.filter(exec => exec.status === 'queued');
    const recent = state.jobExecutions.filter(exec => exec.status === 'success' || exec.status === 'failed');
    return { running, upcoming, recent };
  }, [state.jobExecutions]);

  const jobExecutions = useMemo(() => {
    if (!selectedJob) return [];

    return state.jobExecutions.filter(execution => {
      return execution.jobId === selectedJob.id;
    });
  }, [selectedJob, state.jobExecutions]);

  const paginatedExecutions = useMemo(() => {
    const start = (executionPage - 1) * EXECUTIONS_PER_PAGE;
    return jobExecutions.slice(start, start + EXECUTIONS_PER_PAGE);
  }, [jobExecutions, executionPage]);

  const metricCards = useMemo(() => {
    const durationLabel = state.metrics
      ? t('automation.sidebar.summary.seconds', {
          value: Math.round(state.metrics.averageDuration),
        })
      : '--';

    return [
      {
        key: 'active',
        title: t('automation.dashboard.metrics.active.title'),
        value: state.metrics?.activeCount ?? '--',
        subtitle: t('automation.dashboard.metrics.active.subtitle'),
        icon: CheckCircle2,
        iconWrapper: 'bg-emerald-500/15 text-emerald-500',
        valueClass: 'text-emerald-500',
        aura: 'bg-emerald-500/20 opacity-60 blur-3xl',
      },
      {
        key: 'paused',
        title: t('automation.dashboard.metrics.paused.title'),
        value: state.metrics?.pausedCount ?? '--',
        subtitle: t('automation.dashboard.metrics.paused.subtitle'),
        icon: PauseCircle,
        iconWrapper: 'bg-amber-500/15 text-amber-500',
        valueClass: 'text-amber-500',
        aura: 'bg-amber-500/20 opacity-60 blur-3xl',
      },
      {
        key: 'failed',
        title: t('automation.dashboard.metrics.failed.title'),
        value: state.metrics?.failedCount ?? '--',
        subtitle: t('automation.dashboard.metrics.failed.subtitle'),
        icon: AlertTriangle,
        iconWrapper: 'bg-rose-500/15 text-rose-500',
        valueClass: 'text-rose-500',
        aura: 'bg-rose-500/20 opacity-60 blur-3xl',
      },
      {
        key: 'duration',
        title: t('automation.dashboard.metrics.duration.title'),
        value: durationLabel,
        subtitle: t('automation.dashboard.metrics.duration.subtitle'),
        icon: Timer,
        iconWrapper: 'bg-sky-500/15 text-sky-500',
        valueClass: 'text-foreground',
        aura: 'bg-sky-500/20 opacity-60 blur-3xl',
      },
    ];
  }, [state.metrics, t]);

  const failureRateValue = state.metrics
    ? `${Math.max(0, 100 - Math.round(state.metrics.successRate * 100))}%`
    : '--';
  const failureRateLabel = t('automation.dashboard.info.failureRate', { rate: failureRateValue });
  const taskCountLabel = t('automation.dashboard.info.taskCount', { count: state.automationJobs.length });

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('automation.dashboard.title')}
        icon={Clock}
        actions={(
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => refresh()} className="h-7 px-2 text-xs gap-1.5">
              <RefreshCw className="h-3.5 w-3.5" />
              {t('automation.dashboard.actions.refresh')}
            </Button>
            <Button size="sm" className="h-7 px-2 text-xs gap-1.5" onClick={openCreateDialog} disabled={state.creating}>
              <Plus className="h-3.5 w-3.5" />
              {t('automation.dashboard.actions.create')}
            </Button>
          </div>
        )}
        info={(
          <div className="hidden md:flex items-center gap-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
              {failureRateLabel}
            </div>
            <div className="flex items-center gap-1">
              <UserCircle className="h-3.5 w-3.5" />
              {taskCountLabel}
            </div>
          </div>
        )}
      />

      <div className="flex-1 overflow-hidden">
        <div className="h-full flex flex-col xl:flex-row">
          <section className="flex-1 overflow-hidden">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-6">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {metricCards.map(card => {
                    const Icon = card.icon;
                    return (
                      <Card key={card.key} className="relative overflow-hidden border border-border/50 bg-card/90 shadow-sm">
                        <div className={`pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full ${card.aura}`} />
                        <CardContent className="relative p-5">
                          <div className="flex items-center justify-between">
                            <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${card.iconWrapper}`}>
                              <Icon className="h-6 w-6" />
                            </div>
                            <span className={`text-3xl font-semibold ${card.valueClass}`}>{card.value}</span>
                          </div>
                          <div className="mt-4">
                            <p className="text-sm font-medium text-foreground">{card.title}</p>
                            <p className="mt-1 text-xs text-muted-foreground">{card.subtitle}</p>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>

                <Card className="bg-card/80">
                  <CardHeader className="flex flex-col gap-4 bg-muted/40 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <CardTitle className="text-base font-semibold">{t('automation.dashboard.table.title')}</CardTitle>
                      <p className="text-xs text-muted-foreground">{t('automation.dashboard.table.subtitle')}</p>
                    </div>
                  </CardHeader>
                  <CardContent className="px-0">
                    <div className="px-4 space-y-4">
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                          <Input
                            placeholder={t('automation.dashboard.search.placeholder')}
                            className="pl-9 h-9"
                            value={state.search}
                            onChange={event => setSearch(event.target.value)}
                          />
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-9 px-4 gap-2"
                          onClick={() => {
                            /* search handled via controlled input */
                          }}
                        >
                          <Search className="h-4 w-4" />
                          {t('automation.dashboard.search.submit')}
                        </Button>
                      </div>
                      <JobTable
                        jobs={paginatedJobs}
                        page={jobPage}
                        totalPages={jobTotalPages}
                        totalItems={jobTotalItems}
                        pageSize={JOBS_PER_PAGE}
                        onPageChange={handleJobPageChange}
                        onEdit={handleEditJob}
                        onExecute={handleExecuteJob}
                        onDelete={handleDeleteJob}
                        onViewExecutions={handleViewJobExecutions}
                      />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </ScrollArea>
          </section>

          <aside className="w-full shrink-0 border-t border-border/60 bg-card/70 xl:w-80 xl:border-l xl:border-t-0">
            <div className="px-5 py-4 border-b border-border/60 bg-muted/40">
              <div className="flex items-center gap-2">
                <AlarmClock className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">{t('automation.dashboard.upcoming.title')}</h3>
              </div>
              <p className="mt-1 pl-6 text-xs text-muted-foreground">{t('automation.dashboard.upcoming.subtitle')}</p>
            </div>
            <ScrollArea className="h-[320px] xl:h-full">
              <div className="px-5 py-4 space-y-4">
                {groupedExecutions.upcoming.length === 0 && groupedExecutions.running.length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t('automation.dashboard.upcoming.none')}</p>
                ) : (
                  <div className="space-y-4">
                    {groupedExecutions.running.map(execution => (
                      <ExecutionCard key={execution.id} execution={execution} onViewLog={handleViewLog} onViewSession={handleViewSession} />
                    ))}
                    {groupedExecutions.upcoming.map(execution => (
                      <ExecutionCard key={execution.id} execution={execution} onViewLog={handleViewLog} onViewSession={handleViewSession} />
                    ))}
                  </div>
                )}

                <div className="border-t border-border/40 pt-4">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">{t('automation.dashboard.upcoming.recentTitle')}</h4>
                  <div className="space-y-3">
                    {groupedExecutions.recent.slice(0, 3).map(execution => (
                      <ExecutionCard key={execution.id} execution={execution} onViewLog={handleViewLog} onViewSession={handleViewSession} />
                    ))}
                  </div>
                </div>
              </div>
            </ScrollArea>
          </aside>
        </div>
      </div>
      <SharedExecutionLogDialog
        isOpen={isLogDialogOpen}
        execution={selectedExecution}
        onClose={handleCloseLog}
        locale={locale}
        copy={executionLogDialogCopy}
        createLogs={buildExecutionLogs}
      />

      <SharedJobExecutionsDialog
        isOpen={isJobExecutionsDialogOpen}
        job={selectedJob}
        executions={paginatedExecutions}
        onClose={handleCloseJobExecutions}
        runtimeBaseUrl={runtimeBaseUrl}
      />

      {selectedExecution?.sessionId && (
        <SessionViewerDialog
          isOpen={isSessionDialogOpen}
          onClose={handleCloseSession}
          sessionId={selectedExecution.sessionId}
          workspaceId={state.automationJobs.find(job => job.id === selectedExecution.jobId)?.workspaceId || ''}
          runtimeBaseUrl={runtimeBaseUrl || ''}
        />
      )}
    </div>
  );
};

interface JobTableProps {
  jobs: AutomationJob[];
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onEdit: (jobId: string) => void;
  onExecute: (job: AutomationJob) => void | Promise<void>;
  onDelete: (job: AutomationJob) => void | Promise<void>;
  onViewExecutions: (job: AutomationJob) => void;
}

const JobTable: React.FC<JobTableProps> = ({ jobs, page, totalPages, totalItems, pageSize, onPageChange, onEdit, onExecute, onDelete, onViewExecutions }) => {
  const { t, state: { currentLanguage } } = useI18n();

  return (
    <div className="rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border/40">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.name')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.schedule')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.nextRun')}
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.status')}
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.view')}
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                {t('automation.dashboard.table.headers.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30 bg-background/40">
            {jobs.map(job => (
              <tr key={job.id}>
                <td className="px-4 py-3 align-top">
                  <div className="text-sm font-medium text-foreground">{job.name}</div>
                  {job.workspaceName && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      <span className="inline-flex items-center gap-1">
                        <span className="text-muted-foreground/60">工作區:</span>
                        <span className="font-medium">{job.workspaceName}</span>
                      </span>
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">{job.description}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {job.tags.map(tag => (
                      <Badge key={tag} variant="outline" className="text-[11px]">
                        <Tag className="mr-1 h-3 w-3" />
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  <div className="font-medium text-sm">
                    {job.trigger === 'manual'
                      ? t(`automation.form.trigger.${job.trigger}`)
                      : job.trigger === 'webhook'
                      ? t(`automation.form.trigger.${job.trigger}`)
                      : job.schedule || t('automation.dashboard.table.noScheduled')}
                  </div>
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  <div>
                    {job.nextRunAt
                      ? t('automation.dashboard.table.nextRunLabel', {
                          value: new Date(job.nextRunAt).toLocaleString(currentLanguage),
                        })
                      : t('automation.dashboard.table.noScheduled')}
                  </div>
                  {job.lastRunAt && (
                    <div className="mt-1">
                      {t('automation.dashboard.table.lastRunLabel', {
                        value: new Date(job.lastRunAt).toLocaleString(currentLanguage),
                      })}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-xs">
                  <span className={`font-semibold ${STATUS_COLORS[job.status] ?? ''}`}>
                    {t(`automation.dashboard.table.status.${job.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 align-top text-center">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 px-3 text-xs"
                    onClick={() => onViewExecutions(job)}
                  >
                    <History className="h-3.5 w-3.5 mr-1" />
                    {t('automation.dashboard.table.viewTask')}
                  </Button>
                </td>
                <td className="px-4 py-3 align-top text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem onClick={() => onEdit(job.id)} className="gap-2 text-xs">
                          <Pencil className="h-3.5 w-3.5" />
                          {t('automation.dashboard.table.edit')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onExecute(job)} className="gap-2 text-xs">
                          <PlayCircle className="h-3.5 w-3.5" />
                          {t('automation.dashboard.table.runNow')}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => onDelete(job)}
                          className="gap-2 text-xs text-destructive focus:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        {t('automation.dashboard.table.delete')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {t('automation.dashboard.table.empty')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <PaginationFooter
        page={page}
        totalPages={totalPages}
        pageSize={pageSize}
        totalItems={totalItems}
        onPageChange={onPageChange}
      />
    </div>
  );
};



interface ExecutionCardProps {
  execution: JobExecution;
  onViewLog?: (execution: JobExecution) => void;
  onViewSession?: (execution: JobExecution) => void;
}

const ExecutionCard: React.FC<ExecutionCardProps> = ({ execution, onViewLog, onViewSession }) => {
  const {
    t,
    state: { currentLanguage },
  } = useI18n();
  const statusLabel = t(getExecutionStatusLabelKey(execution.status));

  const handleViewLog = () => {
    if (onViewLog) {
      onViewLog(execution);
    }
  };

  const handleViewSession = () => {
    if (onViewSession) {
      onViewSession(execution);
    }
  };

  return (
    <div className="rounded-lg border border-border/40 bg-background/70 p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-muted-foreground">{statusLabel}</div>
        <div className="text-[11px] text-muted-foreground">
          {execution.startedAt
            ? new Date(execution.startedAt).toLocaleString(currentLanguage)
            : t('automation.dashboard.executionCard.notStarted')}
        </div>
      </div>
      <p className="mt-2 text-sm text-foreground" title={execution.summary}>{execution.summary}</p>
      <div className="mt-3 flex flex-col gap-2 text-[11px] text-muted-foreground">
        {/* 第一行：觸發方式和耗時 */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>{t('automation.dashboard.executionCard.trigger', { trigger: t(`automation.form.trigger.${execution.trigger}`) })}</span>
          {execution.duration && (
            <span>{t('automation.dashboard.executionCard.duration', { seconds: execution.duration })}</span>
          )}
        </div>
        {/* 第二行：操作按鈕（靠右對齊） */}
        <div className="flex gap-2 justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-3 text-[11px] font-medium text-primary"
            onClick={handleViewLog}
          >
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            {t('automation.dashboard.executionCard.viewLogs')}
          </Button>
          {execution.sessionId && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-3 text-[11px] font-medium text-primary"
              onClick={handleViewSession}
            >
              <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
              {t('automation.dashboard.executionCard.viewSession')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

interface PaginationFooterProps {
  page: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
}

const PaginationFooter: React.FC<PaginationFooterProps> = ({ page, totalPages, pageSize, totalItems, onPageChange }) => {
  const { t } = useI18n();
  const safeTotalPages = Math.max(1, totalPages);
  const currentPage = Math.min(page, safeTotalPages);
  const hasData = totalItems > 0;
  const startItem = hasData ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = hasData ? Math.min(currentPage * pageSize, totalItems) : 0;
  const disablePrev = !hasData || currentPage <= 1;
  const disableNext = !hasData || currentPage >= safeTotalPages;

  const handlePrev = () => {
    if (!disablePrev) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (!disableNext) {
      onPageChange(currentPage + 1);
    }
  };

  return (
    <div className="flex flex-col gap-3 border-t border-border/40 bg-background/60 px-4 py-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <span>
        {hasData
          ? t('automation.dashboard.pagination.summary', { start: startItem, end: endItem, total: totalItems })
          : t('automation.dashboard.pagination.empty')}
      </span>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handlePrev}
          disabled={disablePrev}
        >
          {t('automation.dashboard.pagination.previous')}
        </Button>
        <span>{t('automation.dashboard.pagination.page', { current: currentPage, total: safeTotalPages })}</span>
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handleNext}
          disabled={disableNext}
        >
          {t('automation.dashboard.pagination.next')}
        </Button>
      </div>
    </div>
  );
};

export default AutomationDashboard;
