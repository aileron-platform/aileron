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

vi.mock('@/features/workspace/components/ChatPanel/slashCommandApi', () => ({
  slashCommandApi: {
    list: slashCommandListMock,
  },
}));

vi.mock('@/features/workspace/features/agent-settings/utils', () => ({
  normalizeAgentType: () => 'codex',
  getAgentToolConfig: () => ({ apiPathPrefix: '/api/v1' }),
}));

import { workspaceApi } from './workspaceApi';

describe('workspaceApi.listSlashCommands', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    slashCommandListMock.mockReset();
  });

  it('有 externalUrl 時會用 public runtime host 呼叫 slash command API', async () => {
    apiGetMock.mockResolvedValue({
      id: 'ws-1',
      name: 'Workspace 1',
      runtimeStatus: {
        externalUrl: 'https://workspace-runtime-ws-1.example.com',
        internalUrl: 'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002',
      },
    });
    slashCommandListMock.mockResolvedValue([]);

    await workspaceApi.listSlashCommands('ws-1');

    expect(slashCommandListMock).toHaveBeenCalledWith(
      'https://workspace-runtime-ws-1.example.com',
      'ws-1',
      '/api/v1',
      undefined
    );
  });

  it('沒有 externalUrl 時才會回退到 internalUrl', async () => {
    apiGetMock.mockResolvedValue({
      id: 'ws-1',
      name: 'Workspace 1',
      runtimeStatus: {
        externalUrl: null,
        internalUrl: 'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002',
      },
    });
    slashCommandListMock.mockResolvedValue([]);

    await workspaceApi.listSlashCommands('ws-1');

    expect(slashCommandListMock).toHaveBeenCalledWith(
      'http://workspace-runtime-ws-1.team-a.svc.cluster.local:3002',
      'ws-1',
      '/api/v1',
      undefined
    );
  });
});
