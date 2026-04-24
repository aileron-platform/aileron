import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@/__tests__/utils/render';
import { useWorkspaceRuntime } from './useWorkspaceRuntime';

const mocks = vi.hoisted(() => ({
  fetchDefaultWorkspaceIdMock: vi.fn(),
  resolveRuntimeBaseUrlWithDetailMock: vi.fn(),
}));

vi.mock('../services/workspaceRuntimeApi', () => ({
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
            cliType: 'claude-code',
            runtimeStatus: {
              terminalExternalUrl: `https://terminal-${workspaceId}.example`,
            },
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
        cliType: 'claude-code',
        runtimeStatus: {
          terminalExternalUrl: 'https://terminal-ws-b.example',
        },
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
        cliType: 'claude-code',
        runtimeStatus: {
          terminalExternalUrl: 'https://terminal-ws-a.example',
        },
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
