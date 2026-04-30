import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AgentFileTreeDataAdapter } from './agentFileTreeDataAdapter';

const { apiClientMock, ApiClientMock } = vi.hoisted(() => {
  const apiClientMock = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  };

  return {
    apiClientMock,
    ApiClientMock: vi.fn(() => apiClientMock),
  };
});

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: ApiClientMock,
  apiClient: apiClientMock,
}));

describe('AgentFileTreeDataAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each(['claude-code', 'gemini', 'codex', 'opencode'] as const)(
    'uses the active %s API prefix for file trees',
    async (apiPrefix) => {
      apiClientMock.get.mockResolvedValueOnce({ nodes: [] });

      const adapter = new AgentFileTreeDataAdapter({
        workspaceId: 'ws-1',
        apiPrefix,
        collection: 'skills',
        scope: 'project',
        runtimeBaseUrl: 'http://runtime.local',
      });
      await adapter.getTree();

      expect(ApiClientMock).toHaveBeenCalledWith({ baseUrl: 'http://runtime.local/api/v1' });
      expect(apiClientMock.get).toHaveBeenCalledWith(
        `/workspaces/ws-1/${apiPrefix}/skills/tree?scope=project&includeHidden=true`,
      );
    },
  );

  it('uses the configured collection and scope when moving files', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'scripts',
      scope: 'user',
    });
    await adapter.move('old.md', 'new.md');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/claude-code/scripts/move?scope=user&sourcePath=old.md&destPath=new.md&sourceScope=user&destScope=user&overwrite=false',
    );
  });
});
