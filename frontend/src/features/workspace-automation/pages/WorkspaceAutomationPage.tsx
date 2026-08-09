import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceAutomationPage');
import {
  Cpu,
  RefreshCw,
  Search,
  ShieldAlert,
  UserCircle,
  CheckCircle2,
  AlertTriangle,
  Timer,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Card, CardContent } from '@/shared/components/ui/card';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import type {
  AutomationJob,
  AutomationMetrics,
  JobUpdateInput,
} from '../model/automationTypes';
import { JobExecutionsDialog } from '../components/execution/JobExecutionsDialog';
import { ExecutionDetailDialog } from '../components/execution/ExecutionDetailDialog';
import { AutomationJobEditDialog } from '../components/job-form/AutomationJobEditDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '../api/automationApi';
import { automationWorkspaceApi } from '../api/automationWorkspaceApi';
import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { useToast } from '@/shared/components/ui/use-toast';
import { getAutomationRunErrorKey } from '../model/automationStatusModel';
import { useAutomationJobPagination } from '../hooks/useAutomationJobPagination';
import type { AutomationWorkspaceSummary } from '../model/automationTypes';
import { AutomationJobTable } from '../components/AutomationJobTable';

interface WorkspaceAutomationPageProps {
  workspaceId: string | null;
  runtimeBaseUrl: string | null;
  isRuntimeLoading: boolean;
  locale: 'zh-TW' | 'en-US';
  canUseAgentChat: boolean;
}

