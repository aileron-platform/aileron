import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const subscribeMock = vi.fn();

vi.mock('../../components/ChatPanel/agentSessionEvents', () => ({
  getEventDispatcher: () => ({
    subscribe: subscribeMock,
  }),
}));

import { useRealtimeSessions } from './useRealtimeSessions';

describe('useRealtimeSessions', () => {
  it('upsertSession 會保留既有資料並合併新 session 欄位', () => {
    subscribeMock.mockReturnValue(() => {});

    const { result } = renderHook(() => useRealtimeSessions('ws-1'));

    act(() => {
      result.current.setSessions([
        {
          session_id: 'session-1',
          workspace_id: 'ws-1',
          source: 'user',
          title: '舊標題',
          created_at: '2026-04-13T00:00:00Z',
          created_by: 'user',
          status: 'idle',
          agentic_tool: 'claude-code',
          ready_for_prompt: true,
          archived: false,
        },
      ] as any);
    });

    act(() => {
      result.current.upsertSession({
        session_id: 'session-1',
        workspace_id: 'ws-1',
        source: 'user',
        title: '新標題',
        created_at: '2026-04-13T00:00:00Z',
        created_by: 'user',
        status: 'running',
        agentic_tool: 'claude-code',
        ready_for_prompt: true,
        archived: false,
      } as any);
    });

    const session = result.current.sessionsMap.get('session-1');
    expect(session?.title).toBe('新標題');
    expect(session?.status).toBe('running');
    expect(result.current.sessionsMap.size).toBe(1);
  });
});
