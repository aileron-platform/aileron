import React from 'react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Progress } from '@/shared/components/ui/progress';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import type { TaskProgress } from '@/shared/hooks/useTaskProgress';
import { useI18n } from '@/shared/hooks/useI18n';

interface TaskProgressDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  progress: TaskProgress | null;
  title?: string;
}

export const TaskProgressDialog: React.FC<TaskProgressDialogProps> = ({
  open,
  onOpenChange,
  progress,
  title,
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isRunning && <Loader2 className="h-5 w-5 animate-spin" />}
            {isCompleted && <CheckCircle2 className="h-5 w-5 text-green-600" />}
            {isFailed && <AlertCircle className="h-5 w-5 text-red-600" />}
            {resolvedTitle}
          </DialogTitle>
          <DialogDescription>
            {getStatusLabel(progress.status)}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
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
            <Alert className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
              <AlertDescription className="text-green-800 dark:text-green-200">
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

          {(isCompleted || isFailed) && (
            <div className="flex justify-end">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                {t('common.taskProgress.close')}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default TaskProgressDialog;
