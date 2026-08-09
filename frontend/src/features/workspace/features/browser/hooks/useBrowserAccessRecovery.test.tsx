import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { NekoConnectionState } from '../lib/nekoProtocol';
import { useBrowserAccessRecovery } from './useBrowserAccessRecovery';

const access = (revision: number) => ({
  browserUrl: '/workspaces/workspace-1/browser',
  password: `password-${revision}`,
  credentialRevision: revision,
  iceServers: [],
});

describe('useBrowserAccessRecovery', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('requests fresh access before replacing a failed stream generation', async () => {
    const requestAccess = vi.fn()
      .mockResolvedValueOnce(access(1))
      .mockResolvedValueOnce(access(2));
    const { result, rerender } = renderHook(
      ({ connectionState }: { connectionState: NekoConnectionState }) =>
        useBrowserAccessRecovery({
          workspaceId: 'workspace-1',
          enabled: true,
          connectionState,
          requestAccess,
        }),
      { initialProps: { connectionState: 'disconnected' as NekoConnectionState } },
    );

    await act(async () => Promise.resolve());
    expect(result.current.generation).toBe(1);

    rerender({ connectionState: 'connecting' });
    rerender({ connectionState: 'failed' });
    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
    });

    expect(requestAccess).toHaveBeenCalledTimes(2);
    expect(result.current.access?.credentialRevision).toBe(2);
    expect(result.current.generation).toBe(2);

    await act(async () => {
      vi.advanceTimersByTime(2_000);
      await Promise.resolve();
    });
    expect(requestAccess).toHaveBeenCalledTimes(2);
  });

  it('retries a transient access API failure after the bounded delay', async () => {
    const requestAccess = vi.fn()
      .mockRejectedValueOnce(new TypeError('network changed'))
      .mockResolvedValueOnce(access(2));
    const { result } = renderHook(() => useBrowserAccessRecovery({
      workspaceId: 'workspace-1',
      enabled: true,
      connectionState: 'disconnected',
      requestAccess,
    }));

    await act(async () => Promise.resolve());
    expect(result.current.state).toBe('recovering');

    await act(async () => {
      vi.advanceTimersByTime(1_000);
      await Promise.resolve();
    });

    expect(requestAccess).toHaveBeenCalledTimes(2);
    expect(result.current.generation).toBe(1);
  });

  it('stops after five serialized attempts', async () => {
    const requestAccess = vi.fn().mockRejectedValue(new TypeError('offline'));
    const { result } = renderHook(() => useBrowserAccessRecovery({
      workspaceId: 'workspace-1',
      enabled: true,
      connectionState: 'disconnected',
      requestAccess,
    }));

    for (const delay of [0, 1_000, 2_000, 4_000, 8_000]) {
      await act(async () => {
        vi.advanceTimersByTime(delay);
        await Promise.resolve();
      });
    }

    expect(result.current.state).toBe('exhausted');
    expect(requestAccess).toHaveBeenCalledTimes(5);
    expect(result.current.errorKey).toBe('workspace.browser.error.recoveryExhausted');
  });

  it('pauses while offline and resumes on the online event', async () => {
    const requestAccess = vi.fn()
      .mockResolvedValueOnce(access(1))
      .mockResolvedValueOnce(access(2));
    const { rerender } = renderHook(
      ({ connectionState }: { connectionState: NekoConnectionState }) =>
        useBrowserAccessRecovery({
          workspaceId: 'workspace-1',
          enabled: true,
          connectionState,
          requestAccess,
        }),
      { initialProps: { connectionState: 'disconnected' as NekoConnectionState } },
    );
    await act(async () => Promise.resolve());
    Object.defineProperty(navigator, 'onLine', { configurable: true, value: false });

    rerender({ connectionState: 'connecting' });
    rerender({ connectionState: 'failed' });
    act(() => vi.advanceTimersByTime(60_000));
    expect(requestAccess).toHaveBeenCalledTimes(1);

    Object.defineProperty(navigator, 'onLine', { configurable: true, value: true });
    await act(async () => {
      window.dispatchEvent(new Event('online'));
      await Promise.resolve();
    });
    expect(requestAccess).toHaveBeenCalledTimes(2);
  });
});
