import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  Terminal,
  XCircle,
} from 'lucide-react';
import { AutomationJob } from '@/features/automation/types';
import { useI18n } from '@/shared/hooks/useI18n';

interface TaskLog {
  timestamp: string;
  level: 'INFO' | 'ERROR' | 'WARNING' | 'SUCCESS';
  message: string;
}

type WorkerTaskItem = AutomationJob;

interface JobLogDialogProps {
  isOpen: boolean;
  onClose: () => void;
  task: WorkerTaskItem | null;
}

type Translate = (key: string, params?: Record<string, string | number>) => string;

const createMockLogs = (task: WorkerTaskItem, t: Translate, locale: string): TaskLog[] => {
  const now = Date.now();
  const baseTimestamp = (offsetMinutes: number) => new Date(now - offsetMinutes * 60_000).toISOString();

  const baseLogs: TaskLog[] = [
    {
      timestamp: baseTimestamp(10),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.start', { name: task.name }),
    },
    {
      timestamp: baseTimestamp(9),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.workspace', { id: task.workspaceId }),
    },
    {
      timestamp: baseTimestamp(8),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.loadEnvironment'),
    },
    {
      timestamp: baseTimestamp(7),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.initializeContext'),
    },
    {
      timestamp: baseTimestamp(6),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.runPrompt', {
        prompt: `${task.prompt.substring(0, 50)}...`,
      }),
    },
    {
      timestamp: baseTimestamp(5),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.verifyResources'),
    },
    {
      timestamp: baseTimestamp(4),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.startLogic'),
    },
  ];

  if (task.status === 'failed') {
    baseLogs.push({
      timestamp: baseTimestamp(2),
      level: 'ERROR',
      message: t('workspace.automation.dialogs.taskLog.mock.failed'),
    });
    baseLogs.push({
      timestamp: baseTimestamp(1),
      level: 'ERROR',
      message: t('workspace.automation.dialogs.taskLog.mock.markFailed'),
    });
  } else if (task.status === 'active') {
    baseLogs.push({
      timestamp: baseTimestamp(2),
      level: 'SUCCESS',
      message: t('workspace.automation.dialogs.taskLog.mock.successDuration', {
        seconds: task.lastDuration || task.averageDuration,
      }),
    });
    baseLogs.push({
      timestamp: baseTimestamp(1),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.nextRun', {
        time: new Date(task.nextRunAt).toLocaleString(locale),
      }),
    });
  } else if (task.status === 'paused') {
    baseLogs.push({
      timestamp: baseTimestamp(1),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.paused'),
    });
  }

  if (task.notifications.email || task.notifications.slack || task.notifications.webhook) {
    const notificationTypes: string[] = [];
    if (task.notifications.email) notificationTypes.push(t('workspace.automation.dialogs.taskLog.notifications.emailLabel'));
    if (task.notifications.slack) notificationTypes.push(t('workspace.automation.dialogs.taskLog.notifications.slackLabel'));
    if (task.notifications.webhook) notificationTypes.push(t('workspace.automation.dialogs.taskLog.notifications.webhookLabel'));

    baseLogs.push({
      timestamp: baseTimestamp(0.5),
      level: 'INFO',
      message: t('workspace.automation.dialogs.taskLog.mock.notifications', {
        channels: notificationTypes.join(', '),
      }),
    });
  }

  return baseLogs;
};

const statusIconMap: Record<string, React.ReactNode> = {
  active: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
  paused: <Clock className="h-4 w-4 text-amber-500" />,
  draft: <Clock className="h-4 w-4 text-gray-500" />,
};

const statusBadgeClass: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  paused: 'bg-amber-100 text-amber-800',
  draft: 'bg-gray-100 text-gray-800',
};

const logLevelColor = (level: string) => {
  switch (level.toUpperCase()) {
    case 'ERROR':
      return 'text-red-400';
    case 'WARNING':
    case 'WARN':
      return 'text-yellow-400';
    case 'SUCCESS':
      return 'text-green-400';
    case 'INFO':
    default:
      return 'text-blue-400';
  }
};

