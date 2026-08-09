import { StrictMode, type ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { NekoClientCallbacks } from '../lib/nekoProtocol';
import { useNekoStream } from './useNekoStream';

const mocks = vi.hoisted(() => ({
  callbacks: null as NekoClientCallbacks | null,
  callbackHistory: [] as NekoClientCallbacks[],
  sequence: [] as string[],
  connect: vi.fn(),
  disconnect: vi.fn(),
}));

vi.mock('../lib/nekoClient', () => ({
  NekoClient: class {
    constructor(callbacks: NekoClientCallbacks) {
      mocks.callbacks = callbacks;
      mocks.callbackHistory.push(callbacks);
    }

    connect(...args: unknown[]): void {
      mocks.connect(...args);
    }

    disconnect(): void {
      mocks.sequence.push('disconnect');
      mocks.disconnect();
    }
  },
}));

vi.mock('../lib/inputHandler', () => ({
  attachInputHandlers: vi.fn(() => () => {
    mocks.sequence.push('detach');
  }),
}));

describe('useNekoStream', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mocks.callbacks = null;
    mocks.callbackHistory.length = 0;
    mocks.sequence.length = 0;
    mocks.connect.mockClear();
    mocks.disconnect.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('detaches input handlers before disconnecting the client', () => {
    const { result, unmount } = renderHook(() =>
      useNekoStream({ url: 'ws://browser.example.test/ws', password: 'derived-password', generation: 1 })
    );
    const video = document.createElement('video');

    act(() => {
      vi.runOnlyPendingTimers();
      result.current.videoRef.current = video;
      mocks.callbacks?.onConnectionStateChange?.('connected');
    });

    mocks.sequence.length = 0;
    unmount();

    expect(mocks.sequence).toEqual(['detach', 'disconnect']);
  });

  it('opens one WebSocket when React Strict Mode probes the effect lifecycle', () => {
    const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;
    const { unmount } = renderHook(
      () => useNekoStream({ url: 'ws://browser.example/ws', password: 'derived-password', generation: 1 }),
      { wrapper }
    );

    expect(mocks.connect).not.toHaveBeenCalled();

    act(() => {
      vi.runOnlyPendingTimers();
    });

    expect(mocks.connect).toHaveBeenCalledTimes(1);
    expect(mocks.connect).toHaveBeenCalledWith(
      'ws://browser.example/ws',
      'derived-password',
      'user',
      [],
    );

    unmount();
    expect(mocks.disconnect).toHaveBeenCalledTimes(1);
  });

  it('ignores callbacks from a client replaced after the URL changes', () => {
    const { result, rerender } = renderHook(
      ({ url }: { url: string }) => useNekoStream({ url, password: 'derived-password', generation: 1 }),
      { initialProps: { url: 'ws://browser-one.example/ws' } }
    );
    act(() => {
      vi.runOnlyPendingTimers();
    });
    const staleCallbacks = mocks.callbackHistory[0];

    rerender({ url: 'ws://browser-two.example/ws' });
    act(() => {
      vi.runOnlyPendingTimers();
    });
    const currentCallbacks = mocks.callbackHistory[1];

    act(() => {
      currentCallbacks.onConnectionStateChange?.('connecting');
      staleCallbacks.onError?.(new Error('stale error'));
      staleCallbacks.onConnectionStateChange?.('failed');
      vi.advanceTimersByTime(3000);
    });

    expect(result.current.connectionState).toBe('connecting');
    expect(result.current.error).toBeNull();
    expect(mocks.connect).toHaveBeenCalledTimes(2);
  });

  it('replaces the complete client when the access generation changes', () => {
    const { rerender } = renderHook(
      ({ generation }: { generation: number }) => useNekoStream({
        url: 'ws://browser.example/ws',
        password: 'derived-password',
        generation,
      }),
      { initialProps: { generation: 1 } },
    );
    act(() => {
      vi.runOnlyPendingTimers();
    });

    rerender({ generation: 2 });
    act(() => {
      vi.runOnlyPendingTimers();
    });

    expect(mocks.connect).toHaveBeenCalledTimes(2);
    expect(mocks.disconnect).toHaveBeenCalledTimes(1);
  });

  it('clears media element streams during cleanup', () => {
    const { result, unmount } = renderHook(() =>
      useNekoStream({ url: 'ws://browser.example/ws', password: 'derived-password', generation: 1 })
    );
    act(() => {
      vi.runOnlyPendingTimers();
    });
    const video = document.createElement('video');
    const audio = document.createElement('audio');
    const stream = {
      getVideoTracks: () => [{}],
      getAudioTracks: () => [{}],
    } as unknown as MediaStream;

    act(() => {
      result.current.videoRef.current = video;
      result.current.audioRef.current = audio;
      mocks.callbacks?.onTrack?.({ streams: [stream] } as RTCTrackEvent);
    });
    expect(video.srcObject).toBe(stream);
    expect(audio.srcObject).toBe(stream);

    unmount();

    expect(video.srcObject).toBeNull();
    expect(audio.srcObject).toBeNull();
  });
});
