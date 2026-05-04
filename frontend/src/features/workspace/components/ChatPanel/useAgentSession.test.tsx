import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentSession } from './useAgentSession';
import { getAgentSessionStore, resetAgentSessionStore } from './agentSessionStore';

const mocks = vi.hoisted(() => ({
  listSessionsMock: vi.fn(),
  createSessionMock: vi.fn(),
  updateSessionMock: vi.fn(),
  setRealtimeSessionsMock: vi.fn(),
  upsertRealtimeSessionMock: vi.fn(),
  refreshMock: vi.fn(async () => undefined),
  mergeMessagesMock: vi.fn(),
  setLoadedOffsetMock: vi.fn(),
  setRealtimeHasMoreMock: vi.fn(),
  emptyMessages: [] as unknown[],
  emptyTasks: [] as unknown[],
  emptySessionsMap: new Map(),
}));

vi.mock('@/features/auth/hooks/useAuth', () => ({
  useAuth: () => ({
    getAccessToken: () => 'token',
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('./agentSessionEvents', () => ({
  getEventDispatcher: () => ({
    subscribe: vi.fn(() => vi.fn()),
    dispatch: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
}));

vi.mock('./agentSessionApi', () => ({
  agentApi: {
    sessions: {
      listSessions: mocks.listSessionsMock,
      createSession: mocks.createSessionMock,
      updateSession: mocks.updateSessionMock,
    },
    tasks: {
      stopTask: vi.fn(),
    },
    messages: {
      listMessages: vi.fn(),
    },
  },
}));

vi.mock('../../realtime', () => ({
  useWebSocketClient: () => ({
    socket: null,
    connected: false,
    connecting: false,
    error: null,
    reconnect: vi.fn(),
  }),
  useRealtimeData: () => ({
    messages: mocks.emptyMessages,
    tasks: mocks.emptyTasks,
    loading: false,
    refresh: mocks.refreshMock,
    mergeMessages: mocks.mergeMessagesMock,
    messagesTotal: 0,
    hasMoreMessages: false,
    loadedOffset: 0,
    setLoadedOffset: mocks.setLoadedOffsetMock,
    setHasMoreMessages: mocks.setRealtimeHasMoreMock,
  }),
  useRealtimeSessions: () => ({
    sessionsMap: mocks.emptySessionsMap,
    setSessions: mocks.setRealtimeSessionsMock,
    upsertSession: mocks.upsertRealtimeSessionMock,
  }),
  useStreamingMessages: () => [],
}));

describe('useAgentSession', () => {
  beforeEach(() => {
    resetAgentSessionStore();
    localStorage.clear();
    sessionStorage.clear();
    mocks.listSessionsMock.mockReset();
    mocks.createSessionMock.mockReset();
    mocks.updateSessionMock.mockReset();
    mocks.setRealtimeSessionsMock.mockReset();
    mocks.upsertRealtimeSessionMock.mockReset();
    mocks.refreshMock.mockClear();
    mocks.mergeMessagesMock.mockClear();
    mocks.setLoadedOffsetMock.mockClear();
    mocks.setRealtimeHasMoreMock.mockClear();

    mocks.listSessionsMock.mockImplementation(async (_runtimeBaseUrl: string, params: { workspace_id?: string }) => {
      if (params.workspace_id === 'ws-a') {
        return {
          items: [
            {
              session_id: 'session-a',
              title: 'Session A',
              created_at: '2026-04-24T00:00:00Z',
              updated_at: '2026-04-24T00:00:00Z',
              agentic_tool: 'claude-code',
            },
            {
              session_id: 'session-a-codex',
              title: 'Session A Codex',
              created_at: '2026-04-25T00:00:00Z',
              updated_at: '2026-04-25T00:00:00Z',
              agentic_tool: 'codex',
            },
          ],
        };
      }

      return {
        items: [
          {
            session_id: 'session-b',
            title: 'Session B',
            created_at: '2026-04-24T00:00:00Z',
            updated_at: '2026-04-24T00:00:00Z',
            agentic_tool: 'claude-code',
          },
        ],
      };
    });
  });

  it('resets transient state and selects the new workspace session when workspaceId changes', async () => {
    const { result, rerender } = renderHook(
      ({ workspaceId }) =>
        useAgentSession({
          runtimeBaseUrl: 'http://runtime.test',
          workspaceId,
          autoConnect: true,
        }),
      {
        initialProps: { workspaceId: 'ws-a' },
      }
    );

    await waitFor(() => {
      expect(result.current.state.currentSessionId).toBe('session-a');
    });

    act(() => {
      const store = getAgentSessionStore();
      store.setQueuedMessages([
        {
          message_id: 'queued-a',
          queue_position: 1,
          content_preview: 'queued',
          created_at: '2026-04-24T00:00:00Z',
        } as any,
      ]);
      store.setPendingPermission({
        request_id: 'perm-a',
        task_id: 'task-a',
        tool_name: 'write_file',
        tool_input: {},
      } as any);
    });

    expect(result.current.state.queuedMessages).toHaveLength(1);
    expect(result.current.state.pendingPermission?.request_id).toBe('perm-a');

    rerender({ workspaceId: 'ws-b' });

    await waitFor(() => {
      expect(result.current.state.currentSessionId).toBe('session-b');
    });

    expect(result.current.state.queuedMessages).toEqual([]);
    expect(result.current.state.pendingPermission).toBeNull();
    expect(mocks.listSessionsMock).toHaveBeenCalledWith(
      'http://runtime.test',
      expect.objectContaining({ workspace_id: 'ws-a' })
    );
    expect(mocks.listSessionsMock).toHaveBeenCalledWith(
      'http://runtime.test',
      expect.objectContaining({ workspace_id: 'ws-b' })
    );
  });

  it('filters sessions by cliType and auto-creates a Codex session when only Claude sessions exist', async () => {
    mocks.listSessionsMock.mockImplementation(async (_runtimeBaseUrl: string, params: { workspace_id?: string; agentic_tool?: string }) => {
      if (params.workspace_id === 'ws-codex') {
        return {
          items: [
            {
              session_id: 'session-claude-1',
              title: 'Claude Session',
              created_at: '2026-04-24T00:00:00Z',
              updated_at: '2026-04-24T00:00:00Z',
              agentic_tool: 'claude-code',
            },
          ],
        };
      }

      return { items: [] };
    });

    mocks.createSessionMock.mockResolvedValue({
      session_id: 'session-codex-1',
      title: 'Codex Session',
      created_at: '2026-04-25T00:00:00Z',
      updated_at: '2026-04-25T00:00:00Z',
      agentic_tool: 'codex',
    });

    const { result } = renderHook(() =>
      useAgentSession({
        runtimeBaseUrl: 'http://runtime.test',
        workspaceId: 'ws-codex',
        cliType: 'codex',
        autoConnect: true,
      })
    );

    await waitFor(() => {
      expect(result.current.state.currentSessionId).toBe('session-codex-1');
    });

    expect(mocks.listSessionsMock).toHaveBeenCalledWith(
      'http://runtime.test',
      expect.objectContaining({
        workspace_id: 'ws-codex',
        agentic_tool: 'codex',
      })
    );
    expect(mocks.createSessionMock).toHaveBeenCalledWith(
      'http://runtime.test',
      expect.objectContaining({
        workspace_id: 'ws-codex',
        agentic_tool: 'codex',
      })
    );
  });

  it('defaults Gemini session creation to yolo permission mode', async () => {
    mocks.listSessionsMock.mockResolvedValue({ items: [] });
    mocks.createSessionMock.mockResolvedValue({
      session_id: 'session-gemini-1',
      title: 'Gemini Session',
      created_at: '2026-04-25T00:00:00Z',
      updated_at: '2026-04-25T00:00:00Z',
      agentic_tool: 'gemini',
      permission_config: {
        mode: 'default',
        gemini: 'yolo',
      },
    });

    const { result } = renderHook(() =>
      useAgentSession({
        runtimeBaseUrl: 'http://runtime.test',
        workspaceId: 'ws-gemini',
        cliType: 'gemini',
        autoConnect: true,
      })
    );

    await waitFor(() => {
      expect(result.current.state.currentSessionId).toBe('session-gemini-1');
    });

    expect(mocks.createSessionMock).toHaveBeenCalledWith(
      'http://runtime.test',
      expect.objectContaining({
        workspace_id: 'ws-gemini',
        agentic_tool: 'gemini',
        permission_config: expect.objectContaining({
          mode: 'default',
          gemini: 'yolo',
        }),
      }),
    );
  });

  it('patches Gemini permission mode on update', async () => {
    mocks.listSessionsMock.mockResolvedValue({
      items: [
        {
          session_id: 'session-gemini-current',
          title: 'Gemini Session',
          created_at: '2026-04-24T00:00:00Z',
          updated_at: '2026-04-24T00:00:00Z',
          agentic_tool: 'gemini',
          permission_config: {
            mode: 'default',
            gemini: 'default',
          },
        },
      ],
    });
    mocks.updateSessionMock.mockResolvedValue({
      session_id: 'session-gemini-current',
      title: 'Gemini Session',
      created_at: '2026-04-24T00:00:00Z',
      updated_at: '2026-04-24T00:00:00Z',
      agentic_tool: 'gemini',
      permission_config: {
        mode: 'default',
        gemini: 'plan',
        gemini_spawned_with: 'default',
      },
    });

    const { result } = renderHook(() =>
      useAgentSession({
        runtimeBaseUrl: 'http://runtime.test',
        workspaceId: 'ws-gemini-patch',
        cliType: 'gemini',
        autoConnect: true,
      })
    );

    await waitFor(() => {
      expect(result.current.state.currentSessionId).toBe('session-gemini-current');
    });

    await act(async () => {
      await result.current.setGeminiPermissionMode('plan');
    });

    expect(mocks.updateSessionMock).toHaveBeenCalledWith(
      'http://runtime.test',
      'session-gemini-current',
      {
        permission_config: {
          mode: 'default',
          gemini: 'plan',
        },
      },
    );
  });
});