export const WorkspaceAutomationPage: React.FC<WorkspaceAutomationPageProps> = ({
  workspaceId,
  runtimeBaseUrl,
  isRuntimeLoading,
  locale,
  canUseAgentChat,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [jobs, setJobs] = useState<AutomationJob[]>([]);
  const [metrics, setMetrics] = useState<AutomationMetrics | null>(null);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<AutomationJob | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [isExecutionDetailOpen, setIsExecutionDetailOpen] = useState(false);

  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AutomationJob | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [workspaces, setWorkspaces] = useState<AutomationWorkspaceSummary[]>([]);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!workspaceId) {
      setJobs([]);
      setMetrics(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const jobList = await automationApi.listJobs(workspaceId);
      setJobs(jobList);

      try {
        const stats = await automationApi.getMetrics(workspaceId);
        setMetrics(stats);
      } catch (metricsError) {
        logger.warn('Failed to load task metrics; using default values', { error: metricsError });
        setMetrics({
          activeCount: jobList.filter(job => job.status === 'active').length,
          pausedCount: jobList.filter(job => job.status === 'paused').length,
          failedCount: 0,
          draftCount: 0,
          successRate: 0,
          runningExecutions: 0,
          queuedExecutions: 0,
          averageDuration: 0,
        });
      }
    } catch (error) {
      logger.error('Failed to load workspace automation data', { error });
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (isRuntimeLoading) {
      setIsLoading(true);
      return;
    }

    void loadData();
  }, [isRuntimeLoading, loadData]);

  const handleRefresh = useCallback(() => {
    void loadData();
  }, [loadData]);

  const filteredJobs = useMemo(() => {
    return jobs.filter(job => {
      const matchSearch = search.trim().length === 0
        ? true
        : job.name.toLowerCase().includes(search.toLowerCase())
          || (job.description ?? '').toLowerCase().includes(search.toLowerCase())
          || job.creatorDisplayName.toLowerCase().includes(search.toLowerCase());
      return matchSearch;
    });
  }, [jobs, search]);

  const jobPagination = useAutomationJobPagination(filteredJobs, search);

  const handleViewJobExecutions = useCallback((job: AutomationJob) => {
    setSelectedJob(job);
    setIsDialogOpen(true);
  }, []);

  const handleEditJob = useCallback((jobId: string) => {
    setIsEditDialogOpen(true);
    setEditLoading(true);
    setEditingTask(null);

    void (async () => {
      try {
        const job = await automationApi.getJob(jobId);
        setEditingTask(job);
      } catch (error) {
        logger.error('Failed to load job', { error });
        setIsEditDialogOpen(false);
      } finally {
        setEditLoading(false);
      }
    })();
  }, []);

  const handleExecuteJob = useCallback(async (job: AutomationJob) => {
    try {
      await automationApi.executeJob(job.id);
      await loadData();
    } catch (error) {
      logger.error('Failed to execute job', { error });
      toast({
        variant: 'destructive',
        title: t('automation.errors.runTitle'),
        description: t(getAutomationRunErrorKey(error)),
      });
    }
  }, [loadData, t, toast]);

  const handleDeleteJob = useCallback(async (job: AutomationJob) => {
    const confirmed = window.confirm(
      t('workspace.automation.confirmations.delete', { name: job.name }),
    );
    if (!confirmed) {
      return;
    }
    try {
      await automationApi.deleteJob(job.id);
      await loadData();
    } catch (error) {
      logger.error('Failed to delete job', { error });
    }
  }, [loadData, t]);

  useEffect(() => {
    if (!isEditDialogOpen) {
      setWorkspaces([]);
      return;
    }

    const controller = new AbortController();
    const selectedId = editingTask?.workspaceId ?? null;

    void (async () => {
      try {
        const items = await automationWorkspaceApi.list(controller.signal);
        if (controller.signal.aborted) return;

        let resolvedItems = items;
        if (selectedId && !items.some(item => item.id === selectedId)) {
          resolvedItems = [...items, { id: selectedId, name: selectedId }];
        }
        setWorkspaces(resolvedItems);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load workspaces', { error });
        setWorkspaces([]);
      }
    })();

    return () => controller.abort();
  }, [editingTask?.workspaceId, isEditDialogOpen]);

  useEffect(() => {
    if (!isEditDialogOpen || !editingTask?.workspaceId) {
      setCommands([]);
      setCommandsLoading(false);
      return;
    }

    const controller = new AbortController();
    setCommandsLoading(true);

    void (async () => {
      try {
        const items = await automationWorkspaceApi.listSlashCommands(
          editingTask.workspaceId,
          controller.signal
        );
        if (controller.signal.aborted) return;
        setCommands(items);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error('Failed to load slash commands', { error });
        setCommands([]);
      } finally {
        if (!controller.signal.aborted) {
          setCommandsLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [editingTask?.workspaceId, isEditDialogOpen]);

  const handleSaveEdit = useCallback(async (payload: JobUpdateInput) => {
    setSaving(true);
    try {
      await automationApi.updateJob(payload);
      setIsEditDialogOpen(false);
      setEditingTask(null);
      await loadData();
    } catch (error) {
      logger.error('Failed to update task', { error });
      throw error;
    } finally {
      setSaving(false);
    }
  }, [loadData]);

  const handleCloseEditDialog = useCallback(() => {
    setIsEditDialogOpen(false);
    setEditingTask(null);
  }, []);

  const metricCards = useMemo(() => {
    const totalExecutions = jobs.reduce((sum, job) => sum + job.totalExecutions, 0);
    const successfulExecutions = jobs.reduce((sum, job) => sum + Math.round(job.totalExecutions * job.successRate), 0);
    const failedExecutions = totalExecutions - successfulExecutions;
    const overallSuccessRate = totalExecutions > 0 ? Math.round((successfulExecutions / totalExecutions) * 100) : 0;

    return [
      {
        key: 'total',
        title: t('workspace.automation.metrics.totalExecutions'),
        value: totalExecutions,
        icon: CheckCircle2,
        iconWrapper: 'bg-blue-500/15 text-blue-500',
        valueClass: 'text-blue-600',
      },
      {
        key: 'successful',
        title: t('workspace.automation.metrics.successfulExecutions'),
        value: successfulExecutions,
        icon: CheckCircle2,
        iconWrapper: 'bg-emerald-500/15 text-emerald-500',
        valueClass: 'text-emerald-600',
      },
      {
        key: 'failed',
        title: t('workspace.automation.metrics.failedExecutions'),
        value: failedExecutions,
        icon: AlertTriangle,
        iconWrapper: 'bg-rose-500/15 text-rose-500',
        valueClass: 'text-rose-600',
      },
      {
        key: 'success-rate',
        title: t('workspace.automation.metrics.successRate'),
        value: `${overallSuccessRate}%`,
        icon: Timer,
        iconWrapper: 'bg-sky-500/15 text-sky-500',
        valueClass: 'text-sky-600',
      },
    ];
  }, [jobs, t]);

  const successRateDisplay = metrics ? `${Math.round(metrics.successRate * 100)}%` : '--';

  return (
    <div className="flex h-full flex-col">
      <FeatureHeader
        title={t('workspace.automation.header.title')}
        icon={Cpu}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              className="h-7 px-2 text-xs"
              disabled={isLoading}
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
              {isLoading
                ? t('workspace.automation.header.refresh.loading')
                : t('workspace.automation.header.refresh.action')}
            </Button>
          </div>
        }
        info={
          <div className="hidden md:flex items-center gap-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
              {t('workspace.automation.header.successRate', { rate: successRateDisplay })}
            </div>
            <div className="flex items-center gap-1">
              <UserCircle className="h-3.5 w-3.5" />
              {t('workspace.automation.header.taskCount', { count: jobs.length })}
            </div>
          </div>
        }
      />

      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-6 space-y-6">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {metricCards.map(card => {
                const Icon = card.icon;
                return (
                  <Card key={card.key} className="border border-border/50 bg-card/90 shadow-sm">
                    <CardContent className="p-3">
                      <div className="flex items-center gap-3">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${card.iconWrapper}`}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="flex-1">
                          <p className="text-xs font-medium text-foreground">{card.title}</p>
                          <span className={`text-lg font-semibold ${card.valueClass}`}>{card.value}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <div className="space-y-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold">{t('workspace.automation.table.title')}</h2>
                  <p className="text-sm text-muted-foreground">{t('workspace.automation.table.description')}</p>
                </div>
              </div>

              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('workspace.automation.table.searchPlaceholder')}
                    className="pl-9 h-9"
                    value={search}
                    onChange={event => setSearch(event.target.value)}
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 px-4 gap-2"
                  onClick={() => {/* Search is applied from the input state. */}}
                >
                  <Search className="h-4 w-4" />
                  {t('workspace.automation.table.searchAction')}
                </Button>
              </div>

              <AutomationJobTable
                scope="workspace"
                jobs={jobPagination.paginatedJobs}
                page={jobPagination.page}
                totalPages={jobPagination.totalPages}
                totalItems={jobPagination.totalItems}
                pageSize={jobPagination.pageSize}
                onPageChange={jobPagination.onPageChange}
                onViewExecutions={handleViewJobExecutions}
                onEdit={handleEditJob}
                onExecute={handleExecuteJob}
                onDelete={handleDeleteJob}
                locale={locale}
              />
            </div>
          </div>
        </ScrollArea>
      </div>

      <JobExecutionsDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setSelectedJob(null);
        }}
        job={selectedJob}
        onViewExecution={executionId => {
          setSelectedExecutionId(executionId);
          setIsExecutionDetailOpen(true);
        }}
        title={selectedJob ? t('workspace.automation.dialogs.executions.title', { name: selectedJob.name }) : undefined}
        description={selectedJob?.description ?? undefined}
      />

      <ExecutionDetailDialog
        open={isExecutionDetailOpen}
        executionId={selectedExecutionId}
        runtimeBaseUrl={runtimeBaseUrl ?? undefined}
        canUseAgentChat={canUseAgentChat}
        onOpenChange={open => {
          setIsExecutionDetailOpen(open);
          if (!open) setSelectedExecutionId(null);
        }}
      />

      <AutomationJobEditDialog
        isOpen={isEditDialogOpen}
        task={editingTask}
        loading={editLoading}
        saving={saving}
        onClose={handleCloseEditDialog}
        onSave={handleSaveEdit}
        workspaces={workspaces}
        commands={commands}
        commandsLoading={commandsLoading}
      />
    </div>
  );
};
