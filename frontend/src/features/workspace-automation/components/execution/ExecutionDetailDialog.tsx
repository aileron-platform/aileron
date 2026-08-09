import { useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Ban,
  CalendarClock,
  CheckCircle2,
  Clock,
  ListOrdered,
  ListPlus,
  MessageSquare,
  Play,
  RefreshCw,
  Timer,
  XCircle,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Button } from '@/shared/components/ui/button';
import {
  aiChatAutomationExecutionThreadQueryKey,
  aiChatThreadQueryKey,
  getThreadApi,
  ThreadApiError,
  ThreadTimeline,
  useAiChatIntegration,
  useThreadEvents,
} from '@/features/ai-chat/public';
import { useI18n } from '@/shared/hooks/useI18n';
import { automationApi } from '../../api/automationApi';
import type { JobExecution } from '../../model/automationTypes';

interface ExecutionDetailDialogProps {
  open: boolean;
  executionId: string | null;
  runtimeBaseUrl?: string;
  canUseAgentChat?: boolean;
  onOpenChange(open: boolean): void;
}

const ACTIVE_STATUSES = new Set<JobExecution['status']>(['queued', 'running']);
const STATUS_PRESENTATION: Record<JobExecution['status'], {
  icon: LucideIcon;
  className: string;
}> = {
  queued: { icon: Clock, className: 'text-amber-500' },
  running: { icon: RefreshCw, className: 'animate-spin text-sky-500' },
  success: { icon: CheckCircle2, className: 'text-emerald-500' },
  failed: { icon: XCircle, className: 'text-rose-500' },
  cancelled: { icon: Ban, className: 'text-muted-foreground' },
};
const STABLE_ERROR_CODES = new Set([
  'automation_execution_failed',
  'agent_execution_failed',
  'workspace_git_repository_required',
  'workspace_git_initial_commit_required',
  'worktree_conflict',
  'worktree_operation_in_progress',
  'worktree_locked',
  'worktree_storage_limit',
  'automation_worktree_unavailable',
  'automation_runtime_unavailable',
]);
const executionQueryKey = (executionId: string | null) =>
  ['automation', 'execution', executionId ?? ''] as const;

const isActive = (execution?: JobExecution): boolean =>
  Boolean(execution && ACTIVE_STATUSES.has(execution.status));

const isThreadNotFound = (error: unknown): boolean =>
  error instanceof ThreadApiError &&
  error.status === 404 &&
  error.code === 'automation_thread_not_found';

