import { describe, expect, it } from 'vitest';
import { QueryClient, type InfiniteData } from '@tanstack/react-query';
import type { ThreadTimelinePage, TimelineMessageItem } from '../model/threadTimelineModel';
import { aiChatThreadTimelineQueryKey } from '../api/threadQueryKeys';
import { mergeThreadTimelineSnapshot } from './useThreadTimeline';

const item = (sequence: number, itemVersion = sequence): TimelineMessageItem => ({
  id: String(sequence), sequence, itemVersion, turnId: 'turn-1',
  turnExecutionId: 'execution-1', type: 'agent_text', parentItemId: null,
  content: { parts: [{ type: 'text', text: String(sequence) }] },
  createdAt: '2026-07-15T00:00:00Z',
});

const page = (items: TimelineMessageItem[]): ThreadTimelinePage => ({
  items, turns: [], executions: [],
  pageInfo: { oldestSequence: items[0]?.sequence ?? null, newestSequence: items.at(-1)?.sequence ?? null, nextBeforeSequence: null, hasMoreBefore: false },
});

const getTimelineData = (
  queryClient: QueryClient,
): InfiniteData<ThreadTimelinePage, number | undefined> | undefined =>
  queryClient.getQueryData(aiChatThreadTimelineQueryKey('workspace-1', 'thread-1'));

describe('mergeThreadTimelineSnapshot', () => {
  it('updates an existing item by itemVersion without inserting a duplicate', () => {
    const queryClient = new QueryClient();
    const current: InfiniteData<ThreadTimelinePage, number | undefined> = {
      pages: [page([item(1, 1)])], pageParams: [undefined],
    };
    queryClient.setQueryData(aiChatThreadTimelineQueryKey('workspace-1', 'thread-1'), current);

    mergeThreadTimelineSnapshot(
      queryClient,
      'workspace-1',
      'thread-1',
      { items: [item(1, 2)], turns: [], executions: [] },
    );

    const merged = getTimelineData(queryClient);
    expect(merged?.pages[0]?.items).toEqual([item(1, 2)]);
  });

  it('limits the cache to a fixed number of message items', () => {
    const queryClient = new QueryClient();
    const current: InfiniteData<ThreadTimelinePage, number | undefined> = {
      pages: [page(Array.from({ length: 500 }, (_, index) => item(index + 1)))],
      pageParams: [undefined],
    };
    queryClient.setQueryData(aiChatThreadTimelineQueryKey('workspace-1', 'thread-1'), current);

    mergeThreadTimelineSnapshot(
      queryClient,
      'workspace-1',
      'thread-1',
      { items: [item(501)], turns: [], executions: [] },
    );

    const merged = getTimelineData(queryClient);
    expect(merged?.pages.flatMap((value) => value.items)).toHaveLength(500);
    expect(merged?.pages[0]?.items[0]?.id).toBe('2');
  });
});
