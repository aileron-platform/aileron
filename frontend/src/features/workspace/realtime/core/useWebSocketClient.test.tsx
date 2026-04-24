import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useWebSocketClient } from './useWebSocketClient';

type ListenerMap = Map<string, Set<(event?: any) => void>>;

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  static OPEN = 1;
  static CLOSED = 3;

  readyState = 0;
  url: string;
  listeners: ListenerMap = new Map();
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event?: any) => void) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: (event?: any) => void) {
    this.listeners.get(type)?.delete(listener);
  }

  send(message: string) {
    this.sentMessages.push(message);
  }

  close(code = 1000, reason = '') {
    this.readyState = MockWebSocket.CLOSED;
    this.emit('close', { code, reason });
  }

  emit(type: string, event: any = {}) {
    if (type === 'open') {
      this.readyState = MockWebSocket.OPEN;
    }
    if (type === 'close') {
      this.readyState = MockWebSocket.CLOSED;
    }
    this.listeners.get(type)?.forEach(listener => listener(event));
  }
}

describe('useWebSocketClient', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('切換 session 時忽略舊 socket 的 close 事件，不回連到舊 session', () => {
    const { rerender } = renderHook(
      ({ sessionId }) =>
        useWebSocketClient({
          runtimeBaseUrl: 'http://runtime.test',
          workspaceId: 'ws-1',
          sessionId,
          autoConnect: true,
        }),
      {
        initialProps: { sessionId: 'session-old' },
      }
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    const firstSocket = MockWebSocket.instances[0]!;

    act(() => {
      firstSocket.emit('open');
    });

    rerender({ sessionId: 'session-new' });

    expect(MockWebSocket.instances).toHaveLength(2);
    const secondSocket = MockWebSocket.instances[1]!;

    act(() => {
      firstSocket.emit('close', { code: 1006, reason: 'stale socket closed late' });
      vi.runOnlyPendingTimers();
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    expect(secondSocket.url).toContain('/api/v1/ws/agent-sessions/session-new');
  });

  it('當前 socket 異常關閉時仍會重連目前 session', () => {
    renderHook(() =>
      useWebSocketClient({
        runtimeBaseUrl: 'http://runtime.test',
        workspaceId: 'ws-1',
        sessionId: 'session-live',
        autoConnect: true,
      })
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    const activeSocket = MockWebSocket.instances[0]!;

    act(() => {
      activeSocket.emit('open');
      activeSocket.emit('close', { code: 1006, reason: 'network lost' });
      vi.advanceTimersByTime(500);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1]!.url).toContain('/api/v1/ws/agent-sessions/session-live');
  });

  it('相同 session 與 runtime 重新 render 時不會建立新 socket', () => {
    const { rerender } = renderHook(
      ({ sessionId, runtimeBaseUrl }) =>
        useWebSocketClient({
          runtimeBaseUrl,
          workspaceId: 'ws-1',
          sessionId,
          autoConnect: true,
        }),
      {
        initialProps: {
          sessionId: 'session-stable',
          runtimeBaseUrl: 'http://runtime.test',
        },
      }
    );

    expect(MockWebSocket.instances).toHaveLength(1);

    rerender({
      sessionId: 'session-stable',
      runtimeBaseUrl: 'http://runtime.test',
    });

    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
