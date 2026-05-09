import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@/__tests__/utils/render';
import { OpenSpecWorkspaceProvider, useOpenSpecWorkspace } from './OpenSpecWorkspaceContext';

const mocks = vi.hoisted(() => {
  const workspaceRuntime = {
    workspaceId: 'ws-1',
    runtimeBaseUrl: 'http://runtime.local',
  };
  const workspaceState = {
    currentFeature: 'file-management',
    openspec: {
      subView: 'in-progress',
      selectedPath: null as string | null,
      openTabs: [] as Array<{ id: string; path: string }>,
      activeTabId: null as string | null,
      modifiedTabs: [] as string[],
    },
  };

  return {
    workspaceRuntime,
    workspaceState,
    reloadCurrentFileMock: vi.fn().mockResolvedValue(undefined),
    getWorkspaceSummaryMock: vi.fn(),
    getWorkspaceStateMock: vi.fn(),
    getCustomizationStateMock: vi.fn(),
    validateCustomizationMock: vi.fn(),
    debugCustomizationMock: vi.fn(),
    subscribeMock: vi.fn(),
  };
});

vi.mock('@/features/auth/hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    getAccessToken: () => 'token',
  }),
}));

vi.mock('../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: mocks.workspaceRuntime,
    state: mocks.workspaceState,
    fileEditor: {
      reloadCurrentFile: mocks.reloadCurrentFileMock,
    },
  }),
}));

vi.mock('../../components/ChatPanel/openSpecApi', () => ({
  openSpecApi: {
    getWorkspaceSummary: (...args: unknown[]) => mocks.getWorkspaceSummaryMock(...args),
    getWorkspaceState: (...args: unknown[]) => mocks.getWorkspaceStateMock(...args),
    getCustomizationState: (...args: unknown[]) => mocks.getCustomizationStateMock(...args),
    validateCustomization: (...args: unknown[]) => mocks.validateCustomizationMock(...args),
    debugCustomization: (...args: unknown[]) => mocks.debugCustomizationMock(...args),
  },
}));

vi.mock('../../components/ChatPanel/agentSessionEvents', () => ({
  getEventDispatcher: () => ({
    subscribe: mocks.subscribeMock,
  }),
}));

describe('OpenSpecWorkspaceContext', () => {
  const wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <OpenSpecWorkspaceProvider>{children}</OpenSpecWorkspaceProvider>
  );

  beforeEach(() => {
    mocks.workspaceRuntime.workspaceId = 'ws-1';
    mocks.workspaceRuntime.runtimeBaseUrl = 'http://runtime.local';
    mocks.workspaceState.currentFeature = 'file-management';
    mocks.workspaceState.openspec.subView = 'in-progress';
    mocks.workspaceState.openspec.selectedPath = null;
    mocks.workspaceState.openspec.openTabs = [];
    mocks.workspaceState.openspec.activeTabId = null;
    mocks.workspaceState.openspec.modifiedTabs = [];

    mocks.reloadCurrentFileMock.mockReset();
    mocks.reloadCurrentFileMock.mockResolvedValue(undefined);
    mocks.getWorkspaceSummaryMock.mockReset();
    mocks.getWorkspaceStateMock.mockReset();
    mocks.getCustomizationStateMock.mockReset();
    mocks.validateCustomizationMock.mockReset();
    mocks.debugCustomizationMock.mockReset();
    mocks.subscribeMock.mockReset();
    mocks.subscribeMock.mockReturnValue(() => {});

    mocks.getWorkspaceSummaryMock.mockResolvedValue({
      workspaceId: 'ws-1',
      initialized: true,
      counts: {
        inProgress: 2,
        complete: 1,
        archived: 0,
      },
    });
    mocks.getWorkspaceStateMock.mockResolvedValue({
      workspaceId: 'ws-1',
      state: {
        cliInstalled: true,
        initialized: true,
        profile: 'core',
        activeChanges: [],
      },
      actions: [],
      changes: [],
    });
  });

  it('loads summary on landing without eagerly loading full workspace state', async () => {
    const { result } = renderHook(() => useOpenSpecWorkspace(), { wrapper });

    await waitFor(() => {
      expect(result.current.summary?.counts.inProgress).toBe(2);
    });

    expect(mocks.getWorkspaceSummaryMock).toHaveBeenCalledWith('http://runtime.local', 'ws-1');
    expect(mocks.getWorkspaceStateMock).not.toHaveBeenCalled();
  });

  it('loads full workspace state when entering an OpenSpec feature', async () => {
    const { rerender } = renderHook(() => useOpenSpecWorkspace(), { wrapper });

    await waitFor(() => {
      expect(mocks.getWorkspaceSummaryMock).toHaveBeenCalledTimes(1);
    });

    mocks.workspaceState.currentFeature = 'openspec';
    rerender();

    await waitFor(() => {
      expect(mocks.getWorkspaceStateMock).toHaveBeenCalledTimes(1);
    });
  });

  it('loads full workspace state when an OpenSpec document becomes active', async () => {
    const { rerender } = renderHook(() => useOpenSpecWorkspace(), { wrapper });

    await waitFor(() => {
      expect(mocks.getWorkspaceSummaryMock).toHaveBeenCalledTimes(1);
    });

    mocks.workspaceState.openspec.selectedPath = '/openspec/changes/demo/proposal.md';
    rerender();

    await waitFor(() => {
      expect(mocks.getWorkspaceStateMock).toHaveBeenCalledTimes(1);
    });
  });

  it('keeps the loaded OpenSpec navigation state when switching documents', async () => {
    mocks.workspaceState.currentFeature = 'openspec';
    mocks.workspaceState.openspec.selectedPath = '/openspec/changes/demo/proposal.md';

    const { rerender } = renderHook(() => useOpenSpecWorkspace(), { wrapper });

    await waitFor(() => {
      expect(mocks.getWorkspaceStateMock).toHaveBeenCalledTimes(1);
    });

    mocks.workspaceState.openspec.selectedPath = '/openspec/changes/demo/design.md';
    rerender();

    await act(async () => {
      await Promise.resolve();
    });

    expect(mocks.getWorkspaceStateMock).toHaveBeenCalledTimes(1);
  });
});
