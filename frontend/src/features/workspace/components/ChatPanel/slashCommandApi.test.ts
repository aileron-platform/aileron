import { beforeEach, describe, expect, it, vi } from 'vitest';

const { getMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class MockApiClient {
    constructor(_options?: unknown) {}

    get = getMock;
  },
}));

vi.mock('@/shared/services/logger', () => ({
  createLogger: () => ({
    warn: vi.fn(),
  }),
}));

import { slashCommandApi } from './slashCommandApi';

describe('slashCommandApi.listPickerItems', () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it('merges slash commands and skills into invocation-ready picker items', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [
          {
            scope: 'project',
            documents: [
              {
                fileName: 'deploy.md',
                namespace: 'ops',
                description: 'Deploy the service',
                scope: 'project',
                size: '1 KB',
              },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        path: '/',
        scope: 'project',
        total: 1,
        nodes: [
          {
            id: '/openspec-explore',
            name: 'openspec-explore',
            path: '/openspec-explore',
            type: 'directory',
            scope: 'project',
            children: [
              {
                id: '/openspec-explore/SKILL.md',
                name: 'SKILL.md',
                path: '/openspec-explore/SKILL.md',
                type: 'file',
                scope: 'project',
              },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        path: '/openspec-explore/SKILL.md',
        scope: 'project',
        content: '---\nname: openspec-explore\ndescription: Explore a change\n---\nbody',
      })
      .mockResolvedValueOnce({
        path: '/',
        scope: 'user',
        total: 0,
        nodes: [],
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['project', 'user']);

    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/slash-commands');
    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/tree?scope=project&maxDepth=8');
    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/content?path=%2Fopenspec-explore%2FSKILL.md&scope=project');
    expect(items).toEqual([
      expect.objectContaining({
        kind: 'skill',
        displayName: 'openspec-explore',
        invocation: '/openspec-explore',
      }),
      expect.objectContaining({
        kind: 'slash-command',
        displayName: 'ops/deploy',
        invocation: '/ops/deploy',
      }),
    ]);
  });

  it('maps plugin skills to namespaced invocations', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [],
      })
      .mockResolvedValueOnce({
        path: '/',
        scope: 'project',
        total: 0,
        nodes: [],
      })
      .mockResolvedValueOnce({
        plugins: [
          {
            pluginName: 'openspec',
            marketplaceName: 'core',
            skillName: 'explore',
            skillPath: '/plugins/openspec/skills/explore',
          },
        ],
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'claude-code', ['project', 'plugin']);

    expect(items).toContainEqual(
      expect.objectContaining({
        kind: 'skill',
        pluginName: 'openspec',
        displayName: 'openspec:explore',
        invocation: '/openspec:explore',
      }),
    );
  });

  it('loads Codex plugin skills from Codex plugin resource APIs', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        layer: 'plugin',
        resource: 'skills',
        directory: '',
        files: [
          {
            name: 'review',
            path: 'review/SKILL.md',
            sizeBytes: 42,
            source: 'plugin',
            readOnly: true,
            metadata: {
              pluginId: 'demo@local',
              pluginName: 'demo',
              marketplaceName: 'local',
            },
          },
        ],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        layer: 'plugin',
        path: 'review/SKILL.md',
        content: '---\nname: review\ndescription: Review code\n---\nbody',
        exists: true,
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['plugin']);

    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/files?layer=plugin');
    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/file?layer=plugin&path=review%2FSKILL.md&pluginId=demo%40local');
    expect(items).toEqual([
      expect.objectContaining({
        kind: 'skill',
        pluginName: 'demo',
        displayName: 'demo:review',
        invocation: '/demo:review',
        description: 'Review code',
      }),
    ]);
  });

  it('loads root-level Codex plugin SKILL.md documents', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        layer: 'plugin',
        resource: 'skills',
        directory: '',
        files: [
          {
            name: 'SKILL.md',
            path: 'SKILL.md',
            sizeBytes: 42,
            source: 'plugin',
            readOnly: true,
            metadata: {
              pluginId: 'single@local',
              pluginName: 'single',
              marketplaceName: 'local',
            },
          },
        ],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        layer: 'plugin',
        path: 'SKILL.md',
        content: '---\nname: single-review\ndescription: Review from root skill\n---\nbody',
        exists: true,
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['plugin']);

    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/file?layer=plugin&path=SKILL.md&pluginId=single%40local');
    expect(items).toEqual([
      expect.objectContaining({
        kind: 'skill',
        pluginName: 'single',
        displayName: 'single:single-review',
        invocation: '/single:single-review',
      }),
    ]);
  });

  it('hides disabled Codex plugin skills when plugin resources return no files', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        layer: 'plugin',
        resource: 'skills',
        directory: '',
        files: [],
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['plugin']);

    expect(getMock).toHaveBeenCalledWith('/api/v1/workspaces/ws-1/codex/skills/files?layer=plugin');
    expect(items).toEqual([]);
  });

  it('keeps Codex prompts when plugin skill discovery fails', async () => {
    getMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [
          {
            scope: 'project',
            documents: [
              {
                fileName: 'review.md',
                description: 'Review the workspace',
                scope: 'project',
                size: '1 KB',
              },
            ],
          },
        ],
      })
      .mockRejectedValueOnce(new Error('plugin unavailable'));

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['plugin']);

    expect(items).toEqual([
      expect.objectContaining({
        kind: 'slash-command',
        displayName: 'review',
        invocation: '/review',
      }),
    ]);
  });

  it('keeps Codex skills when prompt discovery fails', async () => {
    getMock
      .mockRejectedValueOnce(new Error('prompts unavailable'))
      .mockResolvedValueOnce({
        path: '/',
        scope: 'project',
        total: 1,
        nodes: [
          {
            id: '/review',
            name: 'review',
            path: '/review',
            type: 'directory',
            scope: 'project',
            children: [
              {
                id: '/review/SKILL.md',
                name: 'SKILL.md',
                path: '/review/SKILL.md',
                type: 'file',
                scope: 'project',
              },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        path: '/review/SKILL.md',
        scope: 'project',
        content: '---\nname: review\ndescription: Review code\n---\nbody',
      });

    const items = await slashCommandApi.listPickerItems('http://runtime.test', 'ws-1', 'codex', ['project']);

    expect(items).toEqual([
      expect.objectContaining({
        kind: 'skill',
        displayName: 'review',
        invocation: '/review',
      }),
    ]);
  });
});
