import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  CheckCircle2,
  Clock,
  RefreshCw,
  Terminal,
  XCircle,
} from 'lucide-react';
import { TaskLog } from '@/shared/types/task';

export type ExecutionLogStatus = 'success' | 'running' | 'failed' | 'queued' | 'waiting' | 'cancelled' | 'timeout';

export interface ExecutionLogDialogExecution {
  id: string;
  jobId: string;
  status: ExecutionLogStatus;
  trigger: string;
  startedAt?: string;
  finishedAt?: string | null;
  duration?: number | null;
  summary: string;
}

export interface ExecutionLogDialogCopy<TExecution extends ExecutionLogDialogExecution> {
  description: string;
  fields: {
    executionId: string;
    jobId: string;
    startedAt: string;
    finishedAt: string;
    trigger: string;
    duration?: string;
  };
  statusLabel: (status: ExecutionLogStatus) => string;
  formatTrigger?: (execution: TExecution) => string;
  formatDuration?: (execution: TExecution) => string | null;
  logs: {
    title: string;
    empty: string;
    loading: string;
    reload: string;
    filters: {
      all: string;
      info: string;
      error: string;
      warning: string;
      success: string;
    };
  };
}

export type ExecutionLogBuilder<TExecution extends ExecutionLogDialogExecution> = (
  execution: TExecution
) => TaskLog[];

export interface ExecutionLogDialogProps<TExecution extends ExecutionLogDialogExecution> {
  isOpen: boolean;
  execution: TExecution | null;
  onClose: () => void;
  locale: string;
  copy: ExecutionLogDialogCopy<TExecution>;
  createLogs: ExecutionLogBuilder<TExecution>;
}

const statusHeadingIconMap = {
  success: { icon: CheckCircle2, iconClassName: 'h-4 w-4 text-primary' },
  failed: { icon: XCircle, iconClassName: 'h-4 w-4 text-rose-500' },
  running: { icon: RefreshCw, iconClassName: 'h-4 w-4 text-sky-500 animate-spin' },
  queued: { icon: Clock, iconClassName: 'h-4 w-4 text-amber-500' },
  waiting: { icon: Clock, iconClassName: 'h-4 w-4 text-purple-500' },
  cancelled: { icon: XCircle, iconClassName: 'h-4 w-4 text-gray-500' },
  timeout: { icon: Clock, iconClassName: 'h-4 w-4 text-orange-500' },
};

const statusBadgeClass: Record<ExecutionLogStatus, string> = {
  success:
    'bg-primary/10 text-primary border-primary/20 dark:bg-primary/15 dark:text-primary-foreground dark:border-primary/30',
  failed:
    'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-500/15 dark:text-rose-200 dark:border-rose-400/40',
  running:
    'bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-500/15 dark:text-sky-200 dark:border-sky-400/40',
  queued:
    'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-500/15 dark:text-amber-200 dark:border-amber-400/40',
  waiting:
    'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-500/15 dark:text-purple-200 dark:border-purple-400/40',
  cancelled:
    'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-500/15 dark:text-gray-200 dark:border-gray-400/40',
  timeout:
    'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-500/15 dark:text-orange-200 dark:border-orange-400/40',
};

const logLevelColor = (level: string) => {
  switch (level.toUpperCase()) {
    case 'ERROR':
      return 'text-rose-400';
    case 'WARNING':
    case 'WARN':
      return 'text-amber-400';
    case 'SUCCESS':
      return 'text-primary';
    case 'INFO':
    default:
      return 'text-sky-400';
  }
};

export function ExecutionLogDialog<
  TExecution extends ExecutionLogDialogExecution = ExecutionLogDialogExecution
