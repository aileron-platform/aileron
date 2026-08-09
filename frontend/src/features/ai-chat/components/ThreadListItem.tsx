import type { KeyboardEvent } from 'react';
import { Cpu } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { isUnread } from '../storage/aiChatStorage';
import { resolveThreadTitle } from '../model/threadTitleModel';
import type { ThreadSummary } from '../model/threadModel';
import { agentIconSrcByTool } from './agentIcons';
import { ThreadActionMenu } from './ThreadActionMenu';
import { ThreadStatusIcon } from './ThreadStatusIcon';

interface ThreadListItemProps {
  thread: ThreadSummary;
  workspaceId: string;
  userId: string;
  selected: boolean;
  onSelect: (threadId: string) => void;
  onArchive: (threadId: string) => void;
  onDelete: (threadId: string) => void;
}

const relativeTimeKey = (isoTime: string): { key: string; count?: number } => {
  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - Date.parse(isoTime)) / 60_000));
  if (elapsedMinutes < 1) {
    return { key: 'aiChat.threadList.relative.now' };
  }
  if (elapsedMinutes < 60) {
    return { key: 'aiChat.threadList.relative.minutesAgo', count: elapsedMinutes };
  }

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) {
    return { key: 'aiChat.threadList.relative.hoursAgo', count: elapsedHours };
  }

  return { key: 'aiChat.threadList.relative.daysAgo', count: Math.floor(elapsedHours / 24) };
};

export const ThreadListItem = ({
  thread,
  workspaceId,
  userId,
  selected,
  onSelect,
  onArchive,
  onDelete,
}: ThreadListItemProps) => {
  const { t } = useI18n();
  const unread = isUnread(thread, userId, workspaceId);
  const relative = relativeTimeKey(thread.updatedAt);
  const title = resolveThreadTitle(thread.title, t);
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    onSelect(thread.id);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(thread.id)}
      onKeyDown={handleKeyDown}
      data-selected={selected ? 'true' : 'false'}
      className={cn(
        'relative flex w-full min-w-0 flex-col gap-2 rounded-md border border-transparent px-3 py-2 pr-9 text-left outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring',
        selected && 'border-border bg-accent/70',
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <ThreadStatusIcon status={thread.status} unread={unread} className="h-4 w-4 shrink-0" />
          <span
            data-testid="ai-chat-thread-title"
            className="min-w-0 flex-1 truncate text-sm font-medium text-foreground"
          >
            {title}
          </span>
        </div>
        <ThreadActionMenu
          thread={thread}
          onArchive={onArchive}
          onDelete={onDelete}
          triggerClassName="absolute right-2 top-2"
        />
      </div>
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span
            data-testid="ai-chat-thread-agent-tag"
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground"
          >
            <img
              src={agentIconSrcByTool[thread.agenticTool]}
              alt=""
              data-testid="ai-chat-thread-agent-icon"
              className="h-4 w-4 shrink-0 rounded-sm"
              aria-hidden="true"
            />
            <span>{thread.agenticTool}</span>
          </span>
          <span
            data-testid="ai-chat-thread-model-tag"
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground"
          >
            <Cpu data-testid="ai-chat-thread-model-icon" className="h-3 w-3 shrink-0" aria-hidden="true" />
            <span>{thread.model}</span>
          </span>
        </div>
        <time dateTime={thread.updatedAt} className="shrink-0 text-[11px] text-muted-foreground">
          {t(relative.key, relative.count === undefined ? undefined : { count: relative.count })}
        </time>
      </div>
    </div>
  );
};
