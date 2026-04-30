import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClaudeCodeFileTreeDataAdapter } from './claudeCodeFileTreeDataAdapter';

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

describe('ClaudeCodeFileTreeDataAdapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the workspace runtime client when runtimeBaseUrl is provided', async () => {
    apiClientMock.get.mockResolvedValueOnce({ nodes: [] });

    const adapter = new ClaudeCodeFileTreeDataAdapter({
      workspaceId: 'ws-1',
      collection: 'skills',
      scope: 'project',
      runtimeBaseUrl: 'http://runtime.local',
    });
    await adapter.getTree();

    expect(ApiClientMock).toHaveBeenCalledWith({ baseUrl: 'http://runtime.local/api/v1' });
    expect(apiClientMock.get).toHaveBeenCalledWith('/workspaces/ws-1/claude-code/skills/tree?scope=project&includeHidden=true');
  });

  it('uses the current move endpoint with source and destination scope', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new ClaudeCodeFileTreeDataAdapter({
      workspaceId: 'ws-1',
      collection: 'scripts',
      scope: 'user',
    });
    await adapter.move('old.md', 'new.md');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/claude-code/scripts/move?scope=user&sourcePath=old.md&destPath=new.md&sourceScope=user&destScope=user&overwrite=false',
    );
  });
});
