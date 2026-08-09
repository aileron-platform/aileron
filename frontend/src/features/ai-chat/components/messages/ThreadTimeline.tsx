import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import { useThreadTimeline } from '../../hooks/useThreadTimeline';
import { useShowInitMessages } from '../../hooks/useShowInitMessages';
import { aiChatThreadTimelineQueryKey } from '../../api/threadQueryKeys';
import { subscribeThreadEvents } from '../../realtime/threadEvents';
import { ThreadMessageList } from './ThreadMessageList';
import { ToolResultContext } from './ToolResultContext';

const AI_CHAT_TIMELINE_OVERSCAN = 8;

interface ThreadTimelineProps {
  workspaceId: string;
  threadId: string;
  scrollContainerRef: RefObject<HTMLDivElement | null>;
  runtimeBaseUrl?: string | null;
}

export const ThreadTimeline = ({
  workspaceId,
  threadId,
  scrollContainerRef,
  runtimeBaseUrl,
}: ThreadTimelineProps) => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const query = useThreadTimeline(workspaceId, threadId, runtimeBaseUrl);
  const [showInitMessages] = useShowInitMessages();
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = query;
  const loadingOlderRef = useRef(false);
  const [unreadItemIds, setUnreadItemIds] = useState<Set<string>>(new Set());
  const latestPageEvicted = query.data?.pageParams[0] !== undefined;
  const presentation = useMemo(() => {
    const pages = [...(query.data?.pages ?? [])].reverse();
    const items = pages.flatMap((page) => page.items);
    const turnsById = new Map(pages.flatMap((page) => page.turns).map((turn) => [turn.id, turn]));
    const executions = pages.flatMap((page) => page.executions);
    const itemsByTurn = new Map<string, typeof items>();
    items.forEach((item) => itemsByTurn.set(item.turnId, [...(itemsByTurn.get(item.turnId) ?? []), item]));
    return [...itemsByTurn.entries()].flatMap(([turnId, turnItems]) => {
      const turn = turnsById.get(turnId);
      return turn ? [{ turn, items: turnItems, executions }] : [];
    }).sort((left, right) => left.turn.sequence - right.turn.sequence);
  },
    [query.data?.pages],
  );
  const virtualizer = useVirtualizer({
    count: presentation.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 220,
    getItemKey: (index) => presentation[index]?.turn.id ?? index,
    measureElement: (element) => element.getBoundingClientRect().height,
    overscan: AI_CHAT_TIMELINE_OVERSCAN,
  });

  useEffect(() => subscribeThreadEvents(workspaceId, (event) => {
    if (event.type !== 'timeline_updated' || event.threadId !== threadId) return;
    const container = scrollContainerRef.current;
    if (!container) return;
    const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 10;
    if (atBottom) return;
    setUnreadItemIds((current) => new Set([...current, ...event.createdItemIds, ...event.changedItemIds]));
  }), [scrollContainerRef, threadId, workspaceId]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return undefined;
    const handleScroll = () => {
      if (container.scrollTop + container.clientHeight >= container.scrollHeight - 10) {
        setUnreadItemIds(new Set());
      }
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [scrollContainerRef]);

  const handleLoadOlder = async () => {
    const container = scrollContainerRef.current;
    if (!container || !hasNextPage || isFetchingNextPage || loadingOlderRef.current) return;
    loadingOlderRef.current = true;
    const previousHeight = container.scrollHeight;
    const previousTop = container.scrollTop;
    try {
      await fetchNextPage();
      window.requestAnimationFrame(() => {
        container.scrollTop = previousTop + (container.scrollHeight - previousHeight);
      });
    } finally {
      loadingOlderRef.current = false;
    }
  };

  if (query.isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{t('aiChat.messages.loading')}</p>;
  }
  if (query.isError && presentation.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="mb-3 text-sm text-destructive">{t('aiChat.messages.loadFailed')}</p>
        <Button type="button" variant="outline" onClick={() => void query.refetch()}>
          {t('aiChat.messages.retry')}
        </Button>
      </div>
    );
  }
  if (presentation.length === 0) return null;

  const returnToLatest = async () => {
    if (latestPageEvicted) {
      await queryClient.resetQueries({
        queryKey: aiChatThreadTimelineQueryKey(workspaceId, threadId),
        exact: true,
      });
    }
    const container = scrollContainerRef.current;
    if (container) container.scrollTop = container.scrollHeight;
    setUnreadItemIds(new Set());
  };

  return (
    <ToolResultContext.Provider value={{ workspaceId, threadId, runtimeBaseUrl }}>
      <div className="space-y-2">
        {query.hasNextPage && (
          <div className="flex justify-center py-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleLoadOlder()}
              disabled={query.isFetchingNextPage}
            >
              {query.isFetchingNextPage
                ? t('aiChat.messages.loadingOlder')
                : t('aiChat.messages.loadOlder')}
            </Button>
          </div>
        )}
        <div
          className="relative w-full"
          style={{ height: virtualizer.getTotalSize() }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = presentation[virtualRow.index];
            if (!row) return null;
            return (
              <div
                key={row.turn.id}
                ref={virtualizer.measureElement}
                data-index={virtualRow.index}
                data-testid="ai-chat-timeline-row"
                className="absolute left-0 top-0 w-full pb-3"
                style={{ transform: `translateY(${virtualRow.start}px)` }}
              >
                <ThreadMessageList
                  items={row.items}
                  turn={row.turn}
                  executions={row.executions}
                  showInitMessages={showInitMessages}
                />
              </div>
            );
          })}
        </div>
        {query.isError && presentation.length > 0 && (
          <div className="flex justify-center py-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => void query.fetchNextPage()}>
              {t('aiChat.messages.retryOlder')}
            </Button>
          </div>
        )}
        {(latestPageEvicted || unreadItemIds.size > 0) && (
          <div className="sticky bottom-2 flex justify-center">
            <Button type="button" size="sm" onClick={() => void returnToLatest()}>
              {latestPageEvicted
                ? t('aiChat.messages.returnToLatest')
                : t('aiChat.messages.newUpdates', { count: unreadItemIds.size })}
            </Button>
          </div>
        )}
      </div>
    </ToolResultContext.Provider>
  );
};
