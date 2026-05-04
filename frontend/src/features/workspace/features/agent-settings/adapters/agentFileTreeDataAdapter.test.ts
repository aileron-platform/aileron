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

  it.each(['claude-code', 'gemini', 'opencode'] as const)(
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

  it('maps Codex file summaries into a file tree', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      files: [
        { name: 'SKILL.md', path: 'builder/SKILL.md', sizeBytes: 12, source: 'project', readOnly: false, metadata: {} },
        { name: 'SKILL.md', path: 'plugin/SKILL.md', sizeBytes: 10, source: 'plugin', readOnly: true, metadata: { pluginId: 'github@openai' } },
      ],
    });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'project',
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledWith('/workspaces/ws-1/codex/skills/files?layer=project');
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ name: 'builder', type: 'directory' });
    expect(tree[0].children?.[0]).toMatchObject({ name: 'SKILL.md', path: 'builder/SKILL.md', scope: 'project' });
  });

  it('reads Codex plugin skill content with the plugin identity', async () => {
    apiClientMock.get
      .mockResolvedValueOnce({
        files: [
          {
            name: 'review',
            path: 'review/SKILL.md',
            sizeBytes: 10,
            source: 'plugin',
            readOnly: true,
            metadata: { pluginId: 'demo@local', pluginName: 'Demo', marketplaceName: 'local' },
          },
        ],
      })
      .mockResolvedValueOnce({ content: '# Review\n' });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'plugin',
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();
    const content = await adapter.getContent('review/SKILL.md');

    expect(apiClientMock.get).toHaveBeenNthCalledWith(1, '/workspaces/ws-1/codex/skills/files?layer=plugin');
    expect(tree[0].children?.[0]).toMatchObject({
      pluginId: 'demo@local',
      pluginName: 'Demo',
      marketplaceName: 'local',
      writable: false,
    });
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/workspaces/ws-1/codex/skills/file?layer=plugin&path=review%2FSKILL.md&pluginId=demo%40local',
    );
    expect(content).toBe('# Review\n');
  });

  it('groups all scope file trees and preserves source metadata', async () => {
    apiClientMock.get
      .mockResolvedValueOnce({
        nodes: [
          {
            id: 'dependency/SKILL.md',
            name: 'SKILL.md',
            path: 'dependency/SKILL.md',
            type: 'file',
          },
        ],
      })
      .mockResolvedValueOnce({
        nodes: [
          {
            id: 'dependency/SKILL.md',
            name: 'SKILL.md',
            path: 'dependency/SKILL.md',
            type: 'file',
          },
        ],
      });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'gemini',
      collection: 'skills',
      scope: 'all',
      scopes: ['project', 'extension'],
      scopeLabels: { project: 'Project', extension: 'Extension' },
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/workspaces/ws-1/gemini/skills/tree?scope=project&includeHidden=true',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/workspaces/ws-1/gemini/skills/tree?scope=extension&includeHidden=true',
    );
    expect(tree).toHaveLength(2);
    expect(tree[0]).toMatchObject({ name: 'Project', path: 'scope:project', writable: false });
    expect(tree[0].children?.[0]).toMatchObject({
      id: 'project:dependency/SKILL.md',
      path: 'project/dependency/SKILL.md',
      scope: 'project',
      metadata: {
        sourcePath: 'dependency/SKILL.md',
        sourceScope: 'project',
      },
    });
    expect(tree[1]).toMatchObject({ name: 'Extension', path: 'scope:extension', writable: false });
  });

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
