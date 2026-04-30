import React from 'react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Progress } from '@/shared/components/ui/progress';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import type { TaskProgress } from '@/shared/hooks/useTaskProgress';
import { useI18n } from '@/shared/hooks/useI18n';

interface TaskProgressCardProps {
  progress: TaskProgress | null;
  title?: string;
  onDismiss?: () => void;
}

export const TaskProgressCard: React.FC<TaskProgressCardProps> = ({
  progress,
  title,
  onDismiss,
}) => {
  const { t } = useI18n();
  const resolvedTitle = title ?? t('common.taskProgress.title');

  const getStatusLabel = (status: string): string => {
    const statusKey = `common.taskProgress.status.${status}`;
    const translated = t(statusKey);
    return translated !== statusKey ? translated : status;
  };
  if (!progress) {
    return null;
  }

  const isRunning = progress.status === 'running' || progress.status === 'pending';
  const isCompleted = progress.status === 'completed';
  const isFailed = progress.status === 'failed';

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            {isRunning && <Loader2 className="h-4 w-4 animate-spin" />}
            {isCompleted && <CheckCircle2 className="h-4 w-4 text-green-600" />}
            {isFailed && <AlertCircle className="h-4 w-4 text-red-600" />}
            {resolvedTitle}: {getStatusLabel(progress.status)}
          </CardTitle>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label={t('common.taskProgress.close')}
            >
              <span aria-hidden="true">x</span>
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{t('common.taskProgress.progress')}</span>
            <span className="text-sm text-muted-foreground">{progress.progress}%</span>
          </div>
          <Progress value={progress.progress} className="h-2" />
        </div>

        {progress.message && (
          <p className="text-sm text-muted-foreground">{progress.message}</p>
        )}

        {isCompleted && progress.result && (
          <Alert className="border-green-200 bg-green-50">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              <div className="font-medium">{progress.result.message}</div>
              {progress.result.synced_count !== undefined && (
                <div className="text-sm mt-1">
                  {t('common.taskProgress.syncedCount', { count: progress.result.synced_count })}
                </div>
              )}
            </AlertDescription>
          </Alert>
        )}

        {isFailed && progress.error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{progress.error}</AlertDescription>
          </Alert>
        )}

        {(progress.started_at || progress.completed_at) && (
          <div className="text-xs text-muted-foreground space-y-1">
            {progress.started_at && (
              <div>{t('common.taskProgress.startedAt')}: {new Date(progress.started_at).toLocaleString()}</div>
            )}
            {progress.completed_at && (
              <div>{t('common.taskProgress.completedAt')}: {new Date(progress.completed_at).toLocaleString()}</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TaskProgressCard;
