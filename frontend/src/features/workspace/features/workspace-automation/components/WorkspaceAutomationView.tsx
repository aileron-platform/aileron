/**
 * WorkspaceAutomationView - 工作區自動化任務主內容
 * 展示當前 workspace 的自動化任務及其執行狀態
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceAutomationView');
import {
  Cpu,
  RefreshCw,
  Search,
  ShieldAlert,
  UserCircle,
  Tag,
  CheckCircle2,
  AlertTriangle,
  Timer,
  History,
  MoreHorizontal,
  Pencil,
  Trash2,
  PlayCircle,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Card, CardContent } from '@/shared/components/ui/card';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/shared/components/ui/dropdown-menu';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useWorkspace } from '@/features/workspace/providers/WorkspaceProvider';
import { workspaceAutomationApi } from '../services/workspaceAutomationApi';
import {
  AutomationJob,
  JobExecution,
  AutomationMetrics,
  JobUpdateInput,
} from '@/features/automation/types';
import { JobExecutionsDialog } from '@/features/automation/components/JobExecutionsDialog';
import { AutomationJobEditDialog, type SchedulerWorkspaceSummary } from '@/features/automation/components/AutomationJobEditDialog';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '@/features/automation/services/automationApi';
import { schedulerWorkspaceApi } from '@/features/automation/services/workspaceApi';
import type { SlashCommandItem } from '@/shared/types/slashCommands';

type WorkerJobItem = AutomationJob;
type WorkerMetrics = AutomationMetrics;
type WorkerExecution = JobExecution;

type Translate = (key: string, params?: Record<string, string | number>) => string;

const STATUS_COLORS: Record<string, string> = {
  active: 'text-emerald-500',
  paused: 'text-amber-500',
  failed: 'text-rose-500',
  draft: 'text-muted-foreground',
};

const JOBS_PER_PAGE = 6;

export const WorkspaceAutomationView: React.FC = () => {
  const { t, state } = useI18n();
  const { workspaceRuntime } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';
  const [jobs, setJobs] = useState<WorkerJobItem[]>([]);
  const [metrics, setMetrics] = useState<WorkerMetrics | null>(null);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [jobPage, setJobPage] = useState(1);
  const [selectedJob, setSelectedJob] = useState<WorkerJobItem | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [jobExecutions, setJobExecutions] = useState<WorkerExecution[]>([]);

  // 編輯對話框狀態
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<AutomationJob | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [workspaces, setWorkspaces] = useState<SchedulerWorkspaceSummary[]>([]);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
  const [commands, setCommands] = useState<SlashCommandItem[]>([]);
  const [commandsLoading, setCommandsLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) {
      setJobs([]);
      setMetrics(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      // 載入任務列表
      const jobList = await workspaceAutomationApi.listJobs(runtimeBaseUrl, workspaceId);
      setJobs(jobList);

      // 嘗試載入指標資料，如果失敗則使用預設值
      try {
        const stats = await workspaceAutomationApi.getMetrics(runtimeBaseUrl, workspaceId);
        setMetrics(stats);
      } catch (metricsError) {
        logger.warn('無法載入任務指標，使用預設值', { error: metricsError });
        // 提供預設的指標資料
        setMetrics({
          activeCount: jobList.filter(job => job.status === 'active').length,
          pausedCount: jobList.filter(job => job.status === 'paused').length,
          failedCount: jobList.filter(job => job.status === 'failed').length,
          draftCount: jobList.filter(job => job.status === 'draft').length,
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
  }, [runtimeBaseUrl, workspaceId]);

  useEffect(() => {
    if (workspaceRuntime.isLoading) {
      setIsLoading(true);
      return;
    }

    void loadData();
  }, [workspaceRuntime.isLoading, loadData]);

  const handleRefresh = useCallback(() => {
    void loadData();
  }, [loadData]);

  const filteredJobs = useMemo(() => {
    return jobs.filter(job => {
      const matchSearch = search.trim().length === 0
        ? true
        : job.name.toLowerCase().includes(search.toLowerCase())
          || job.description.toLowerCase().includes(search.toLowerCase())
          || job.owner.toLowerCase().includes(search.toLowerCase());
      return matchSearch;
    });
  }, [jobs, search]);

  const jobTotalItems = filteredJobs.length;
  const jobTotalPages = Math.max(1, Math.ceil(jobTotalItems / JOBS_PER_PAGE));

  useEffect(() => {
    setJobPage(1);
  }, [search]);

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

  const handleViewJobExecutions = useCallback((job: WorkerJobItem) => {
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

  const handleExecuteJob = useCallback(async (job: WorkerJobItem) => {
    try {
      await automationApi.executeJob(job.id);
      await loadData(); // 重新載入資料
    } catch (error) {
      logger.error('Failed to execute job', { error });
    }
  }, [loadData]);

  const handleDeleteJob = useCallback(async (job: WorkerJobItem) => {
    const confirmed = window.confirm(
      `確定要刪除任務「${job.name}」嗎？`
    );
    if (!confirmed) {
      return;
    }
    try {
      await automationApi.deleteJob(job.id);
      await loadData(); // 重新載入資料
    } catch (error) {
      logger.error('Failed to delete job', { error });
    }
  }, [loadData]);

  useEffect(() => {
    if (!isDialogOpen || !selectedJob || !runtimeBaseUrl || !workspaceId) {
      setJobExecutions([]);
      return;
    }

    void workspaceAutomationApi
      .getJobExecutions(runtimeBaseUrl, workspaceId, selectedJob.id, 50)
      .then(setJobExecutions)
      .catch(error => {
        logger.error('Failed to load job executions', { error });
        setJobExecutions([]);
      });
  }, [isDialogOpen, selectedJob, runtimeBaseUrl, workspaceId]);

  // 載入工作區列表
  useEffect(() => {
    if (!isEditDialogOpen) {
      setWorkspaces([]);
      setWorkspacesLoading(false);
      return;
    }

    const controller = new AbortController();
    setWorkspacesLoading(true);

    const selectedId = editingTask?.workspaceId ?? null;

    void (async () => {
      try {
        const items = await schedulerWorkspaceApi.list(controller.signal);
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
      } finally {
        if (!controller.signal.aborted) {
          setWorkspacesLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [editingTask?.workspaceId, isEditDialogOpen]);

  // 載入 Slash Commands
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
        const items = await schedulerWorkspaceApi.listSlashCommands(
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

  // 處理保存編輯
  const handleSaveEdit = useCallback(async (payload: JobUpdateInput) => {
    setSaving(true);
    try {
      await automationApi.updateJob(payload);
      setIsEditDialogOpen(false);
      setEditingTask(null);
      await loadData(); // 重新載入資料
    } catch (error) {
      logger.error('Failed to update task', { error });
      throw error; // 讓對話框顯示錯誤
    } finally {
      setSaving(false);
    }
  }, [loadData]);

  // 關閉編輯對話框
  const handleCloseEditDialog = useCallback(() => {
    setIsEditDialogOpen(false);
    setEditingTask(null);
  }, []);

  // 收集現有的標籤建議
  const existingTags = useMemo(() => {
    const tags = new Set<string>();
    jobs.forEach(job => job.tags.forEach(tag => tags.add(tag)));
    return Array.from(tags);
  }, [jobs]);

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
                  onClick={() => {/* 使用輸入框即時篩選 */}}
                >
                  <Search className="h-4 w-4" />
                  {t('workspace.automation.table.searchAction')}
                </Button>
              </div>

              <JobTable
                jobs={paginatedJobs}
                page={jobPage}
                totalPages={jobTotalPages}
                totalItems={jobTotalItems}
                pageSize={JOBS_PER_PAGE}
                onPageChange={handleJobPageChange}
                onViewExecutions={handleViewJobExecutions}
                onEdit={handleEditJob}
                onExecute={handleExecuteJob}
                onDelete={handleDeleteJob}
                t={t}
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
        executions={jobExecutions}
        title={selectedJob ? t('workspace.automation.dialogs.executions.title', { name: selectedJob.name }) : undefined}
        description={selectedJob?.description}
        runtimeBaseUrl={runtimeBaseUrl}
      />

      <AutomationJobEditDialog
        isOpen={isEditDialogOpen}
        task={editingTask}
        loading={editLoading}
        saving={saving}
        onClose={handleCloseEditDialog}
        onSave={handleSaveEdit}
        workspaces={workspaces}
        workspacesLoading={workspacesLoading}
        commands={commands}
        commandsLoading={commandsLoading}
        existingTags={existingTags}
      />
    </div>
  );
};

