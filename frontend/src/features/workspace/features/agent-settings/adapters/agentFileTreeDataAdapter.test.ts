import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
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

  it.each(['claude-code', 'opencode'] as const)(
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

      expect(ApiClientMock).toHaveBeenCalledWith({
        baseUrl: 'http://runtime.local/api/v1',
        unauthorizedBehavior: 'propagate',
        executionAudience: 'workspace-runtime',
      });
      expect(apiClientMock.get).toHaveBeenCalledWith(
        `/workspaces/ws-1/${apiPrefix}/skills/tree?scope=project&includeHidden=true`,
      );
    },
  );

  it('normalizes scoped skill tree responses through the shared parser', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      path: '/',
      nodes: [
        {
          id: 'skills/demo',
          name: 'demo',
          path: 'skills/demo',
          type: 'directory',
          children: [
            {
              id: 'skills/demo/SKILL.md',
              name: 'SKILL.md',
              path: 'skills/demo/SKILL.md',
              type: 'file',
            },
          ],
        },
      ],
      total: 1,
    });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'project',
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();

    expect(tree[0].children?.[0]).toMatchObject({
      name: 'SKILL.md',
      path: 'skills/demo/SKILL.md',
      type: 'file',
    });
  });

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

    expect(apiClientMock.get).toHaveBeenCalledWith('/workspaces/ws-1/codex/skills/files?scope=project');
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

    expect(apiClientMock.get).toHaveBeenNthCalledWith(1, '/workspaces/ws-1/codex/skills/files?scope=plugin');
    expect(tree[0].children?.[0]).toMatchObject({
      pluginId: 'demo@local',
      pluginName: 'Demo',
      marketplaceName: 'local',
      writable: false,
    });
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/workspaces/ws-1/codex/skills/file?scope=plugin&path=review%2FSKILL.md&pluginId=demo%40local',
    );
    expect(content).toBe('# Review\n');
  });

  it('prevents writes to Codex plugin file trees', async () => {
    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'plugin',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await expect(adapter.create({
      type: 'create',
      path: 'review/SKILL.md',
      content: '# Review',
      isDirectory: false,
    })).rejects.toThrow('Cannot write files in a read-only scope');
    await expect(adapter.update('review/SKILL.md', '# Updated')).rejects.toThrow('Cannot write files in a read-only scope');
    await expect(adapter.delete('review/SKILL.md')).rejects.toThrow('Cannot write files in a read-only scope');

    expect(apiClientMock.post).not.toHaveBeenCalled();
    expect(apiClientMock.put).not.toHaveBeenCalled();
    expect(apiClientMock.delete).not.toHaveBeenCalled();
  });

  it('creates Codex skill files through the generic Skills POST route', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'project',
    });

    const result = await adapter.create({
      type: 'create',
      path: '/review tools/SKILL #1.md',
      content: '# Review',
      isDirectory: false,
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills?scope=project&path=review%20tools%2FSKILL%20%231.md&type=file',
      { content: '# Review' },
    );
    expect(apiClientMock.put).not.toHaveBeenCalled();
    expect(result).toEqual({ success: true });
  });

  it('creates Codex skill directories without a content body', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'user',
    });

    await adapter.create({
      type: 'create',
      path: 'review tools/assets',
      isDirectory: true,
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills?scope=user&path=review%20tools%2Fassets&type=directory',
    );
    expect(apiClientMock.put).not.toHaveBeenCalled();
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
      apiPrefix: 'opencode',
      collection: 'skills',
      scope: 'all',
      scopes: ['project', 'user'],
      scopeLabels: { project: 'Project', user: 'User' },
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/workspaces/ws-1/opencode/skills/tree?scope=project&includeHidden=true',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      2,
      '/workspaces/ws-1/opencode/skills/tree?scope=user&includeHidden=true',
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
    expect(tree[1]).toMatchObject({ name: 'User', path: 'scope:user', writable: false });
  });

  it('loads all Claude scopes with one aggregate request', async () => {
    apiClientMock.get.mockResolvedValueOnce({
      nodes: [
        {
          id: 'review/SKILL.md',
          name: 'SKILL.md',
          path: 'review/SKILL.md',
          type: 'file',
          scope: 'project',
        },
        {
          id: 'deploy/SKILL.md',
          name: 'SKILL.md',
          path: 'deploy/SKILL.md',
          type: 'file',
          scope: 'user',
        },
      ],
    });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'all',
      scopes: ['project', 'user', 'plugin'],
      scopeLabels: { project: 'Project', user: 'User', plugin: 'Plugin' },
      runtimeBaseUrl: 'http://runtime.local',
    });

    const tree = await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledTimes(1);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/workspaces/ws-1/claude-code/skills/tree?scope=all&includeHidden=true',
    );
    expect(tree.map((node) => node.name)).toEqual(['Project', 'User']);
  });

  it('deduplicates warm collection loads through the shared query cache', async () => {
    apiClientMock.get.mockResolvedValue({ nodes: [] });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'project',
      runtimeBaseUrl: 'http://runtime.local',
      queryClient,
    });

    await Promise.all([adapter.getTree(), adapter.getTree()]);
    await adapter.getTree();

    expect(apiClientMock.get).toHaveBeenCalledTimes(1);
    expect(apiClientMock.get).toHaveBeenCalledWith(
      '/workspaces/ws-1/claude-code/skills/tree?scope=project&includeHidden=true',
      { signal: expect.any(AbortSignal) },
    );
  });

  it('uses the skills collection and scope when moving files', async () => {
    apiClientMock.post.mockResolvedValueOnce({ success: true });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'user',
    });
    await adapter.move('old.md', 'new.md');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/claude-code/skills/move?scope=user&sourcePath=old.md&destPath=new.md&sourceScope=user&destScope=user&overwrite=false',
    );
  });

  it('creates the full Codex Skills destination before deleting the move source', async () => {
    apiClientMock.get.mockResolvedValueOnce({ content: '# Skill' });
    apiClientMock.post.mockResolvedValueOnce({ success: true });
    apiClientMock.delete.mockResolvedValueOnce({ success: true });

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'project',
    });
    await adapter.move('builder/SKILL.md', 'renamed/SKILL.md');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills?scope=project&path=renamed%2FSKILL.md&type=file',
      { content: '# Skill' },
    );
    expect(apiClientMock.delete).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills/file?scope=project&path=builder%2FSKILL.md',
    );
    expect(apiClientMock.post.mock.invocationCallOrder[0]).toBeLessThan(
      apiClientMock.delete.mock.invocationCallOrder[0],
    );
  });

  it('does not delete a Codex move source when destination creation fails', async () => {
    apiClientMock.get.mockResolvedValueOnce({ content: '# Skill' });
    apiClientMock.post.mockRejectedValueOnce(new Error('create failed'));

    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'project',
    });

    await expect(
      adapter.move('builder/SKILL.md', 'renamed/SKILL.md'),
    ).rejects.toThrow('create failed');

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills?scope=project&path=renamed%2FSKILL.md&type=file',
      { content: '# Skill' },
    );
    expect(apiClientMock.delete).not.toHaveBeenCalled();
  });

  it('uploads binary skill files as multipart without reading them into text', async () => {
    apiClientMock.post.mockResolvedValueOnce({
      items: [{
        sourcePath: 'archive.zip',
        finalPath: 'demo/archive.zip',
        status: 'created',
        size: 3,
        type: 'file',
        error: null,
      }],
      total: 1,
      succeeded: 1,
      skipped: 0,
      failed: 0,
    });
    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'user',
      runtimeBaseUrl: 'http://runtime.local',
    });
    const file = new File([new Uint8Array([0, 255, 1])], 'archive.zip');
    const readText = vi.fn();
    Object.defineProperty(file, 'text', { value: readText });

    await adapter.upload({
      targetPath: 'demo',
      files: [file],
    });

    expect(apiClientMock.post).toHaveBeenCalledTimes(1);
    const [path, formData] = apiClientMock.post.mock.calls[0] as [string, FormData];
    expect(path).toBe('/workspaces/ws-1/claude-code/skills/upload');
    expect(formData.get('targetPath')).toBe('demo');
    expect(formData.get('scope')).toBe('user');
    expect(formData.get('defaultStrategy')).toBe('cancel');
    expect(formData.get('resolutions')).toBe('[]');
    expect(formData.get('archiveAction')).toBeNull();
    expect(formData.get('keepArchive')).toBeNull();
    expect(formData.get('conflictStrategy')).toBeNull();
    expect(formData.get('files')).toBe(file);
    expect(readText).not.toHaveBeenCalled();
  });

  it('normalizes an empty upload target to the root directory', async () => {
    apiClientMock.post.mockResolvedValueOnce({
      items: [],
      total: 0,
      succeeded: 0,
      skipped: 0,
      failed: 0,
    });
    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'claude-code',
      collection: 'skills',
      scope: 'user',
    });

    await adapter.upload({ targetPath: '', files: [new File(['skill'], 'SKILL.md')] });

    const [, formData] = apiClientMock.post.mock.calls[0] as [string, FormData];
    expect(formData.get('targetPath')).toBe('/');
  });

  it('extracts an uploaded skill archive through the scoped archive endpoint', async () => {
    apiClientMock.post.mockResolvedValueOnce({
      items: [{
        sourcePath: 'demo.zip',
        finalPath: 'demo/SKILL.md',
        status: 'created',
        size: 12,
        type: 'file',
        error: null,
      }],
      total: 1,
      succeeded: 1,
      skipped: 0,
      failed: 0,
    });
    const adapter = new AgentFileTreeDataAdapter({
      workspaceId: 'ws-1',
      apiPrefix: 'codex',
      collection: 'skills',
      scope: 'project',
      runtimeBaseUrl: 'http://runtime.local',
    });

    await adapter.extractArchive({
      archivePath: 'demo.zip',
      targetPath: '/',
      defaultStrategy: 'cancel',
      resolutions: [],
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      '/workspaces/ws-1/codex/skills/extract',
      {
        archivePath: 'demo.zip',
        targetPath: '/',
        scope: 'project',
        defaultStrategy: 'cancel',
        resolutions: [],
      },
    );
  });
});
