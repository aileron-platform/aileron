// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { subscribeThreadEvents, useThreadEvents } from './threadEvents';
import { executionGrantBroker } from '@/features/auth/public';

vi.mock('@/features/auth/public', () => ({
  executionGrantBroker: {
    registerTarget: vi.fn(),
    getGrant: vi.fn(() => 'signed-grant'),
  },
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  readonly url: string;
  readonly protocols: string[];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string, protocols: string[] = []) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  close() {}

  open() {
    this.onopen?.();
  }

  message(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  disconnect() {
    this.onclose?.();
  }
}

describe('useThreadEvents', () => {
  const workspaceId = 'e0e4aba0-8442-4851-a9c4-5c45f9e74fb6';
  let queryClient: QueryClient;
  let invalidateQueries: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries').mockResolvedValue();
  });

  afterEach(() => {
    queryClient.clear();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const renderEvents = () => renderHook(
    () => useThreadEvents(workspaceId, `/workspaces/${workspaceId}/runtime`, true),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    },
  );

  it('keeps the bearer out of the URL and sends it through WebSocket protocols', () => {
    renderEvents();

    expect(FakeWebSocket.instances[0]?.url).toBe(
      `ws://${window.location.host}/workspaces/${workspaceId}/runtime/api/v1/threads/events`,
    );
    expect(FakeWebSocket.instances[0]?.url).not.toContain('signed-grant');
    expect(FakeWebSocket.instances[0]?.protocols).toEqual([
      'aileron-thread-v1',
      'bearer.c2lnbmVkLWdyYW50',
    ]);
  });

  it('fails closed without a bearer token', () => {
    vi.mocked(executionGrantBroker.getGrant).mockImplementationOnce(() => {
      throw new Error('grant unavailable');
    });

    renderEvents();

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('does not open a WebSocket when thread events are disabled', () => {
    renderHook(
      () => useThreadEvents('workspace-1', 'https://runtime.test', false),
      {
        wrapper: ({ children }: { children: ReactNode }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      },
    );

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it.each(['archived', 'status_updated', 'error'] as const)(
    'invalidates detail and list for %s',
    async (type) => {
      renderEvents();
      const subscriber = vi.fn();
      const unsubscribe = subscribeThreadEvents(workspaceId, subscriber);
      const event = { threadId: 'thread-1', type, ...(type === 'status_updated' ? { status: 'working' } : {}) };

      await act(async () => {
        FakeWebSocket.instances[0]?.message(event);
      });

      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'thread', workspaceId, 'thread-1'] });
      expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'threads', workspaceId] });
      expect(subscriber).toHaveBeenCalledWith({
        ...event,
        createdItemIds: [],
        changedItemIds: [],
        turns: [],
        executions: [],
        refreshLatest: false,
      });
      unsubscribe();
    },
  );

  it('invalidates only thread detail for messages_updated', async () => {
    renderEvents();

    await act(async () => {
      FakeWebSocket.instances[0]?.message({ threadId: 'thread-1', type: 'messages_updated' });
    });

    expect(invalidateQueries).toHaveBeenCalledTimes(1);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'thread', workspaceId, 'thread-1'] });
  });

  it('removes detail and invalidates the list prefix for deleted', async () => {
    const removeQueries = vi.spyOn(queryClient, 'removeQueries');
    renderEvents();
    const subscriber = vi.fn();
    const unsubscribe = subscribeThreadEvents(workspaceId, subscriber);

    await act(async () => {
      FakeWebSocket.instances[0]?.message({ threadId: 'thread-1', type: 'deleted' });
    });

    expect(removeQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'thread', workspaceId, 'thread-1'] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'threads', workspaceId] });
    expect(subscriber).toHaveBeenCalledWith({
      threadId: 'thread-1',
      type: 'deleted',
      createdItemIds: [],
      changedItemIds: [],
      turns: [],
      executions: [],
      refreshLatest: false,
    });
    unsubscribe();
  });

  it('invalidates only the list prefix for thread_created', async () => {
    renderEvents();

    await act(async () => {
      FakeWebSocket.instances[0]?.message({ threadId: 'thread-2', type: 'thread_created' });
    });

    expect(invalidateQueries).toHaveBeenCalledTimes(1);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'threads', workspaceId] });
  });

  it('uses prefix invalidation for active and archived list variants', async () => {
    invalidateQueries.mockRestore();
    queryClient.setQueryData(['ai-chat', 'threads', workspaceId, false], []);
    queryClient.setQueryData(['ai-chat', 'threads', workspaceId, true], []);
    renderEvents();

    await act(async () => {
      FakeWebSocket.instances[0]?.message({ threadId: 'thread-2', type: 'thread_created' });
      await Promise.resolve();
    });

    expect(queryClient.getQueryState(['ai-chat', 'threads', workspaceId, false])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(['ai-chat', 'threads', workspaceId, true])?.isInvalidated).toBe(true);
  });

  it('reconnects with backoff and invalidates the full list prefix after reopening', async () => {
    renderEvents();
    FakeWebSocket.instances[0]?.open();
    invalidateQueries.mockClear();

    act(() => {
      FakeWebSocket.instances[0]?.disconnect();
      vi.runOnlyPendingTimers();
    });
    expect(FakeWebSocket.instances).toHaveLength(2);

    await act(async () => {
      FakeWebSocket.instances[1]?.open();
    });

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['ai-chat', 'threads', workspaceId] });
  });

  it('reconnects immediately when the browser comes back online', () => {
    renderEvents();
    FakeWebSocket.instances[0]?.open();

    act(() => {
      FakeWebSocket.instances[0]?.disconnect();
      window.dispatchEvent(new Event('online'));
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
  });
});
