import { Check, ChevronDown, MessageSquare, Plus } from 'lucide-react';
import { useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { isUnread } from '../storage/aiChatStorage';
import { resolveThreadTitle } from '../model/threadTitleModel';
import type { ThreadSummary } from '../model/threadModel';
import { agentIconSrcByTool } from './agentIcons';
import { ThreadStatusIcon } from './ThreadStatusIcon';

interface ThreadSwitcherProps {
  workspaceId: string;
  userId: string;
  threads: ThreadSummary[];
  selectedThreadId: string | null;
  onSelect: (threadId: string) => void;
  onNewThread: () => void;
}

const sortRecentThreads = (threads: ThreadSummary[]): ThreadSummary[] =>
  [...threads]
    .filter((thread) => !thread.archived)
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
    .slice(0, 5);

export const ThreadSwitcher = ({
  workspaceId,
  userId,
  threads,
  selectedThreadId,
  onSelect,
  onNewThread,
}: ThreadSwitcherProps) => {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const recentThreads = sortRecentThreads(threads);
  const selectedThread = recentThreads.find((thread) => thread.id === selectedThreadId)
    ?? threads.find((thread) => thread.id === selectedThreadId)
    ?? null;
  const selectedTitle = selectedThread ? resolveThreadTitle(selectedThread.title, t) : null;

  const handleSelect = (threadId: string) => {
    onSelect(threadId);
    setOpen(false);
  };

  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            role="combobox"
            aria-label={t('aiChat.companion.switchThread')}
            aria-expanded={open}
            className="inline-flex h-8 min-w-0 flex-1 items-center justify-between gap-2 rounded-md border border-border bg-background px-2 text-xs hover:bg-accent"
          >
            <span className="flex min-w-0 items-center gap-1.5">
              {selectedThread ? (
                <>
                  <img
                    src={agentIconSrcByTool[selectedThread.agenticTool]}
                    alt=""
                    data-testid="ai-chat-thread-switcher-agent-icon"
                    className="h-4 w-4 shrink-0 rounded-sm"
                    aria-hidden="true"
                  />
                  <ThreadStatusIcon
                    status={selectedThread.status}
                    unread={isUnread(selectedThread, userId, workspaceId)}
                    className="h-4 w-4 shrink-0"
                  />
                </>
              ) : (
                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              )}
              <span className="truncate">
                {selectedTitle ?? t('aiChat.threadList.empty')}
              </span>
            </span>
            <ChevronDown
              className={cn('h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
              aria-hidden="true"
            />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-2">
          <div className="space-y-1">
            {recentThreads.length > 0 ? (
              recentThreads.map((thread) => (
                <button
                  key={thread.id}
                  type="button"
                  aria-label={resolveThreadTitle(thread.title, t)}
                  className={cn(
                    'flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent',
                    thread.id === selectedThreadId && 'bg-accent text-accent-foreground',
                  )}
                  onClick={() => handleSelect(thread.id)}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <img
                      src={agentIconSrcByTool[thread.agenticTool]}
                      alt=""
                      data-testid="ai-chat-thread-switcher-item-agent-icon"
                      className="h-4 w-4 shrink-0 rounded-sm"
                      aria-hidden="true"
                    />
                    <ThreadStatusIcon
                      status={thread.status}
                      unread={isUnread(thread, userId, workspaceId)}
                      className="h-4 w-4 shrink-0"
                    />
                    <span className="truncate">{resolveThreadTitle(thread.title, t)}</span>
                  </span>
                  {thread.id === selectedThreadId && <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
                </button>
              ))
            ) : (
              <div className="px-2 py-2 text-xs text-muted-foreground">{t('aiChat.threadList.empty')}</div>
            )}
          </div>
        </PopoverContent>
      </Popover>
      <button
        type="button"
        aria-label={t('aiChat.threadList.newThread')}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={onNewThread}
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
};
