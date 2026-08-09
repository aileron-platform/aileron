import { useI18n } from '@/shared/hooks/useI18n';
import { isRunning } from '../model/threadStatusModel';
import type { ThreadStatus } from '../model/threadModel';

interface WorkingMessageProps {
  status: ThreadStatus;
}

export const WorkingMessage = ({ status }: WorkingMessageProps) => {
  const { t } = useI18n();

  if (!isRunning(status)) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" aria-hidden="true" />
      <span>{t(`aiChat.working.${status}`)}</span>
    </div>
  );
};
