// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ThreadTimelinePage } from '../../model/threadTimelineModel';
import { ThreadTimeline } from './ThreadTimeline';

const mocks = vi.hoisted(() => ({
  useThreadTimeline: vi.fn(),
  useShowInitMessages: vi.fn(),
  messageList: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (params ? `${key} ${JSON.stringify(params)}` : key),
  }),
}));

vi.mock('../../hooks/useThreadTimeline', () => ({
  useThreadTimeline: (...args: unknown[]) => mocks.useThreadTimeline(...args),
}));

vi.mock('../../hooks/useShowInitMessages', () => ({
  useShowInitMessages: () => mocks.useShowInitMessages(),
}));

vi.mock('../../realtime/threadEvents', () => ({
  subscribeThreadEvents: () => () => {},
}));

// jsdom never lays out elements (offsetHeight/getBoundingClientRect always report 0),
// so the real @tanstack/react-virtual would never report any virtual items to render.
// Mirror the workaround already used by CommitHistoryPanel.test.tsx: stub the virtualizer
// so it always renders one row per timeline entry, matching the real component's behavior
// once the DOM actually has size.
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (options: {
    count: number;
    estimateSize: (index: number) => number;
    getItemKey?: (index: number) => string | number;
  }) => ({
    getVirtualItems: () => Array.from({ length: options.count }, (_, index) => ({
      index,
      start: index * options.estimateSize(index),
      key: options.getItemKey ? options.getItemKey(index) : index,
    })),
    getTotalSize: () => options.count * options.estimateSize(0),
    measureElement: () => {},
  }),
}));

vi.mock('./ThreadMessageList', () => ({
  ThreadMessageList: (props: Record<string, unknown>) => {
    mocks.messageList(props);
    return <div data-testid="message-list" />;
  },
}));

const page = (overrides: Partial<ThreadTimelinePage> = {}): ThreadTimelinePage => ({
  items: [
    {
      id: 'item-1', sequence: 1, itemVersion: 1, turnId: 'turn-1', turnExecutionId: 'execution-1',
      type: 'agent_text', parentItemId: null, content: { parts: [{ type: 'text', text: 'Hi' }] },
      createdAt: '2026-07-15T00:00:00Z',
    },
  ],
  turns: [{
    id: 'turn-1', sequence: 1, version: 1, status: 'complete',
    errorCode: null, errorInfo: null, createdAt: '2026-07-15T00:00:00Z', completedAt: '2026-07-15T00:01:00Z',
  }],
  executions: [],
  pageInfo: { oldestSequence: 1, newestSequence: 1, nextBeforeSequence: null, hasMoreBefore: false },
  ...overrides,
});

const baseQuery = (overrides: Record<string, unknown> = {}) => ({
  data: { pages: [page()], pageParams: [undefined] },
  isLoading: false,
  isError: false,
  hasNextPage: false,
  isFetchingNextPage: false,
  fetchNextPage: vi.fn(async () => {}),
  refetch: vi.fn(),
  ...overrides,
});

const renderTimeline = (queryOverrides: Record<string, unknown> = {}) => {
  mocks.useThreadTimeline.mockReturnValue(baseQuery(queryOverrides));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const scrollContainerRef = createRef<HTMLDivElement>();
  render(
    <QueryClientProvider client={queryClient}>
      <div ref={scrollContainerRef}>
        <ThreadTimeline workspaceId="workspace-1" threadId="thread-1" scrollContainerRef={scrollContainerRef} />
      </div>
    </QueryClientProvider>,
  );
  return { scrollContainerRef };
};

beforeEach(() => {
  mocks.useThreadTimeline.mockReset();
  mocks.useShowInitMessages.mockReset();
  mocks.useShowInitMessages.mockReturnValue([false, vi.fn()]);
  mocks.messageList.mockClear();
});

afterEach(() => {
  cleanup();
});

describe('ThreadTimeline', () => {
  it('passes the show-init-messages preference down to each rendered turn', () => {
    mocks.useShowInitMessages.mockReturnValue([true, vi.fn()]);

    renderTimeline();

    expect(mocks.messageList).toHaveBeenCalledWith(
      expect.objectContaining({ showInitMessages: true }),
    );
  });

  it('does not auto-fetch older messages when the scroll container is near the top', () => {
    const fetchNextPage = vi.fn(async () => {});
    const { scrollContainerRef } = renderTimeline({ hasNextPage: true, fetchNextPage });
    const container = scrollContainerRef.current as HTMLDivElement;
    Object.defineProperty(container, 'scrollTop', { value: 0, configurable: true });

    fireEvent.scroll(container);

    expect(fetchNextPage).not.toHaveBeenCalled();
  });

  it('does not render a load-older control when there is no older page', () => {
    renderTimeline({ hasNextPage: false });

    expect(screen.queryByRole('button', { name: 'aiChat.messages.loadOlder' })).not.toBeInTheDocument();
  });

  it('shows a disabled loading button while fetching the next page', () => {
    renderTimeline({ hasNextPage: true, isFetchingNextPage: true });

    const button = screen.getByRole('button', { name: 'aiChat.messages.loadingOlder' });
    expect(button).toBeDisabled();
  });

  it('fetches older messages on click and restores the scroll offset after loading', async () => {
    const user = userEvent.setup();
    const fetchNextPage = vi.fn(async () => {
      Object.defineProperty(container, 'scrollHeight', { value: 1400, configurable: true });
    });
    const { scrollContainerRef } = renderTimeline({ hasNextPage: true, fetchNextPage });
    const container = scrollContainerRef.current as HTMLDivElement;
    Object.defineProperty(container, 'scrollHeight', { value: 1000, configurable: true });
    Object.defineProperty(container, 'scrollTop', { value: 50, configurable: true, writable: true });

    await user.click(screen.getByRole('button', { name: 'aiChat.messages.loadOlder' }));

    expect(fetchNextPage).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(container.scrollTop).toBe(450);
    });
  });
});