>({
  isOpen,
  execution,
  onClose,
  locale,
  copy,
  createLogs,
}: ExecutionLogDialogProps<TExecution>) {
  const [logFilter, setLogFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!execution || !isOpen) {
      return;
    }

    setIsLoading(true);
    const timeout = window.setTimeout(() => {
      setLogs(createLogs(execution));
      setIsLoading(false);

      window.setTimeout(() => {
        const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
        if (viewport instanceof HTMLElement) {
          viewport.scrollTop = viewport.scrollHeight;
        }
      }, 100);
    }, 260);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [execution, isOpen, createLogs]);

  const filteredLogs = useMemo(() => {
    if (logFilter === 'all') {
      return logs;
    }
    return logs.filter(log => log.level.toLowerCase() === logFilter.toLowerCase());
  }, [logs, logFilter]);

  const formatTime = (timestamp: string) =>
    new Date(timestamp).toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

  const handleReload = () => {
    if (!execution) {
      return;
    }
    setIsLoading(true);
    window.setTimeout(() => {
      setLogs(createLogs(execution));
      setIsLoading(false);
    }, 220);
  };

  if (!execution) {
    return null;
  }

  const statusHeadingIcon = statusHeadingIconMap[execution.status];
  const statusClass = statusBadgeClass[execution.status];
  const statusLabel = copy.statusLabel(execution.status);
  const triggerLabel = copy.formatTrigger?.(execution) ?? execution.trigger;
  const durationLabel =
    copy.formatDuration?.(execution) ?? (typeof execution.duration === 'number' ? `${execution.duration}s` : null);

  const truncatedSummary = execution.summary.length > 80
    ? `${execution.summary.substring(0, 80)}...`
    : execution.summary;

  return (
    <Dialog open={isOpen} onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-3xl h-[70vh] flex flex-col">
        <DialogHeader>
          <DialogHeading icon={statusHeadingIcon.icon} iconClassName={statusHeadingIcon.iconClassName}>
            <span className="text-sm md:text-base font-semibold" title={execution.summary}>{truncatedSummary}</span>
            <Badge className={`${statusClass} capitalize`}>
              {statusLabel}
            </Badge>
          </DialogHeading>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 p-4 bg-muted/60 rounded-lg border border-border/40">
          <div>
            <div className="text-xs text-muted-foreground">{copy.fields.executionId}</div>
            <div className="font-medium text-sm">{execution.id}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{copy.fields.jobId}</div>
            <div className="font-medium text-sm">{execution.jobId}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{copy.fields.startedAt}</div>
            <div className="font-medium text-sm">{new Date(execution.startedAt).toLocaleString(locale)}</div>
          </div>
          {execution.finishedAt && (
            <div>
              <div className="text-xs text-muted-foreground">{copy.fields.finishedAt}</div>
              <div className="font-medium text-sm">{new Date(execution.finishedAt).toLocaleString(locale)}</div>
            </div>
          )}
          <div>
            <div className="text-xs text-muted-foreground">{copy.fields.trigger}</div>
            <div className="font-medium text-sm uppercase">{triggerLabel}</div>
          </div>
          {copy.fields.duration && durationLabel && (
            <div>
              <div className="text-xs text-muted-foreground">{copy.fields.duration}</div>
              <div className="font-medium text-sm">{durationLabel}</div>
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between p-2 border-b border-border/40">
            <h4 className="text-sm font-medium">{copy.logs.title}</h4>
            <div className="flex items-center gap-2">
              <select
                value={logFilter}
                onChange={event => setLogFilter(event.target.value)}
                className="text-xs border border-border/60 rounded px-2 py-1 bg-background"
              >
                <option value="all">{copy.logs.filters.all}</option>
                <option value="info">{copy.logs.filters.info}</option>
                <option value="error">{copy.logs.filters.error}</option>
                <option value="warning">{copy.logs.filters.warning}</option>
                <option value="success">{copy.logs.filters.success}</option>
              </select>
              <Button variant="outline" size="sm" onClick={handleReload} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
                {copy.logs.reload}
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 p-4 bg-gray-900 rounded-lg" ref={scrollAreaRef}>
            <div className="space-y-1 font-mono text-sm">
              {isLoading ? (
                <div className="text-center text-gray-400 py-8">
                  <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin" />
                  <p>{copy.logs.loading}</p>
                </div>
              ) : filteredLogs.length > 0 ? (
                filteredLogs.map((log, index) => (
                  <div key={`${log.timestamp}-${index}`} className="flex gap-2 py-1 hover:bg-gray-800/50 rounded px-2 -mx-2">
                    <span className="text-gray-400 text-xs min-w-[80px]">{formatTime(log.timestamp)}</span>
                    <span className={`text-xs min-w-[60px] font-medium ${logLevelColor(log.level)}`}>
                      [{log.level}]
                    </span>
                    <span className="flex-1 text-xs leading-relaxed break-words text-gray-200">
                      {log.message}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-center text-gray-400 py-8">
                  <Terminal className="h-8 w-8 mx-auto mb-2" />
                  <p>{copy.logs.empty}</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ExecutionLogDialog;