export function ExecutionDetailDialog({
  open,
  executionId,
  runtimeBaseUrl,
  canUseAgentChat = false,
  onOpenChange,
}: ExecutionDetailDialogProps) {
  const { t, state } = useI18n();
  const aiChatIntegration = useAiChatIntegration();
  const queryClient = useQueryClient();
  const timelineScrollRef = useRef<HTMLDivElement>(null);
  const [cancelling, setCancelling] = useState(false);
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';
  const threadApi = useMemo(
    () => canUseAgentChat && runtimeBaseUrl ? getThreadApi(runtimeBaseUrl) : null,
    [canUseAgentChat, runtimeBaseUrl],
  );

  const executionQuery = useQuery({
    queryKey: executionQueryKey(executionId),
    queryFn: () => automationApi.getExecution(executionId ?? ''),
    enabled: open && Boolean(executionId),
    retry: false,
    refetchInterval: query => isActive(query.state.data) ? 3000 : false,
  });
  const execution = executionQuery.data;
  const active = isActive(execution);
  const workspaceId = execution?.workspaceId ?? '';
  const integrationOwnsThreadEvents = Boolean(
    workspaceId
    && runtimeBaseUrl
    && aiChatIntegration.workspaceId === workspaceId
    && aiChatIntegration.runtimeBaseUrl === runtimeBaseUrl,
  );
  useThreadEvents(
    workspaceId,
    open && !integrationOwnsThreadEvents ? runtimeBaseUrl ?? '' : '',
    canUseAgentChat,
  );

  const threadQuery = useQuery({
    queryKey: aiChatAutomationExecutionThreadQueryKey(workspaceId, executionId),
    queryFn: () => threadApi!.getThreadByAutomationExecution(executionId ?? ''),
    enabled: canUseAgentChat
      && open
      && Boolean(executionId)
      && Boolean(workspaceId)
      && threadApi !== null,
    retry: false,
    refetchInterval: query => {
      if (query.state.data) return false;
      if (active && (query.state.error == null || isThreadNotFound(query.state.error))) return 3000;
      return false;
    },
  });
  const resolvedThreadId = threadQuery.data?.id ?? null;
  const metadataQuery = useQuery({
    queryKey: aiChatThreadQueryKey(workspaceId, resolvedThreadId),
    queryFn: () => threadApi!.getThread(resolvedThreadId ?? ''),
    enabled: canUseAgentChat
      && open
      && Boolean(resolvedThreadId)
      && threadApi !== null,
    initialData: threadQuery.data,
    refetchInterval: query => {
      const runtimeActive = query.state.data
        ? ['queued', 'booting', 'working', 'stopping'].includes(query.state.data.status)
        : false;
      return active || runtimeActive ? 3000 : false;
    },
  });

  const formatTimestamp = (value: string | null): string => {
    if (!value) return t('automation.executionDetail.notAvailable');
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? t('automation.executionDetail.notAvailable')
      : date.toLocaleString(locale);
  };

  const duration = execution?.startedAt && execution.finishedAt
    ? Math.max(0, Math.round(
      (new Date(execution.finishedAt).getTime() - new Date(execution.startedAt).getTime()) / 1000,
    ))
    : null;

  const handleCancel = async () => {
    if (!executionId || !execution || !active) return;
    setCancelling(true);
    try {
      const canonical = await automationApi.cancelExecution(executionId);
      queryClient.setQueryData(executionQueryKey(executionId), canonical);
      await executionQuery.refetch();
    } finally {
      setCancelling(false);
    }
  };

  const errorSummary = execution?.errorCode
    ? STABLE_ERROR_CODES.has(execution.errorCode)
      ? t(`automation.executionDetail.errors.${execution.errorCode}`)
      : t('automation.executionDetail.errors.generic')
    : null;
  const statusPresentation = execution ? STATUS_PRESENTATION[execution.status] : null;
  const StatusIcon = statusPresentation?.icon;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0 border-b pb-4">
          <DialogHeading icon={MessageSquare} className="text-lg font-semibold">
            {t('automation.executionDetail.title')}
          </DialogHeading>
          <DialogDescription>
            {executionId
              ? t('automation.executionDetail.subtitle', { executionId })
              : t('automation.executionDetail.notAvailable')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 min-h-0 flex flex-col gap-4 pt-4">
          {executionQuery.isLoading ? (
            <div className="flex flex-1 items-center justify-center">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : executionQuery.isError || !execution ? (
            <p className="text-sm text-destructive">
              {t('automation.executionDetail.errors.loadFailed')}
            </p>
          ) : (
            <>
              <section
                data-testid="execution-lifecycle-strip"
                className="rounded-md border border-border/60 bg-muted/15 px-3 py-2.5"
              >
                <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
                  <div className="min-w-24 shrink-0 pr-1">
                    <div className="flex items-center gap-1.5">
                      {StatusIcon && (
                        <StatusIcon
                          className={`h-3.5 w-3.5 ${statusPresentation.className}`}
                          aria-hidden="true"
                        />
                      )}
                      <span className="text-xs font-semibold">
                        {t(`automation.executionDetail.status.${execution.status}`)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Zap className="h-3 w-3" aria-hidden="true" />
                      <span>{t(`automation.form.trigger.${execution.trigger}`)}</span>
                    </div>
                  </div>
                  <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-6">
                    <LifecycleItem icon={CalendarClock} label={t('automation.executionDetail.fields.scheduledFor')} value={formatTimestamp(execution.scheduledFor)} />
                    <LifecycleItem icon={ListPlus} label={t('automation.executionDetail.fields.queuedAt')} value={formatTimestamp(execution.queuedAt)} />
                    <LifecycleItem icon={Play} label={t('automation.executionDetail.fields.startedAt')} value={formatTimestamp(execution.startedAt)} />
                    <LifecycleItem icon={CheckCircle2} label={t('automation.executionDetail.fields.finishedAt')} value={formatTimestamp(execution.finishedAt)} />
                    <LifecycleItem
                      icon={Timer}
                      label={t('automation.executionDetail.fields.duration')}
                      value={duration == null
                        ? t('automation.executionDetail.notAvailable')
                        : t('automation.executionDetail.durationSeconds', { seconds: duration })}
                    />
                    {execution.queuePosition != null && (
                      <LifecycleItem
                        icon={ListOrdered}
                        label={t('automation.executionDetail.fields.queuePosition')}
                        value={t('automation.executionDetail.queuePosition', {
                          position: execution.queuePosition,
                        })}
                      />
                    )}
                  </dl>
                  {active && (
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      className="h-7 shrink-0 px-2.5 text-xs"
                      disabled={cancelling}
                      onClick={() => void handleCancel()}
                    >
                      <Ban className="mr-1.5 h-3.5 w-3.5" />
                      {t('automation.executionDetail.actions.cancel')}
                    </Button>
                  )}
                </div>
                {errorSummary && (
                  <p className="mt-2 border-t border-border/50 pt-2 text-xs text-destructive">
                    {errorSummary}
                  </p>
                )}
              </section>

              {!runtimeBaseUrl ? (
                <p className="text-sm text-muted-foreground">
                  {t('automation.executionDetail.thread.runtimeUnavailable')}
                </p>
              ) : resolvedThreadId ? (
                <div ref={timelineScrollRef} className="min-h-0 flex-1 overflow-y-auto rounded-lg border bg-muted/20 p-4">
                  <ThreadTimeline
                    workspaceId={workspaceId}
                    threadId={resolvedThreadId}
                    scrollContainerRef={timelineScrollRef}
                    runtimeBaseUrl={runtimeBaseUrl}
                  />
                  {metadataQuery.isError && (
                    <p className="text-sm text-destructive">
                      {t('automation.executionDetail.thread.loadFailed')}
                    </p>
                  )}
                </div>
              ) : active && (threadQuery.isLoading || isThreadNotFound(threadQuery.error)) ? (
                <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                  <Clock className="mr-2 h-4 w-4" />
                  {t('automation.executionDetail.thread.waiting')}
                </div>
              ) : threadQuery.isError && !isThreadNotFound(threadQuery.error) ? (
                <p className="text-sm text-destructive">
                  {t('automation.executionDetail.thread.loadFailed')}
                </p>
              ) : isThreadNotFound(threadQuery.error) ? (
                <p className="text-sm text-muted-foreground">
                  {t('automation.executionDetail.thread.notFound')}
                </p>
              ) : null}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LifecycleItem({ icon: Icon, label, value }: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 border-l border-border/50 pl-2.5 first:border-l-0 first:pl-0">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/80" aria-hidden="true" />
      <div className="min-w-0">
        <dt className="truncate text-[10px] font-medium leading-4 text-muted-foreground">{label}</dt>
        <dd className="truncate whitespace-nowrap text-xs font-medium leading-4 tabular-nums" title={value}>
          {value}
        </dd>
      </div>
    </div>
  );
}
