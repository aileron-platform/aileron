import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Ban, CheckCircle2, ChevronLeft, ChevronRight, Clock, Eye, RefreshCw, XCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Tabs, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '../../api/automationApi';
import type { AutomationJob, JobExecution } from '../../model/automationTypes';

type ExecutionRangeOption = 'all' | 'today' | 'tomorrow' | 'week' | 'month' | 'custom';

interface CustomDateRange {
  start: string | null;
  end: string | null;
}

interface JobExecutionsDialogProps {
  isOpen: boolean;
  job: AutomationJob | null;
  onClose: () => void;
  onViewExecution(executionId: string): void;
  title?: string;
  description?: string;
}

const EXECUTIONS_PER_PAGE = 10;

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
const endOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);

const getRange = (option: ExecutionRangeOption, custom: CustomDateRange) => {
  const now = new Date();
  if (option === 'all') return { start: null, end: null };
  if (option === 'today') return { start: startOfDay(now), end: endOfDay(now) };
  if (option === 'tomorrow') {
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    return { start: startOfDay(tomorrow), end: endOfDay(tomorrow) };
  }
  if (option === 'week') {
    const start = startOfDay(now);
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    const end = endOfDay(new Date(start));
    end.setDate(end.getDate() + 6);
    return { start, end };
  }
  if (option === 'month') {
    return {
      start: new Date(now.getFullYear(), now.getMonth(), 1),
      end: endOfDay(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
    };
  }
  let start = custom.start ? startOfDay(new Date(`${custom.start}T00:00:00`)) : null;
  let end = custom.end ? endOfDay(new Date(`${custom.end}T00:00:00`)) : null;
  if (start && end && start > end) [start, end] = [startOfDay(end), endOfDay(start)];
  return { start, end };
};

const statusIcon: Record<JobExecution['status'], React.ReactNode> = {
  queued: <Clock className="h-4 w-4 text-amber-500" />,
  running: <RefreshCw className="h-4 w-4 animate-spin text-sky-500" />,
  success: <CheckCircle2 className="h-4 w-4 text-primary" />,
  failed: <XCircle className="h-4 w-4 text-rose-500" />,
  cancelled: <Ban className="h-4 w-4 text-muted-foreground" />,
};

export function JobExecutionsDialog({
  isOpen,
  job,
  onClose,
  onViewExecution,
  title,
  description,
}: JobExecutionsDialogProps) {
  const { t, state } = useI18n();
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';
  const [page, setPage] = useState(1);
  const [rangeOption, setRangeOption] = useState<ExecutionRangeOption>('all');
  const [customRange, setCustomRange] = useState<CustomDateRange>({ start: null, end: null });
  const range = useMemo(() => getRange(rangeOption, customRange), [rangeOption, customRange]);
  const rangeStart = range.start?.toISOString();
  const rangeEnd = range.end?.toISOString();
  const executionsQuery = useQuery({
    queryKey: ['automation', 'job-executions', job?.id, page, rangeStart, rangeEnd],
    queryFn: () => automationApi.getJobExecutions(job!.id, {
      page,
      pageSize: EXECUTIONS_PER_PAGE,
      rangeStart,
      rangeEnd,
    }),
    enabled: isOpen && Boolean(job),
    retry: false,
    placeholderData: previous => previous,
  });
  const executions = executionsQuery.data?.items ?? [];
  const total = executionsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / EXECUTIONS_PER_PAGE));

  useEffect(() => {
    if (isOpen) setPage(1);
  }, [isOpen, job?.id]);

  useEffect(() => {
    if (executionsQuery.data && page > totalPages) setPage(totalPages);
  }, [executionsQuery.data, page, totalPages]);

  const handleRangeChange = (value: string) => {
    setRangeOption(value as ExecutionRangeOption);
    setPage(1);
  };

  const formatTime = (execution: JobExecution) => new Date(
    execution.startedAt ?? execution.queuedAt ?? execution.scheduledFor,
  ).toLocaleString(locale);

  const formatDuration = (execution: JobExecution) => {
    if (!execution.startedAt || !execution.finishedAt) {
      return t('workspace.automation.dialogs.executions.notAvailable');
    }
    const seconds = Math.max(0, Math.round(
      (new Date(execution.finishedAt).getTime() - new Date(execution.startedAt).getTime()) / 1000,
    ));
    return t('workspace.automation.dialogs.executions.durationSeconds', { seconds });
  };

  return (
    <Dialog open={isOpen} onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="flex h-[min(760px,90vh)] w-[min(900px,calc(100vw-2rem))] max-w-none flex-col overflow-hidden border-border/60 p-0">
        <DialogHeader className="flex-shrink-0 border-b border-border/60 px-6 py-5">
          <div className="flex items-start justify-between gap-4 pr-8">
            <div className="space-y-1">
              <DialogHeading icon={Clock} className="text-base font-semibold">
                {title ?? t('workspace.automation.dialogs.executions.recordTitle', { name: job?.name ?? '' })}
              </DialogHeading>
              <DialogDescription>
                {description ?? t('workspace.automation.dialogs.executions.recordDescription')}
              </DialogDescription>
            </div>
            {job && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={executionsQuery.isFetching}
                onClick={() => void executionsQuery.refetch()}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${executionsQuery.isFetching ? 'animate-spin' : ''}`} />
                {t('workspace.automation.dialogs.executions.refresh')}
              </Button>
            )}
          </div>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden px-6 py-5">
          <Tabs value={rangeOption} onValueChange={handleRangeChange}>
            <TabsList className="h-auto flex-wrap justify-start">
              {(['all', 'today', 'tomorrow', 'week', 'month', 'custom'] as const).map(option => (
                <TabsTrigger key={option} value={option}>
                  {t(`workspace.automation.dialogs.executions.rangeTabs.${option}`)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="grid min-h-16 grid-cols-2 gap-3" aria-live="polite">
            {rangeOption === 'custom' ? (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="execution-range-start" className="text-xs text-muted-foreground">
                    {t('workspace.automation.dialogs.executions.customRange.start')}
                  </Label>
                  <Input id="execution-range-start" type="date" value={customRange.start ?? ''} onChange={event => { setCustomRange(prev => ({ ...prev, start: event.target.value || null })); setPage(1); }} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="execution-range-end" className="text-xs text-muted-foreground">
                    {t('workspace.automation.dialogs.executions.customRange.end')}
                  </Label>
                  <Input id="execution-range-end" type="date" value={customRange.end ?? ''} onChange={event => { setCustomRange(prev => ({ ...prev, end: event.target.value || null })); setPage(1); }} />
                </div>
              </>
            ) : (
              <p className="col-span-2 self-center text-xs text-muted-foreground">
                {t('workspace.automation.dialogs.executions.resultCount', { count: total })}
              </p>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border/60">
            <table className="w-full min-w-[760px] border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-muted/95 text-left text-[11px] text-muted-foreground backdrop-blur">
                <tr className="border-b border-border/60">
                  <th className="px-3 py-2 font-medium">{t('workspace.automation.dialogs.executions.columns.status')}</th>
                  <th className="px-3 py-2 font-medium">{t('workspace.automation.dialogs.executions.columns.trigger')}</th>
                  <th className="px-3 py-2 font-medium">{t('workspace.automation.dialogs.executions.columns.occurredAt')}</th>
                  <th className="px-3 py-2 font-medium">{t('workspace.automation.dialogs.executions.columns.duration')}</th>
                  <th className="px-3 py-2 font-medium">{t('workspace.automation.dialogs.executions.columns.queue')}</th>
                  <th className="px-3 py-2 text-right font-medium">{t('workspace.automation.dialogs.executions.columns.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {executions.map(execution => (
                  <tr key={execution.id} className="bg-background/70 transition-colors hover:bg-muted/30">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        {statusIcon[execution.status]}
                        <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                          {t(`workspace.automation.dialogs.executions.status.${execution.status}`)}
                        </Badge>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {t(`workspace.automation.triggers.${execution.trigger}`)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs tabular-nums">{formatTime(execution)}</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs tabular-nums">{formatDuration(execution)}</td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {execution.queuePosition == null
                        ? t('workspace.automation.dialogs.executions.notAvailable')
                        : t('workspace.automation.dialogs.executions.queuePositionShort', { position: execution.queuePosition })}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => onViewExecution(execution.id)}>
                        <Eye className="mr-1.5 h-3.5 w-3.5" />
                        {t('workspace.automation.dialogs.executions.viewExecution')}
                      </Button>
                    </td>
                  </tr>
                ))}
                {!executionsQuery.isLoading && executions.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                      {executionsQuery.isError
                        ? t('workspace.automation.dialogs.executions.loadFailed')
                        : t('workspace.automation.dialogs.executions.empty')}
                    </td>
                  </tr>
                )}
                {executionsQuery.isLoading && (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                      <RefreshCw className="mx-auto h-5 w-5 animate-spin" />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground">
            <span>{t('workspace.automation.dialogs.executions.resultCount', { count: total })}</span>
            <div className="flex items-center gap-2">
              <span>{t('workspace.automation.dialogs.executions.pagination', { page, totalPages })}</span>
              <Button type="button" variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1 || executionsQuery.isFetching} onClick={() => setPage(current => current - 1)} aria-label={t('workspace.automation.dialogs.executions.previousPage')}>
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button type="button" variant="outline" size="icon" className="h-7 w-7" disabled={page >= totalPages || executionsQuery.isFetching} onClick={() => setPage(current => current + 1)} aria-label={t('workspace.automation.dialogs.executions.nextPage')}>
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
