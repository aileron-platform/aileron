/**
 * AutomationDashboardPage - Automation center main view
 */

import React, { useCallback, useMemo, useState } from 'react';
import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('AutomationDashboardPage');
import {
  Clock,
  RefreshCw,
  Plus,
  Search,
  ShieldAlert,
  UserCircle,
  AlarmClock,
  CheckCircle2,
  PauseCircle,
  AlertTriangle,
  Timer,
  Eye,
} from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';

import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useAutomation } from '../providers/AutomationProvider';
import type { AutomationJob, JobExecution } from '../model/automationTypes';
import { JobExecutionsDialog as SharedJobExecutionsDialog } from '../components/execution/JobExecutionsDialog';
import { ExecutionDetailDialog } from '../components/execution/ExecutionDetailDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { getAutomationRunErrorKey, getExecutionStatusLabelKey } from '../model/automationStatusModel';
import { useToast } from '@/shared/components/ui/use-toast';
import { useAutomationJobPagination } from '../hooks/useAutomationJobPagination';
import { AutomationJobTable } from '../components/AutomationJobTable';
import { resolveWorkspacePermissions } from '@/features/workspace/public';

export const AutomationDashboardPage: React.FC = () => {
  const { state, setSearch, refresh, openCreateDialog, openEditDialog, executeTask, deleteTask } = useAutomation();
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [isExecutionDetailOpen, setIsExecutionDetailOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<AutomationJob | null>(null);
  const [isJobExecutionsDialogOpen, setIsJobExecutionsDialogOpen] = useState(false);
  const [runtimeBaseUrl, setRuntimeBaseUrl] = useState<string | undefined>(undefined);
  const [canUseAgentChat, setCanUseAgentChat] = useState(false);

  const { t } = useI18n();
  const { toast } = useToast();

  const handleViewExecution = useCallback(async (executionId: string) => {
    setSelectedExecutionId(executionId);
    setIsExecutionDetailOpen(true);
    setRuntimeBaseUrl(undefined);
    setCanUseAgentChat(false);
    const execution = state.jobExecutions.find(item => item.id === executionId);
    const workspaceId = execution?.workspaceId ?? selectedJob?.workspaceId;
    if (!workspaceId) return;
    try {
      interface WorkspaceDetailResponse {
        id: string;
        name: string;
        runtimeStatus: {
          runtimeUrl: string;
        };
        accessRole?: unknown;
        allowedOperations?: unknown;
      }

      const detail = await apiClient.get<WorkspaceDetailResponse>(
        `/workspaces/${encodeURIComponent(workspaceId)}`
      );
      setRuntimeBaseUrl(detail.runtimeStatus.runtimeUrl);
      setCanUseAgentChat(resolveWorkspacePermissions(
        detail.accessRole,
        detail.allowedOperations,
      ).canUseChat);
    } catch (error) {
      logger.error('Failed to resolve execution Runtime URL', { error, executionId, workspaceId });
      setRuntimeBaseUrl(undefined);
    }
  }, [selectedJob?.workspaceId, state.jobExecutions]);

  const handleViewJobExecutions = useCallback((job: AutomationJob) => {
    setSelectedJob(job);
    setIsJobExecutionsDialogOpen(true);
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
          || (job.description ?? '').toLowerCase().includes(state.search.toLowerCase())
          || job.creatorDisplayName.toLowerCase().includes(state.search.toLowerCase());
      return matchFilter && matchSearch;
    });
  }, [state.automationJobs, state.filter, state.search]);

  const jobPagination = useAutomationJobPagination(
    filteredJobs,
    `${state.filter}:${state.search}`,
  );

  const handleEditJob = useCallback((jobId: string) => {
    openEditDialog(jobId);
  }, [openEditDialog]);

  const handleExecuteJob = useCallback(async (job: AutomationJob) => {
    try {
      await executeTask(job.id);
    } catch (error) {
      logger.error('Failed to execute automation job immediately', { error, jobId: job.id });
      toast({
        variant: 'destructive',
        title: t('automation.errors.runTitle'),
        description: t(getAutomationRunErrorKey(error)),
      });
    }
  }, [executeTask, t, toast]);

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
                      <AutomationJobTable
                        scope="global"
                        jobs={jobPagination.paginatedJobs}
                        page={jobPagination.page}
                        totalPages={jobPagination.totalPages}
                        totalItems={jobPagination.totalItems}
                        pageSize={jobPagination.pageSize}
                        onPageChange={jobPagination.onPageChange}
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
                      <ExecutionCard key={execution.id} execution={execution} onViewExecution={handleViewExecution} />
                    ))}
                    {groupedExecutions.upcoming.map(execution => (
                      <ExecutionCard key={execution.id} execution={execution} onViewExecution={handleViewExecution} />
                    ))}
                  </div>
                )}

                <div className="border-t border-border/40 pt-4">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">{t('automation.dashboard.upcoming.recentTitle')}</h4>
                  <div className="space-y-3">
                    {groupedExecutions.recent.slice(0, 3).map(execution => (
                      <ExecutionCard key={execution.id} execution={execution} onViewExecution={handleViewExecution} />
                    ))}
                  </div>
                </div>
              </div>
            </ScrollArea>
          </aside>
        </div>
      </div>
      <SharedJobExecutionsDialog
        isOpen={isJobExecutionsDialogOpen}
        job={selectedJob}
        onClose={handleCloseJobExecutions}
        onViewExecution={handleViewExecution}
      />

      <ExecutionDetailDialog
        open={isExecutionDetailOpen}
        executionId={selectedExecutionId}
        runtimeBaseUrl={runtimeBaseUrl}
        canUseAgentChat={canUseAgentChat}
        onOpenChange={open => {
          setIsExecutionDetailOpen(open);
          if (!open) {
            setSelectedExecutionId(null);
            setRuntimeBaseUrl(undefined);
          }
        }}
      />
    </div>
  );
};

interface ExecutionCardProps {
  execution: JobExecution;
  onViewExecution(executionId: string): void;
}

const ExecutionCard: React.FC<ExecutionCardProps> = ({ execution, onViewExecution }) => {
  const {
    t,
    state: { currentLanguage },
  } = useI18n();
  const statusLabel = t(getExecutionStatusLabelKey(execution.status));

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
      <div className="mt-3 flex flex-col gap-2 text-[11px] text-muted-foreground">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span>{t('automation.dashboard.executionCard.trigger', { trigger: t(`automation.form.trigger.${execution.trigger}`) })}</span>
        </div>
        <div className="flex gap-2 justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-3 text-[11px] font-medium text-primary"
            onClick={() => onViewExecution(execution.id)}
          >
            <Eye className="mr-1.5 h-3.5 w-3.5" />
            {t('automation.dashboard.executionCard.viewExecution')}
          </Button>
        </div>
      </div>
    </div>
  );
};
