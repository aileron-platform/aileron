import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiGetMock, slashCommandListMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  slashCommandListMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('@/shared/api/slashCommandApi', () => ({
  slashCommandApi: {
    list: slashCommandListMock,
  },
}));

import { automationWorkspaceApi } from './automationWorkspaceApi';

describe('automationWorkspaceApi', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    slashCommandListMock.mockReset();
  });

  it('uses the Manager-projected same-origin Runtime URL for slash commands', async () => {
    apiGetMock.mockResolvedValue({
      id: 'ws-1',
      name: 'Workspace 1',
      runtimeStatus: {
        runtimeUrl: '/workspaces/ws-1/runtime',
      },
    });
    slashCommandListMock.mockResolvedValue([]);

    await automationWorkspaceApi.listSlashCommands('ws-1');

    expect(slashCommandListMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/runtime',
      'ws-1',
      'claude-code',
      undefined
    );
  });

  it('uses the first enabled agentic tool for automation slash commands', async () => {
    apiGetMock.mockResolvedValue({
      id: 'ws-1',
      name: 'Workspace 1',
      agenticTools: ['codex', 'opencode'],
      runtimeStatus: {
        runtimeUrl: '/workspaces/ws-1/runtime',
      },
    });
    slashCommandListMock.mockResolvedValue([]);

    await automationWorkspaceApi.listSlashCommands('ws-1');

    expect(slashCommandListMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/runtime',
      'ws-1',
      'codex',
      undefined
    );
  });

  it('lists workspaces through the canonical collection route', async () => {
    apiGetMock.mockResolvedValue({
      items: [
        { id: 'ws-b', name: 'Workspace B' },
        { id: 'ws-a', name: 'Workspace A' },
      ],
    });

    const result = await automationWorkspaceApi.list();

    expect(apiGetMock).toHaveBeenCalledWith('/workspaces?page=1&pageSize=50');
    expect(result.map(item => item.id)).toEqual(['ws-a', 'ws-b']);
  });
});
