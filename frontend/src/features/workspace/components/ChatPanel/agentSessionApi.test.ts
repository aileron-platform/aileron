import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getMock, postMock, patchMock, deleteMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class {
    get = getMock;
    post = postMock;
    patch = patchMock;
    delete = deleteMock;
  },
}));

import { agentSessionApi } from './agentSessionApi';

describe('agentSessionApi sessions', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
  });

  it('建立 session 時只使用 session_id', async () => {
    postMock.mockResolvedValue({
      session_id: 'sess-k8s-1',
      created_at: '2026-04-13T00:00:00Z',
      created_by: 'user',
      status: 'idle',
      agentic_tool: 'codex',
      workspace_id: 'ws-1',
      ready_for_prompt: true,
      archived: false,
    });

    const session = await agentSessionApi.createSession('http://runtime.test', {
      workspace_id: 'ws-1',
      agentic_tool: 'codex',
    });

    expect(session.session_id).toBe('sess-k8s-1');
  });

  it('查詢 session 列表時只使用 session_id', async () => {
    getMock.mockResolvedValue({
      items: [
        {
          session_id: 'sess-k8s-2',
          created_at: '2026-04-13T00:00:00Z',
          created_by: 'user',
          status: 'idle',
          agentic_tool: 'codex',
          workspace_id: 'ws-1',
          ready_for_prompt: true,
          archived: false,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    const response = await agentSessionApi.listSessions('http://runtime.test', {
      workspace_id: 'ws-1',
    });

    expect(response.items[0]?.session_id).toBe('sess-k8s-2');
  });
});
