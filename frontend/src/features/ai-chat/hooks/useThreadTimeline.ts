import { useInfiniteQuery, useQuery, type InfiniteData, type QueryClient } from '@tanstack/react-query';
import type {
  ThreadExecutionMetadata,
  ThreadTimelinePage,
  ThreadTurnMetadata,
  TimelineItems,
  TimelineMessageItem,
} from '../model/threadTimelineModel';
import { requireThreadApi, useThreadApi } from './useThreadApi';
import { aiChatThreadTimelineQueryKey, aiChatToolResultQueryKey } from '../api/threadQueryKeys';

const AI_CHAT_TIMELINE_PAGE_SIZE = 100;
const AI_CHAT_TIMELINE_MAX_PAGES = 5;
const AI_CHAT_TIMELINE_MAX_ITEMS = 500;

const mergeByVersion = <T extends { id: string; version: number }>(
  current: T[],
  incoming: T[],
): T[] => {
  const byId = new Map(current.map((item) => [item.id, item]));
  incoming.forEach((item) => {
    const existing = byId.get(item.id);
    if (!existing || item.version >= existing.version) byId.set(item.id, item);
  });
  return [...byId.values()];
};

const mergeItems = (
  current: TimelineMessageItem[],
  incoming: TimelineMessageItem[],
): TimelineMessageItem[] => {
  const byId = new Map(current.map((item) => [item.id, item]));
  incoming.forEach((item) => {
    const existing = byId.get(item.id);
    if (!existing || item.itemVersion >= existing.itemVersion) byId.set(item.id, item);
  });
  return [...byId.values()].sort((left, right) => left.sequence - right.sequence);
};

const mergeTimelineSnapshot = (
  current: InfiniteData<ThreadTimelinePage, number | undefined> | undefined,
  incoming: TimelineItems,
): InfiniteData<ThreadTimelinePage, number | undefined> | undefined => {
  if (!current?.pages[0]) return current;
  const foundIds = new Set<string>();
  const pages = current.pages.map((page) => {
    const replacements = incoming.items.filter((item) =>
      page.items.some((existing) => existing.id === item.id),
    );
    replacements.forEach((item) => foundIds.add(item.id));
    return {
      ...page,
      items: mergeItems(page.items, replacements),
      turns: mergeByVersion(page.turns, incoming.turns),
      executions: mergeByVersion(page.executions, incoming.executions),
    };
  });
  const additions = current.pageParams[0] === undefined
    ? incoming.items.filter((item) => !foundIds.has(item.id))
    : [];
  pages[0] = {
    ...pages[0],
    items: mergeItems(pages[0].items, additions),
    turns: mergeByVersion(pages[0].turns, incoming.turns),
    executions: mergeByVersion(pages[0].executions, incoming.executions),
  };

  let retained = 0;
  const boundedPages = pages.flatMap((page) => {
    const remaining = AI_CHAT_TIMELINE_MAX_ITEMS - retained;
    if (remaining <= 0) return [];
    const items = page.items.slice(-remaining);
    retained += items.length;
    return [{ ...page, items }];
  });
  return {
    ...current,
    pages: boundedPages,
    pageParams: current.pageParams.slice(0, boundedPages.length),
  };
};

export const mergeThreadTimelineSnapshot = (
  queryClient: QueryClient,
  workspaceId: string,
  threadId: string,
  incoming: TimelineItems,
): void => {
  queryClient.setQueryData(
    aiChatThreadTimelineQueryKey(workspaceId, threadId),
    (current: InfiniteData<ThreadTimelinePage, number | undefined> | undefined) =>
      mergeTimelineSnapshot(current, incoming),
  );
};

export const useThreadTimeline = (
  workspaceId: string,
  threadId: string | null | undefined,
  runtimeBaseUrl?: string | null,
) => {
  const api = useThreadApi(runtimeBaseUrl);
  return useInfiniteQuery({
    queryKey: aiChatThreadTimelineQueryKey(workspaceId, threadId ?? ''),
    queryFn: ({ pageParam }) => requireThreadApi(api).getTimeline(
      threadId ?? '',
      pageParam,
      AI_CHAT_TIMELINE_PAGE_SIZE,
    ),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage) => lastPage.pageInfo.hasMoreBefore
      ? lastPage.pageInfo.nextBeforeSequence ?? undefined
      : undefined,
    maxPages: AI_CHAT_TIMELINE_MAX_PAGES,
    enabled: Boolean(workspaceId && threadId) && api !== null,
  });
};

export const useToolResultContent = (
  workspaceId: string,
  threadId: string,
  messageId: string,
  enabled: boolean,
  runtimeBaseUrl?: string | null,
) => {
  const api = useThreadApi(runtimeBaseUrl);
  return useQuery({
    queryKey: aiChatToolResultQueryKey(workspaceId, threadId, messageId),
    queryFn: () => requireThreadApi(api).getToolResultContent(threadId, messageId),
    enabled: enabled && api !== null,
    gcTime: 0,
    staleTime: 0,
    retry: false,
  });
};