interface JobTableProps {
  jobs: WorkerJobItem[];
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onViewExecutions: (job: WorkerJobItem) => void;
  onEdit: (jobId: string) => void;
  onExecute: (job: WorkerJobItem) => void | Promise<void>;
  onDelete: (job: WorkerJobItem) => void | Promise<void>;
  t: Translate;
  locale: string;
}

const JobTable: React.FC<JobTableProps> = ({ jobs, page, totalPages, totalItems, pageSize, onPageChange, onViewExecutions, onEdit, onExecute, onDelete, t, locale }) => {
  const getStatusLabel = (status: WorkerJobItem['status']) => {
    const key = `workspace.automation.status.${status}`;
    return t(key);
  };

  return (
    <div className="rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border/40">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.name')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.schedule')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.nextRun')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.status')}</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.view')}</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">{t('workspace.automation.table.columns.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30 bg-background/40">
            {jobs.map(job => (
              <tr key={job.id}>
                <td className="px-4 py-3 align-top">
                  <div className="text-sm font-medium text-foreground">{job.name}</div>
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
                      ? t(`workspace.automation.triggers.${job.trigger}`)
                      : job.trigger === 'webhook'
                      ? t(`workspace.automation.triggers.${job.trigger}`)
                      : job.schedule || t('workspace.automation.table.noScheduled')}
                  </div>
                </td>
                <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                  <div>
                    {job.nextRunAt
                      ? t('workspace.automation.table.nextRun', { time: new Date(job.nextRunAt).toLocaleString(locale) })
                      : t('workspace.automation.table.noScheduled')}
                  </div>
                  {job.lastRunAt && (
                    <div className="mt-1">
                      {t('workspace.automation.table.lastRun', { time: new Date(job.lastRunAt).toLocaleString(locale) })}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-xs">
                  <span className={`font-semibold ${STATUS_COLORS[job.status] ?? ''}`}>
                    {getStatusLabel(job.status)}
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
                    {t('workspace.automation.table.viewButton')}
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
                        {t('workspace.automation.table.editAction')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onExecute(job)} className="gap-2 text-xs">
                        <PlayCircle className="h-3.5 w-3.5" />
                        {t('workspace.automation.table.executeAction')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => onDelete(job)}
                        className="gap-2 text-xs text-destructive focus:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {t('workspace.automation.table.deleteAction')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {t('workspace.automation.table.empty')}
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
        t={t}
      />
    </div>
  );
};

interface PaginationFooterProps {
  page: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  t: Translate;
}

const PaginationFooter: React.FC<PaginationFooterProps> = ({ page, totalPages, pageSize, totalItems, onPageChange, t }) => {
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
          ? t('workspace.automation.pagination.range', { start: startItem, end: endItem, total: totalItems })
          : t('workspace.automation.pagination.empty')}
      </span>
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handlePrev}
          disabled={disablePrev}
        >
          {t('workspace.automation.pagination.previous')}
        </Button>
        <span>{t('workspace.automation.pagination.page', { current: currentPage, total: safeTotalPages })}</span>
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-3"
          onClick={handleNext}
          disabled={disableNext}
        >
          {t('workspace.automation.pagination.next')}
        </Button>
      </div>
    </div>
  );
};
