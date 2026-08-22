import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGetMock, promptInvocationListMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  promptInvocationListMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('@/shared/api/promptInvocationApi', () => ({
  promptInvocationApi: {
    list: promptInvocationListMock,
  },
}));

import { automationWorkspaceApi } from './automationWorkspaceApi';

describe('automationWorkspaceApi', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    promptInvocationListMock.mockReset();
  });

  it('uses the selected Agentic Tool and already-projected Runtime URL', async () => {
    promptInvocationListMock.mockResolvedValue({ items: [] });

    await automationWorkspaceApi.listPromptInvocations('http://runtime.test', 'ws-1', 'codex');

    expect(promptInvocationListMock).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'codex',
    );
    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it('lists workspaces through the canonical collection route', async () => {
    apiGetMock.mockResolvedValue({
      items: [
        { id: 'ws-b', name: 'Workspace B', runtimeUrl: 'http://runtime-b.test' },
        { id: 'ws-a', name: 'Workspace A', runtimeUrl: 'http://runtime-a.test' },
      ],
    });

    const result = await automationWorkspaceApi.list();

    expect(apiGetMock).toHaveBeenCalledWith('/workspaces?page=1&pageSize=50');
    expect(result.map(item => item.id)).toEqual(['ws-a', 'ws-b']);
    expect(result[0]?.runtimeUrl).toBe('http://runtime-a.test');
  });
});
