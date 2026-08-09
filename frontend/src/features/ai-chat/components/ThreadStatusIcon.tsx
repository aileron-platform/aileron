import { AlertCircle, Check, Clock, Pencil } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { toMinimalStatus } from '../model/threadStatusModel';
import type { ThreadStatus } from '../model/threadModel';

interface ThreadStatusIconProps {
  status: ThreadStatus;
  unread: boolean;
  className?: string;
}

export const ThreadStatusIcon = ({ status, unread, className }: ThreadStatusIconProps) => {
  const minimalStatus = toMinimalStatus(status);
  const showUnread = unread && minimalStatus !== 'active' && minimalStatus !== 'finishing';

  return (
    <span className={cn('relative inline-flex h-5 w-5 items-center justify-center', className)}>
      {minimalStatus === 'draft' && <Pencil className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      {minimalStatus === 'pending' && <Clock className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      {minimalStatus === 'active' && (
        <span
          data-testid="status-active"
          className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
        />
      )}
      {minimalStatus === 'finishing' && (
        <span
          data-testid="status-active"
          className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/60 border-t-transparent"
        />
      )}
      {minimalStatus === 'complete' && <Check className="h-4 w-4 text-emerald-600" aria-hidden="true" />}
      {minimalStatus === 'error' && <AlertCircle className="h-4 w-4 text-destructive" aria-hidden="true" />}
      {showUnread && (
        <span
          data-testid="status-unread"
          className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-blue-500 ring-2 ring-background"
        />
      )}
    </span>
  );
};