export const JobLogDialog: React.FC<JobLogDialogProps> = ({ isOpen, onClose, task }) => {
  const { t, state } = useI18n();
  const locale = state.currentLanguage === 'zh-TW' ? 'zh-TW' : 'en-US';
  const [logFilter, setLogFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!task || !isOpen) {
      return;
    }

    setIsLoading(true);
    const timeout = window.setTimeout(() => {
      setLogs(createMockLogs(task, t, locale));
      setIsLoading(false);

      window.setTimeout(() => {
        const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
        if (viewport instanceof HTMLElement) {
          viewport.scrollTop = viewport.scrollHeight;
        }
      }, 100);
    }, 300);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [task, isOpen, t, locale]);

  const filteredLogs = useMemo(() => {
    if (logFilter === 'all') {
      return logs;
    }
    return logs.filter((log) => log.level.toLowerCase() === logFilter.toLowerCase());
  }, [logs, logFilter]);

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  if (!task) {
    return null;
  }

  const handleReload = () => {
    setIsLoading(true);
    setTimeout(() => {
      setLogs(createMockLogs(task, t, locale));
      setIsLoading(false);
    }, 300);
  };

  const statusIcon = statusIconMap[task.status] || <AlertCircle className="h-4 w-4 text-gray-500" />;
  const statusClass = statusBadgeClass[task.status] || 'bg-gray-100 text-gray-800';
  const statusLabel = t(`workspace.automation.status.${task.status}`);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {statusIcon}
            <span>{task.name}</span>
            <Badge className={statusClass}>
              {statusLabel}
            </Badge>
          </DialogTitle>
          <DialogDescription>
            {t('workspace.automation.dialogs.taskLog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 p-4 bg-muted/50 rounded-lg">
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.name')}</div>
            <div className="font-medium">{task.name}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.owner')}</div>
            <div className="font-medium">{task.owner}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.trigger')}</div>
            <div className="font-medium">
              {t(`workspace.automation.triggers.${task.trigger}`)}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.schedule')}</div>
            <div className="font-medium">{task.schedule}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.createdAt')}</div>
            <div className="font-medium">{new Date(task.createdAt).toLocaleString(locale)}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.updatedAt')}</div>
            <div className="font-medium">{new Date(task.updatedAt).toLocaleString(locale)}</div>
          </div>
          {task.lastRunAt && (
            <div>
              <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.lastRun')}</div>
              <div className="font-medium">{new Date(task.lastRunAt).toLocaleString(locale)}</div>
            </div>
          )}
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.nextRun')}</div>
            <div className="font-medium">
              {task.nextRunAt
                ? new Date(task.nextRunAt).toLocaleString(locale)
                : t('workspace.automation.table.noScheduled', '未排程')}
            </div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.successRate')}</div>
            <div className="font-medium">{Math.round(task.successRate * 100)}%</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.totalExecutions')}</div>
            <div className="font-medium">{t('workspace.automation.dialogs.taskLog.totalExecutions', { count: task.totalExecutions })}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.averageDuration')}</div>
            <div className="font-medium">{t('workspace.automation.dialogs.taskLog.durationSeconds', { seconds: task.averageDuration })}</div>
          </div>
          {task.lastDuration && (
            <div>
              <div className="text-sm text-muted-foreground">{t('workspace.automation.dialogs.taskLog.fields.lastDuration')}</div>
              <div className="font-medium">{t('workspace.automation.dialogs.taskLog.durationSeconds', { seconds: task.lastDuration })}</div>
            </div>
          )}
        </div>

        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
          <div className="text-sm font-medium text-slate-700 mb-2">{t('workspace.automation.dialogs.taskLog.promptLabel')}</div>
          <div className="text-sm text-slate-600 break-words font-mono bg-white p-3 rounded border max-h-32 overflow-y-auto">
            {task.prompt}
          </div>
        </div>

        {(task.notifications.email || task.notifications.slack || task.notifications.webhook) && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-medium text-blue-700 mb-2">{t('workspace.automation.dialogs.taskLog.notifications.title')}</div>
            <div className="flex flex-wrap gap-2">
              {task.notifications.email && (
                <Badge variant="outline" className="text-blue-700 border-blue-300">
                  {t('workspace.automation.dialogs.taskLog.notifications.email')}
                </Badge>
              )}
              {task.notifications.slack && (
                <Badge variant="outline" className="text-blue-700 border-blue-300">
                  {t('workspace.automation.dialogs.taskLog.notifications.slack')}
                </Badge>
              )}
              {task.notifications.webhook && (
                <Badge variant="outline" className="text-blue-700 border-blue-300">
                  {t('workspace.automation.dialogs.taskLog.notifications.webhook')}
                </Badge>
              )}
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between p-2 border-b">
            <h4 className="font-medium">{t('workspace.automation.dialogs.taskLog.logs.title')}</h4>
            <div className="flex items-center gap-2">
              <select
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                className="text-xs border rounded px-2 py-1 bg-background"
              >
                <option value="all">{t('workspace.automation.dialogs.taskLog.logs.filters.all')}</option>
                <option value="info">{t('workspace.automation.dialogs.taskLog.logs.filters.info')}</option>
                <option value="error">{t('workspace.automation.dialogs.taskLog.logs.filters.error')}</option>
                <option value="warning">{t('workspace.automation.dialogs.taskLog.logs.filters.warning')}</option>
                <option value="success">{t('workspace.automation.dialogs.taskLog.logs.filters.success')}</option>
              </select>
              <Button variant="outline" size="sm" onClick={handleReload} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
                {t('workspace.automation.dialogs.taskLog.logs.reload')}
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 p-4 bg-gray-900 rounded-lg" ref={scrollAreaRef}>
            <div className="space-y-1 font-mono text-sm">
              {isLoading ? (
                <div className="text-center text-gray-400 py-8">
                  <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin" />
                  <p>{t('workspace.automation.dialogs.taskLog.logs.loading')}</p>
                </div>
              ) : filteredLogs.length > 0 ? (
                filteredLogs.map((log, index) => (
                  <div key={index} className="flex gap-2 py-1 hover:bg-gray-800/50 rounded px-2 -mx-2">
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
                  <p>{t('workspace.automation.dialogs.taskLog.logs.empty')}</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default JobLogDialog;
