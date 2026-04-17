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
      .mockResolvedValueOnce([
        {
          pluginName: 'openspec',
          marketplaceName: 'core',
          skillName: 'explore',
          skillPath: '/plugins/openspec/skills/explore',
        },
      ]);

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
});
