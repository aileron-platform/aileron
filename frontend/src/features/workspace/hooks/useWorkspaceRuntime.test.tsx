import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@/__tests__/utils/render';
import { useWorkspaceRuntime } from './useWorkspaceRuntime';

interface WorkspaceRuntimeResolution {
  url: string;
  detail: {
    id: string;
    agenticTools: string[];
    accessRole?: unknown;
    accessSource?: unknown;
    accessSources?: unknown;
    allowedOperations?: unknown;
    runtimeStatus: Record<string, unknown> | null;
  };
}

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
};

const mocks = vi.hoisted(() => ({
  fetchDefaultWorkspaceIdMock: vi.fn(),
  resolveRuntimeBaseUrlWithDetailMock: vi.fn(),
}));

vi.mock('../api/workspaceRuntimeApi', () => ({
  fetchDefaultWorkspaceId: (...args: unknown[]) => mocks.fetchDefaultWorkspaceIdMock(...args),
  resolveRuntimeBaseUrlWithDetail: (...args: unknown[]) => mocks.resolveRuntimeBaseUrlWithDetailMock(...args),
}));

describe('useWorkspaceRuntime', () => {
  beforeEach(() => {
    mocks.fetchDefaultWorkspaceIdMock.mockReset();
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockReset();
  });

  it('clears the previous runtime URL while switching to another workspace', async () => {
    let resolveWorkspaceBUrl: ((value: { url: string; detail: unknown }) => void) | null = null;

    mocks.resolveRuntimeBaseUrlWithDetailMock.mockImplementation((workspaceId: string) => {
      if (workspaceId === 'ws-a') {
        return Promise.resolve({
          url: 'https://runtime-a.example',
          detail: {
            id: workspaceId,
            agenticTools: ['codex', 'opencode'],
            accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
            allowedOperations: ['workspace.detail.read'],
            runtimeStatus: null,
          },
        });
      }

      if (workspaceId === 'ws-b') {
        return new Promise<{ url: string; detail: unknown }>((resolve) => {
          resolveWorkspaceBUrl = resolve;
        });
      }

      throw new Error(`Unexpected workspace: ${workspaceId}`);
    });

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useWorkspaceRuntime(workspaceId),
      {
        initialProps: { workspaceId: 'ws-a' as string | null | undefined },
      },
    );

    await waitFor(() => {
      expect(result.current.workspaceId).toBe('ws-a');
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-a.example');
    });

    rerender({ workspaceId: 'ws-b' });

    await waitFor(() => {
      expect(result.current.workspaceId).toBe('ws-b');
      expect(result.current.runtimeBaseUrl).toBeNull();
    });

    resolveWorkspaceBUrl?.({
      url: 'https://runtime-b.example',
      detail: {
        id: 'ws-b',
        agenticTools: ['opencode'],
        accessRole: 'manager',
            accessSource: 'direct_share',
            accessSources: ['direct_share'],
        allowedOperations: ['workspace.detail.read'],
        runtimeStatus: null,
      },
    });

    await waitFor(() => {
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-b.example');
    });
  });

  it('clears runtime identity without fetching a default workspace when the selection becomes null', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockResolvedValue({
      url: 'https://runtime-a.example',
      detail: {
        id: 'ws-a',
        agenticTools: ['codex'],
        accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
        allowedOperations: ['workspace.detail.read'],
        runtimeStatus: null,
      },
    });

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useWorkspaceRuntime(workspaceId),
      {
        initialProps: { workspaceId: 'ws-a' as string | null | undefined },
      },
    );

    await waitFor(() => {
      expect(result.current.workspaceId).toBe('ws-a');
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-a.example');
    });

    rerender({ workspaceId: null });

    await waitFor(() => {
      expect(result.current.workspaceId).toBeNull();
      expect(result.current.runtimeBaseUrl).toBeNull();
    });

    expect(mocks.fetchDefaultWorkspaceIdMock).not.toHaveBeenCalled();
  });

  it('exposes enabled tools without deriving a single workspace agentic tool', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockResolvedValue({
      url: 'https://runtime-a.example',
      detail: {
        id: 'ws-a',
        agenticTools: ['opencode', 'claude-code'],
        accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
        allowedOperations: ['workspace.detail.read'],
        runtimeStatus: null,
      },
    });

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-a.example');
      expect(result.current.agenticTools).toEqual(['claude-code', 'opencode']);
    });

    expect('agenticTool' in result.current).toBe(false);
  });

  it('preserves workspace authorization when the runtime has no URL', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockResolvedValue({
      url: null,
      detail: {
        id: 'ws-a',
        agenticTools: ['codex'],
        accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
        allowedOperations: [
          'workspace.detail.read',
          'workspace.agent_chat.use',
        ],
        runtimeStatus: null,
      },
    });

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.isAuthorizationResolved).toBe(true);
    });

    expect(result.current.workspaceId).toBe('ws-a');
    expect(result.current.runtimeBaseUrl).toBeNull();
    expect(result.current.accessRole).toBe('owner');
    expect(result.current.allowedOperations).toEqual([
      'workspace.detail.read',
      'workspace.agent_chat.use',
    ]);
    expect(result.current.error).toBeNull();
    expect(result.current.errorCode).toBeNull();
  });

  it('reports an error when workspace detail has no supported enabled tools', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockResolvedValue({
      url: 'https://runtime-a.example',
      detail: {
        id: 'ws-a',
        agenticTools: ['unsupported'],
        accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
        allowedOperations: ['workspace.detail.read'],
        runtimeStatus: null,
      },
    });

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.error).toBe('workspace.runtime.errors.agenticToolsUnavailable');
      expect(result.current.runtimeBaseUrl).toBeNull();
    });
    expect(result.current.agenticTools).toEqual([]);
  });

  it('keeps the latest workspace detail when an older workspace request resolves last', async () => {
    const workspaceA = createDeferred<WorkspaceRuntimeResolution>();
    const workspaceB = createDeferred<WorkspaceRuntimeResolution>();

    mocks.resolveRuntimeBaseUrlWithDetailMock.mockImplementation((workspaceId: string) => {
      if (workspaceId === 'ws-a') {
        return workspaceA.promise;
      }
      if (workspaceId === 'ws-b') {
        return workspaceB.promise;
      }
      throw new Error(`Unexpected workspace: ${workspaceId}`);
    });

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useWorkspaceRuntime(workspaceId),
      {
        initialProps: { workspaceId: 'ws-a' as string | null | undefined },
      },
    );

    await waitFor(() => {
      expect(mocks.resolveRuntimeBaseUrlWithDetailMock).toHaveBeenCalledWith(
        'ws-a',
      );
    });

    rerender({ workspaceId: 'ws-b' });

    await waitFor(() => {
      expect(mocks.resolveRuntimeBaseUrlWithDetailMock).toHaveBeenCalledWith(
        'ws-b',
      );
    });

    await act(async () => {
      workspaceB.resolve({
        url: 'https://runtime-b.example',
        detail: {
          id: 'ws-b',
          agenticTools: ['opencode'],
          accessRole: 'manager',
            accessSource: 'direct_share',
            accessSources: ['direct_share'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      });
      await workspaceB.promise;
    });

    await waitFor(() => {
      expect(result.current.workspaceId).toBe('ws-b');
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-b.example');
      expect(result.current.accessRole).toBe('manager');
    });

    await act(async () => {
      workspaceA.resolve({
        url: 'https://runtime-a.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['codex'],
          accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      });
      await workspaceA.promise;
    });

    expect(result.current.workspaceId).toBe('ws-b');
    expect(result.current.runtimeBaseUrl).toBe('https://runtime-b.example');
    expect(result.current.accessRole).toBe('manager');
  });

  it('keeps the confirmed authorization snapshot while background reloads are pending', async () => {
    const earlierReload = createDeferred<WorkspaceRuntimeResolution>();
    const latestReload = createDeferred<WorkspaceRuntimeResolution>();

    mocks.resolveRuntimeBaseUrlWithDetailMock
      .mockResolvedValueOnce({
        url: 'https://runtime-initial.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['codex'],
          accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      })
      .mockReturnValueOnce(earlierReload.promise)
      .mockReturnValueOnce(latestReload.promise);

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.accessRole).toBe('owner');
    });

    let earlierReloadPromise!: Promise<void>;
    let latestReloadPromise!: Promise<void>;
    act(() => {
      earlierReloadPromise = result.current.reload();
      latestReloadPromise = result.current.reload();
    });

    expect(result.current.accessRole).toBe('owner');
    expect(result.current.isAuthorizationResolved).toBe(true);
    expect(result.current.isLoading).toBe(false);

    await act(async () => {
      latestReload.resolve({
        url: 'https://runtime-latest.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['opencode'],
          accessRole: 'reader',
            accessSource: 'direct_share',
            accessSources: ['direct_share'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      });
      await latestReloadPromise;
    });

    await act(async () => {
      earlierReload.resolve({
        url: 'https://runtime-earlier.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['codex'],
          accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      });
      await earlierReloadPromise;
    });

    expect(result.current.runtimeBaseUrl).toBe('https://runtime-latest.example');
    expect(result.current.agenticTools).toEqual(['opencode']);
    expect(result.current.accessRole).toBe('reader');
    expect(result.current.isAuthorizationResolved).toBe(true);
  });

  it('keeps the confirmed runtime snapshot when a background reload fails transiently', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock
      .mockResolvedValueOnce({
        url: 'https://runtime-a.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['codex'],
          accessRole: 'manager',
            accessSource: 'direct_share',
            accessSources: ['direct_share'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      })
      .mockRejectedValueOnce(new Error('Network unavailable'));

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.accessRole).toBe('manager');
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.workspaceId).toBe('ws-a');
    expect(result.current.runtimeBaseUrl).toBe('https://runtime-a.example');
    expect(result.current.agenticTools).toEqual(['codex']);
    expect(result.current.accessRole).toBe('manager');
    expect(result.current.error).toBeNull();
    expect(result.current.errorCode).toBeNull();
    expect(result.current.isAuthorizationResolved).toBe(true);
    expect(mocks.resolveRuntimeBaseUrlWithDetailMock).toHaveBeenCalledTimes(2);
  });

  it('clears the confirmed runtime snapshot when a background reload confirms access denial', async () => {
    const accessDeniedError = Object.assign(new Error('Workspace access denied'), {
      errorCode: 'WORKSPACE_ACCESS_DENIED',
    });
    mocks.resolveRuntimeBaseUrlWithDetailMock
      .mockResolvedValueOnce({
        url: 'https://runtime-a.example',
        detail: {
          id: 'ws-a',
          agenticTools: ['codex'],
          accessRole: 'owner',
            accessSource: 'owned',
            accessSources: ['owned'],
          allowedOperations: ['workspace.detail.read'],
          runtimeStatus: null,
        },
      })
      .mockRejectedValueOnce(accessDeniedError);

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.accessRole).toBe('owner');
    });

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.runtimeBaseUrl).toBeNull();
    expect(result.current.agenticTools).toEqual([]);
    expect(result.current.accessRole).toBeNull();
    expect(result.current.errorCode).toBe('WORKSPACE_ACCESS_DENIED');
    expect(result.current.isAuthorizationResolved).toBe(true);
    expect(mocks.resolveRuntimeBaseUrlWithDetailMock).toHaveBeenCalledTimes(2);
  });

  it('fails closed when workspace detail contains a malformed access role', async () => {
    mocks.resolveRuntimeBaseUrlWithDetailMock.mockResolvedValue({
      url: 'https://runtime-a.example',
      detail: {
        id: 'ws-a',
        agenticTools: ['codex'],
        accessRole: 'administrator',
        runtimeStatus: null,
      },
    });

    const { result } = renderHook(() => useWorkspaceRuntime('ws-a'));

    await waitFor(() => {
      expect(result.current.isAuthorizationResolved).toBe(true);
    });

    expect(result.current.accessRole).toBeNull();
    expect(result.current.allowedOperations).toEqual([]);
    expect(result.current.runtimeBaseUrl).toBeNull();
    expect(result.current.errorCode).toBe('WORKSPACE_ACCESS_DENIED');
    expect(mocks.resolveRuntimeBaseUrlWithDetailMock).toHaveBeenCalledTimes(1);
  });

});
