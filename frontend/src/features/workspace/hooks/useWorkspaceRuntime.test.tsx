import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@/__tests__/utils/render';
import { useWorkspaceRuntime } from './useWorkspaceRuntime';

const mocks = vi.hoisted(() => ({
  fetchDefaultWorkspaceIdMock: vi.fn(),
  resolveRuntimeBaseUrlMock: vi.fn(),
  fetchWorkspaceDetailMock: vi.fn(),
}));

vi.mock('../services/workspaceRuntimeApi', () => ({
  fetchDefaultWorkspaceId: (...args: unknown[]) => mocks.fetchDefaultWorkspaceIdMock(...args),
  resolveRuntimeBaseUrl: (...args: unknown[]) => mocks.resolveRuntimeBaseUrlMock(...args),
  fetchWorkspaceDetail: (...args: unknown[]) => mocks.fetchWorkspaceDetailMock(...args),
}));

describe('useWorkspaceRuntime', () => {
  beforeEach(() => {
    mocks.fetchDefaultWorkspaceIdMock.mockReset();
    mocks.resolveRuntimeBaseUrlMock.mockReset();
    mocks.fetchWorkspaceDetailMock.mockReset();
  });

  it('clears the previous runtime URL while switching to another workspace', async () => {
    let resolveWorkspaceBUrl: ((value: string) => void) | null = null;

    mocks.resolveRuntimeBaseUrlMock.mockImplementation((workspaceId: string) => {
      if (workspaceId === 'ws-a') {
        return Promise.resolve('https://runtime-a.example');
      }

      if (workspaceId === 'ws-b') {
        return new Promise<string>((resolve) => {
          resolveWorkspaceBUrl = resolve;
        });
      }

      throw new Error(`Unexpected workspace: ${workspaceId}`);
    });
    mocks.fetchWorkspaceDetailMock.mockImplementation((workspaceId: string) =>
      Promise.resolve({
        id: workspaceId,
        cliType: 'claude-code',
        runtimeStatus: {
          terminalExternalUrl: `https://terminal-${workspaceId}.example`,
        },
      }),
    );

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

    resolveWorkspaceBUrl?.('https://runtime-b.example');

    await waitFor(() => {
      expect(result.current.runtimeBaseUrl).toBe('https://runtime-b.example');
    });
  });

  it('clears runtime identity without fetching a default workspace when the selection becomes null', async () => {
    mocks.resolveRuntimeBaseUrlMock.mockResolvedValue('https://runtime-a.example');
    mocks.fetchWorkspaceDetailMock.mockResolvedValue({
      id: 'ws-a',
      cliType: 'claude-code',
      runtimeStatus: {
        terminalExternalUrl: 'https://terminal-ws-a.example',
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
      expect(result.current.terminalExternalUrl).toBeNull();
    });

    expect(mocks.fetchDefaultWorkspaceIdMock).not.toHaveBeenCalled();
  });
});
