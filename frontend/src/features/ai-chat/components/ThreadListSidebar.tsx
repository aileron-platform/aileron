import { MessageSquare } from 'lucide-react';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { useI18n } from '@/shared/hooks/useI18n';
import type { ThreadSummary } from '../model/threadModel';
import { ThreadListItem } from './ThreadListItem';

interface ThreadListSidebarProps {
  workspaceId: string;
  userId: string;
  selectedThreadId: string | null;
  threads: ThreadSummary[];
  isLoading: boolean;
  onSelect: (threadId: string) => void;
  onArchive: (threadId: string) => void;
  onDelete: (threadId: string) => void;
}

export const ThreadListSidebar = ({
  workspaceId,
  userId,
  selectedThreadId,
  threads,
  isLoading,
  onSelect,
  onArchive,
  onDelete,
}: ThreadListSidebarProps) => {
  const { t } = useI18n();

  const emptyState = (
    <div
      data-testid="ai-chat-thread-list-empty"
      className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center"
    >
      <div className="rounded-full bg-muted p-3 text-muted-foreground">
        <MessageSquare className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{t('aiChat.threadList.emptyTitle')}</p>
        <p className="text-sm text-muted-foreground">{t('aiChat.threadList.emptyDescription')}</p>
      </div>
    </div>
  );

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col bg-background">
      <ScrollArea className="min-h-0 flex-1">
        <div data-testid="ai-chat-thread-list-content" className="h-full w-full min-w-0 max-w-full space-y-1 p-2">
          {isLoading ? (
            <div className="px-3 py-4 text-sm text-muted-foreground">{t('aiChat.threadList.loading')}</div>
          ) : threads.length === 0 ? (
            emptyState
          ) : (
            threads.map((thread) => (
              <ThreadListItem
                key={thread.id}
                thread={thread}
                workspaceId={workspaceId}
                userId={userId}
                selected={thread.id === selectedThreadId}
                onSelect={onSelect}
                onArchive={onArchive}
                onDelete={onDelete}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </aside>
  );
};
