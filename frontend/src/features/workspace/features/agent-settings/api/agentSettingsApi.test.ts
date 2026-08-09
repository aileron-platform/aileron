import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());
const apiPutMock = vi.hoisted(() => vi.fn());
const apiPatchMock = vi.hoisted(() => vi.fn());
const apiDeleteMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class MockApiClient {
    get = apiGetMock;
    post = apiPostMock;
    put = apiPutMock;
    patch = apiPatchMock;
    delete = apiDeleteMock;
  },
}));

import {
  buildHookRulesFromAgentHook,
  createAgentSettingsApi,
  mapHookScopeDocumentToAgentHooks,
} from './agentSettingsApi';

beforeEach(() => {
  apiGetMock.mockReset();
  apiPostMock.mockReset();
  apiPutMock.mockReset();
  apiPatchMock.mockReset();
  apiDeleteMock.mockReset();
});

describe('agentSettingsApi plugin resources', () => {
  it('updates Codex plugin MCP policy and hook trust through independent endpoints', async () => {
    apiPatchMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'user',
        pluginId: 'review tools/official',
        serverId: 'search/tools',
        policy: {},
        effective: true,
        revision: 'policy-r2',
        providerResourceGeneration: 8,
        newThreadRequired: true,
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'user',
        pluginId: 'review tools/official',
        trusted: false,
        trustState: 'untrusted',
        revision: 'trust-r2',
        providerResourceGeneration: 9,
        newThreadRequired: true,
      });
    const api = createAgentSettingsApi('codex');
    const policy = {
      enabled: true,
      defaultToolsApprovalMode: 'prompt' as const,
      enabledTools: ['search'],
      disabledTools: null,
      tools: {
        search: { approvalMode: 'approve' as const },
      },
    };

    await api.updateCodexPluginMcpPolicy(
      'http://runtime.test',
      'ws-1',
      'review tools/official',
      'search/tools',
      policy,
      'policy-r1',
    );
    await api.updateCodexPluginHookTrust(
      'http://runtime.test',
      'ws-1',
      'review tools/official',
      false,
      'trust-r1',
    );

    expect(apiPatchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/codex/plugins/review%20tools/official/mcp-servers/search/tools/policy',
      {
        scope: 'user',
        policy,
        revision: 'policy-r1',
      },
      undefined,
    );
    expect(apiPatchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/codex/plugins/review%20tools/official/hook-trust',
      {
        scope: 'user',
        trusted: false,
        revision: 'trust-r1',
      },
      undefined,
    );
  });
});

describe('agentSettingsApi hook mapping', () => {
  it('uses the backend scope query parameter for Codex rules files', async () => {
    apiGetMock.mockResolvedValueOnce({ files: [] });
    const api = createAgentSettingsApi('codex');

    await api.listCodexRules('http://runtime.test', 'ws-1', 'project');

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/rules?scope=project',
      undefined,
    );
  });

  it('preserves hook scope revision and sends it when saving', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scopes: [
        {
          scope: 'project',
          revision: 'project-r1',
          hooks: {
            PreToolUse: [
              {
                matcher: 'Write',
                hooks: [{ type: 'command', command: 'echo write' }],
              },
            ],
          },
        },
      ],
    });
    apiPutMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r2',
      hooks: {
        PreToolUse: [
          {
            matcher: 'Write',
            hooks: [{ type: 'command', command: 'echo updated' }],
          },
        ],
      },
    });
    const api = createAgentSettingsApi('claude-code');

    const scopes = await api.listHookScopes('http://runtime.test', 'ws-1');
    const updated = await api.updateHookScope(
      'http://runtime.test',
      'ws-1',
      'project',
      {
        PreToolUse: [
          {
            matcher: 'Write',
            hooks: [{ type: 'command', command: 'echo updated' }],
          },
        ],
      },
      scopes.scopes[0].revision,
    );

    expect(scopes.scopes[0]).toEqual(expect.objectContaining({
      revision: 'project-r1',
    }));
    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/hooks/project',
      {
        hooks: {
          PreToolUse: [
            {
              matcher: 'Write',
              hooks: [{ type: 'command', command: 'echo updated' }],
            },
          ],
        },
        revision: 'project-r1',
      },
      undefined,
    );
    expect(updated).toEqual(expect.objectContaining({
      revision: 'project-r2',
    }));
  });

  it('preserves hook action name and description when loading scope documents', () => {
    const hooks = mapHookScopeDocumentToAgentHooks({
      scope: 'project',
      hooks: {
        PreToolUse: [
          {
            matcher: 'Write',
            hooks: [
              {
                type: 'command',
                name: 'security-check',
                description: 'Check commands before execution',
                command: 'echo write',
                timeout: 30,
              },
            ],
          },
        ],
      },
    });

    expect(hooks[0].matchers[0].hooks[0]).toEqual({
      type: 'command',
      name: 'security-check',
      description: 'Check commands before execution',
      command: 'echo write',
      timeout: 30,
      statusMessage: undefined,
    });
  });

  it('groups plugin hook rules by event type with source metadata', () => {
    const hooks = mapHookScopeDocumentToAgentHooks({
      scope: 'plugin',
      hooks: {
        SessionStart: [
          {
            matcher: 'm1',
            pluginName: 'asdf',
            marketplaceName: 'local-marketplace',
            hooks: [{ type: 'command', command: 'echo "m1"', timeout: 600 }],
          },
          {
            matcher: 'm2',
            pluginName: 'other',
            marketplaceName: 'local-marketplace',
            hooks: [{ type: 'http', url: 'http://m2', timeout: 30 }],
          },
        ],
      },
    });

    expect(hooks).toEqual([
      expect.objectContaining({
        id: 'plugin:SessionStart',
        scope: 'plugin',
        eventName: 'SessionStart',
        pluginName: 'asdf',
        marketplaceName: 'local-marketplace',
        matchers: [
          expect.objectContaining({ matcher: 'm1' }),
          expect.objectContaining({ matcher: 'm2' }),
        ],
      }),
    ]);
  });

  it('persists non-empty hook action metadata and omits blank metadata when saving', () => {
    expect(buildHookRulesFromAgentHook({
      id: 'project:PreToolUse',
      scope: 'project',
      eventName: 'PreToolUse',
      matchers: [
        {
          matcher: 'Write',
          hooks: [
            {
              type: 'command',
              name: ' security-check ',
              description: ' Check commands before execution ',
              command: ' echo write ',
              timeout: 30,
            },
            {
              type: 'command',
              name: '   ',
              description: '   ',
              command: ' echo empty ',
              timeout: 15,
            },
          ],
        },
      ],
    })).toEqual([
      {
        matcher: 'Write',
        hooks: [
          {
            type: 'command',
            name: 'security-check',
            description: 'Check commands before execution',
            command: 'echo write',
            timeout: 30,
          },
          {
            type: 'command',
            command: 'echo empty',
            timeout: 15,
          },
        ],
      },
    ]);
  });
});

describe('agentSettingsApi codex hook revision mapping', () => {
  it('uses scope path routes and sends revision when mutating codex hooks', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      source: 'hooks_json',
      path: '/workspace/.codex/hooks.json',
      content: '{}',
      exists: true,
      revision: 'project-r1',
      featureEnabled: true,
      inlineHooks: [],
      entries: [],
      eventMetadata: [],
    });
    apiPutMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'project',
        source: 'hooks_json',
        path: '/workspace/.codex/hooks.json',
        content: '{"hooks":{}}',
        exists: true,
        revision: 'project-r2',
        featureEnabled: true,
        inlineHooks: [],
        entries: [],
        eventMetadata: [],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'project',
        source: 'hooks_json',
        path: '/workspace/.codex/hooks.json',
        content: '{"hooks":{}}',
        exists: true,
        revision: 'project-r3',
        featureEnabled: true,
        inlineHooks: [],
        entries: [],
        eventMetadata: [],
      });
    apiDeleteMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      source: 'hooks_json',
      path: '/workspace/.codex/hooks.json',
      content: '{}',
      exists: true,
      revision: 'project-r4',
      featureEnabled: true,
      inlineHooks: [],
      entries: [],
      eventMetadata: [],
    });
    apiPostMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      layer: 'project',
      featureEnabled: true,
    }).mockResolvedValueOnce({
      workspaceId: 'ws-1',
      layer: 'project',
      featureEnabled: false,
    });
    const api = createAgentSettingsApi('codex');
    const entry = {
      id: 'project:PreToolUse:0',
      event: 'PreToolUse',
      index: 0,
      actions: [{ type: 'command' as const, command: 'echo ok' }],
      source: 'hooks_json' as const,
      readOnly: false,
    };

    await api.getCodexHooks('http://runtime.test', 'ws-1', 'project');
    await api.updateCodexHooks('http://runtime.test', 'ws-1', 'project', '{"hooks":{}}', 'project-r1');
    await api.upsertCodexHookEntry('http://runtime.test', 'ws-1', 'project', entry, 'project-r2', null);
    await api.deleteCodexHookEntry('http://runtime.test', 'ws-1', 'project', entry, 'project-r3');
    await api.enableCodexHooks('http://runtime.test', 'ws-1', 'project');
    await api.disableCodexHooks('http://runtime.test', 'ws-1', 'project');

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/hooks/project',
      undefined,
    );
    expect(apiPutMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/codex/hooks/project',
      { content: '{"hooks":{}}', revision: 'project-r1' },
      undefined,
    );
    expect(apiPutMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/codex/hooks/project/entry',
      { entry, previous: null, revision: 'project-r2' },
      undefined,
    );
    expect(apiDeleteMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/hooks/project/entry',
      undefined,
      { entry, revision: 'project-r3' },
    );
    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/hooks/project/enable',
      undefined,
      undefined,
    );
    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/hooks/project/disable',
      undefined,
      undefined,
    );
  });
});

describe('agentSettingsApi agents-md revision mapping', () => {
  it('loads Codex agents-md from the query scope route', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      content: '# Codex',
      path: '/workspace/AGENTS.md',
      exists: true,
      maxBytes: 200,
      sizeBytes: 7,
      revision: 'project-r1',
      caveats: [],
    });
    const api = createAgentSettingsApi('codex');

    await api.getCodexAgentsMd('http://runtime.test', 'ws-1', 'project');

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/agents-md?scope=project',
      undefined,
    );
  });

  it('sends revision when saving Claude agents-md', async () => {
    apiPutMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r2',
    });
    const api = createAgentSettingsApi('claude-code');

    await api.updateAgentsMd('http://runtime.test', 'ws-1', {
      scope: 'project',
      content: '# Agents',
      revision: 'project-r1',
    });

    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/agents-md',
      {
        scope: 'project',
        content: '# Agents',
        revision: 'project-r1',
      },
      undefined,
    );
  });

  it('sends revision when saving Codex agents-md', async () => {
    apiPutMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'user',
      path: '/home/user/.codex/AGENTS.md',
      revision: 'user-r2',
    });
    const api = createAgentSettingsApi('codex');

    await api.updateCodexAgentsMd('http://runtime.test', 'ws-1', {
      scope: 'user',
      content: '# Codex',
      revision: 'user-r1',
    });

    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/codex/agents-md',
      {
        scope: 'user',
        content: '# Codex',
        revision: 'user-r1',
      },
      undefined,
    );
  });
});

describe('agentSettingsApi resource error mapping', () => {
  it('maps unified error envelopes through the shared parser', async () => {
    apiPatchMock.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            errorCode: 'REVISION_CONFLICT',
            message: 'Resource was modified',
            validationResults: [{ path: 'plugins.demo' }],
          },
        },
      },
    });
    const api = createAgentSettingsApi('codex');

    await expect(
      api.setCodexPluginEnabled('http://runtime.test', 'ws-1', 'demo', 'project', false),
    ).rejects.toMatchObject({
      message: 'Resource was modified',
      errorCode: 'REVISION_CONFLICT',
      validationResults: [{ path: 'plugins.demo' }],
    });
  });
});

describe('agentSettingsApi output style revision mapping', () => {
  it('maps output style detail revisions and sends revision when mutating', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [
          {
            scope: 'project',
            revision: 'scope-r1',
            documents: [
              {
                fileName: 'concise.md',
                name: 'Concise',
                description: 'Short answers',
                scope: 'project',
                size: '12B',
              },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'project',
        revision: 'doc-r1',
        document: {
          fileName: 'concise.md',
          name: 'Concise',
          description: 'Short answers',
          scope: 'project',
          size: '12B',
          content: '# Concise',
        },
      });
    apiPostMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'doc-r2',
      document: {
        fileName: 'new.md',
        name: 'New',
        scope: 'project',
        size: '10B',
        content: '# New',
      },
    });
    apiPutMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'doc-r3',
      document: {
        fileName: 'concise.md',
        name: 'Concise',
        scope: 'project',
        size: '12B',
        content: '# Updated',
      },
    });
    apiDeleteMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      fileName: 'concise.md',
      revision: 'scope-r2',
      deleted: true,
    });
    const api = createAgentSettingsApi('claude-code');

    const result = await api.listOutputStyles('http://runtime.test', 'ws-1');
    const document = await api.loadOutputStyle(
      'http://runtime.test',
      'ws-1',
      result.items[0],
    );
    await api.createOutputStyle('http://runtime.test', 'ws-1', {
      id: 'project:new.md',
      title: 'New',
      scope: 'project',
      content: '# New',
      metadata: { fileName: 'new.md', revision: 'scope-r1' },
    });
    await api.updateOutputStyle('http://runtime.test', 'ws-1', {
      ...document,
      content: '# Updated',
    });
    await api.deleteOutputStyle('http://runtime.test', 'ws-1', document);

    expect(result).toEqual(expect.objectContaining({
      items: [
        expect.objectContaining({
          id: 'project:concise.md',
          metadata: expect.objectContaining({
            fileName: 'concise.md',
            revision: 'scope-r1',
          }),
        }),
      ],
      availableScopes: [{ scope: 'project', readOnly: false }],
    }));
    expect(document).toEqual(expect.objectContaining({
      content: '# Concise',
      metadata: expect.objectContaining({ revision: 'doc-r1' }),
    }));
    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/output-styles/project',
      {
        fileName: 'new.md',
        content: '# New',
        name: 'New',
        description: undefined,
        revision: 'scope-r1',
      },
      undefined,
    );
    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/output-styles/project/concise.md',
      {
        content: '# Updated',
        name: 'Concise',
        description: 'Short answers',
        revision: 'doc-r1',
      },
      undefined,
    );
    expect(apiDeleteMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/output-styles/project/concise.md?revision=doc-r1',
      undefined,
      undefined,
    );
  });

  it('uses stable relative locators for same-name nested plugin output styles', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        providerResourceGeneration: 12,
        scopes: [{
          scope: 'plugin',
          revision: 'plugin-r1',
          documents: [
            {
              fileName: 'output-styles/a/concise.md',
              name: 'Concise A',
              scope: 'plugin',
              size: '12B',
              pluginId: 'review@official',
              pluginName: 'Review Tools',
              marketplaceId: 'official',
              enabled: true,
              readOnly: true,
              editable: false,
              relativeSourcePath: 'output-styles/a/concise.md',
              generation: 12,
            },
            {
              fileName: 'output-styles/b/concise.md',
              name: 'Concise B',
              scope: 'plugin',
              size: '12B',
              pluginId: 'review@official',
              pluginName: 'Review Tools',
              marketplaceId: 'official',
              enabled: true,
              readOnly: true,
              editable: false,
              relativeSourcePath: 'output-styles/b/concise.md',
              generation: 12,
            },
          ],
        }],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        providerResourceGeneration: 12,
        scope: 'plugin',
        revision: 'plugin-r1',
        document: {
          fileName: 'output-styles/a/concise.md',
          name: 'Concise A',
          scope: 'plugin',
          size: '12B',
          content: '# Concise A',
          pluginId: 'review@official',
          pluginName: 'Review Tools',
          marketplaceId: 'official',
          enabled: true,
          readOnly: true,
          editable: false,
          relativeSourcePath: 'output-styles/a/concise.md',
          generation: 12,
        },
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        providerResourceGeneration: 12,
        scope: 'plugin',
        revision: 'plugin-r1',
        document: {
          fileName: 'output-styles/b/concise.md',
          name: 'Concise B',
          scope: 'plugin',
          size: '12B',
          content: '# Concise B',
          pluginId: 'review@official',
          pluginName: 'Review Tools',
          marketplaceId: 'official',
          enabled: true,
          readOnly: true,
          editable: false,
          relativeSourcePath: 'output-styles/b/concise.md',
          generation: 12,
        },
      });
    const api = createAgentSettingsApi('claude-code');

    const result = await api.listOutputStyles(
      'http://runtime.test',
      'ws-1',
      { scope: 'plugin', pluginId: 'review@official' },
    );
    await Promise.all(result.items.map((document) =>
      api.loadOutputStyle('http://runtime.test', 'ws-1', document)));

    expect(apiGetMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/claude-code/output-styles?scope=plugin&pluginId=review%40official',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/output-styles/plugin/output-styles/a/concise.md?pluginId=review%40official',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/workspaces/ws-1/claude-code/output-styles/plugin/output-styles/b/concise.md?pluginId=review%40official',
      undefined,
    );
    expect(result).toEqual(expect.objectContaining({
      providerResourceGeneration: 12,
      availableScopes: [{ scope: 'plugin', readOnly: true }],
      items: [
        expect.objectContaining({
          id: 'plugin:review@official:output-styles/a/concise.md',
          scope: 'plugin',
          pluginName: 'Review Tools',
          metadata: expect.objectContaining({
            fileName: 'output-styles/a/concise.md',
            pluginId: 'review@official',
            readOnly: true,
            editable: false,
            relativeSourcePath: 'output-styles/a/concise.md',
            generation: 12,
          }),
        }),
        expect.objectContaining({
          id: 'plugin:review@official:output-styles/b/concise.md',
          scope: 'plugin',
          pluginName: 'Review Tools',
          metadata: expect.objectContaining({
            fileName: 'output-styles/b/concise.md',
            pluginId: 'review@official',
            readOnly: true,
            editable: false,
            relativeSourcePath: 'output-styles/b/concise.md',
            generation: 12,
          }),
        }),
      ],
    }));
  });

  it('namespaces identical plugin output-style locators by plugin identity', async () => {
    const locator = 'output-styles/shared/style.md';
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        providerResourceGeneration: 13,
        scopes: [{
          scope: 'plugin',
          documents: [
            {
              fileName: locator,
              name: 'Review Style',
              scope: 'plugin',
              size: '12B',
              pluginId: 'review@official',
            },
            {
              fileName: locator,
              name: 'Build Style',
              scope: 'plugin',
              size: '12B',
              pluginId: 'build@community',
            },
          ],
        }],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        document: {
          fileName: locator,
          name: 'Review Style',
          scope: 'plugin',
          size: '12B',
          content: '# Review',
          pluginId: 'review@official',
        },
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        document: {
          fileName: locator,
          name: 'Build Style',
          scope: 'plugin',
          size: '12B',
          content: '# Build',
          pluginId: 'build@community',
        },
      });
    const api = createAgentSettingsApi('claude-code');

    const result = await api.listOutputStyles(
      'http://runtime.test',
      'ws-1',
      { scope: 'plugin' },
    );
    await Promise.all(result.items.map((document) =>
      api.loadOutputStyle('http://runtime.test', 'ws-1', document)));

    expect(result.items.map(document => document.id).sort()).toEqual([
      'plugin:build@community:output-styles/shared/style.md',
      'plugin:review@official:output-styles/shared/style.md',
    ]);
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/output-styles/plugin/output-styles/shared/style.md?pluginId=review%40official',
      undefined,
    );
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/output-styles/plugin/output-styles/shared/style.md?pluginId=build%40community',
      undefined,
    );
  });
});

describe('agentSettingsApi slash command mapping', () => {
  it('preserves Claude plugin slash command source metadata', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        items: [
          {
            path: 'review.md',
            scope: 'plugin',
            description: 'Review selected code',
            size: '120B',
            pluginName: 'quality',
            marketplaceName: 'team-tools',
          },
        ],
        availableScopes: [{ scope: 'plugin', readOnly: true }],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        revision: 'r1',
        document: {
          path: 'review.md',
          description: 'Review selected code',
          scope: 'plugin',
          size: '120B',
          content: '# Review',
          pluginName: 'quality',
          marketplaceName: 'team-tools',
        },
      });

    const api = createAgentSettingsApi('claude-code');
    const documents = await api.listSlashCommands('http://runtime.test', 'ws-1');
    const loaded = await api.loadSlashCommand(
      'http://runtime.test',
      'ws-1',
      documents.items[0],
    );

    expect(apiGetMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/plugin/content?path=review.md',
      undefined,
    );
    expect([loaded]).toEqual([
      expect.objectContaining({
        id: 'plugin:review.md',
        title: 'quality:review',
        scope: 'plugin',
        pluginName: 'quality',
        marketplaceName: 'team-tools',
        metadata: expect.objectContaining({
          source: 'plugin',
          pluginName: 'quality',
          marketplaceName: 'team-tools',
          format: 'markdown',
          revision: 'r1',
        }),
      }),
    ]);
    expect(documents.availableScopes).toEqual([{ scope: 'plugin', readOnly: true }]);
  });

  it('loads plugin slash command details by path without ambiguous file lookups', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        items: [
          {
            path: 'drive/search.md',
            description: 'Drive search',
            scope: 'plugin',
            size: '120B',
            format: 'markdown',
            pluginName: 'google-workspace',
            marketplaceName: 'team-tools',
          },
          {
            path: 'gmail/search.md',
            description: 'Gmail search',
            scope: 'plugin',
            size: '130B',
            format: 'markdown',
            pluginName: 'google-workspace',
            marketplaceName: 'team-tools',
          },
        ],
        availableScopes: [{ scope: 'plugin', readOnly: true }],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        revision: 'drive-r1',
        document: {
          path: 'drive/search.md',
          description: 'Drive search',
          scope: 'plugin',
          size: '120B',
          format: 'markdown',
          content: 'prompt = "drive"',
          pluginName: 'google-workspace',
          marketplaceName: 'team-tools',
        },
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        revision: 'gmail-r1',
        document: {
          path: 'gmail/search.md',
          description: 'Gmail search',
          scope: 'plugin',
          size: '130B',
          format: 'markdown',
          content: 'prompt = "gmail"',
          pluginName: 'google-workspace',
          marketplaceName: 'team-tools',
        },
      });

    const api = createAgentSettingsApi('claude-code');
    const documents = await api.listSlashCommands('http://runtime.test', 'ws-1');
    await Promise.all(documents.items.map((document) =>
      api.loadSlashCommand('http://runtime.test', 'ws-1', document)));

    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/plugin/content?path=drive%2Fsearch.md',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/plugin/content?path=gmail%2Fsearch.md',
      undefined,
    );
    expect(documents.items.map((document) => document.id)).toEqual([
      'plugin:drive/search.md',
      'plugin:gmail/search.md',
    ]);
    expect(documents.items.map((document) => document.pluginName)).toEqual(['google-workspace', 'google-workspace']);
  });

  it('fetches scope revision when creating a slash command without a revision', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'user',
      revision: 'scope-r1',
      documents: [],
    });
    apiPostMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'user',
      revision: 'doc-r1',
      document: {
        path: 'deploy.md',
        description: 'deploy command',
        scope: 'user',
        size: '12B',
        content: '# Deploy',
      },
    });
    const api = createAgentSettingsApi('claude-code');

    await api.createSlashCommand('http://runtime.test', 'ws-1', {
      id: 'user:deploy.md',
      title: 'deploy.md',
      scope: 'user',
      content: '# Deploy',
      metadata: { fileName: 'deploy.md', relativePath: 'deploy.md' },
    });

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/user',
      undefined,
    );
    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/user',
      {
        path: 'deploy.md',
        content: '# Deploy',
        revision: 'scope-r1',
      },
      undefined,
    );
  });
});

describe('agentSettingsApi mcp revision mapping', () => {
  it('maps Codex plugin definition metadata separately from its user policy', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scopes: [{
        scope: 'plugin',
        mcpServers: {
          search: {
            type: 'stdio',
            command: 'node',
            enabled: true,
            pluginId: 'demo@local',
            pluginName: 'Demo',
            marketplaceName: 'local',
            relativeSourcePath: '.mcp.json',
            generation: 7,
            readOnly: true,
            editable: false,
            effective: false,
            serverId: 'search',
            policyRevision: 'policy-r1',
            policy: {
              enabled: false,
              defaultToolsApprovalMode: null,
              enabledTools: null,
              disabledTools: null,
              tools: {},
            },
          },
        },
      }],
    });
    const api = createAgentSettingsApi('codex');

    const [server] = await api.listMcpServers('http://runtime.test', 'ws-1');

    expect(server).toMatchObject({
      id: 'plugin:demo@local:search',
      name: 'search',
      scope: 'plugin',
      readOnly: true,
      editable: false,
      effective: false,
      serverId: 'search',
      pluginId: 'demo@local',
      policyRevision: 'policy-r1',
      policy: {
        enabled: false,
      },
    });
  });

  it('maps scope revision onto listed MCP servers and sends it in mutations', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scopes: [
        {
          scope: 'project',
          revision: 'project-r1',
          mcpServers: {
            docs: {
              type: 'stdio',
              command: 'npx',
              args: ['docs'],
              enabled: true,
            },
          },
        },
      ],
    });
    apiPostMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r2',
      mcpServers: {
        docs: {
          type: 'stdio',
          command: 'npx',
          args: ['docs'],
          enabled: true,
        },
      },
    });
    apiPutMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r3',
      mcpServers: {
        docs: {
          type: 'stdio',
          command: 'node',
          args: ['server.js'],
          enabled: true,
        },
      },
    });
    apiPatchMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r4',
      mcpServers: {
        docs: {
          type: 'stdio',
          command: 'node',
          args: ['server.js'],
          enabled: false,
        },
      },
    });
    apiDeleteMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r5',
    });

    const api = createAgentSettingsApi('claude-code');
    const [server] = await api.listMcpServers('http://runtime.test', 'ws-1');

    expect(server).toEqual(expect.objectContaining({
      id: 'project:docs',
      name: 'docs',
      scope: 'project',
      revision: 'project-r1',
    }));

    await api.createMcpServer('http://runtime.test', 'ws-1', server);
    await api.updateMcpServer('http://runtime.test', 'ws-1', {
      ...server,
      command: 'node',
      args: ['server.js'],
    });
    await api.toggleMcpServerStatus('http://runtime.test', 'ws-1', server, false);
    await api.deleteMcpServer('http://runtime.test', 'ws-1', server);

    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/mcp-servers/project',
      {
        revision: 'project-r1',
        mcpServers: {
          docs: {
            type: 'stdio',
            command: 'npx',
            args: ['docs'],
          },
        },
      },
      undefined,
    );
    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/mcp-servers/project/docs',
      {
        revision: 'project-r1',
        mcpServers: {
          docs: {
            type: 'stdio',
            command: 'node',
            args: ['server.js'],
          },
        },
      },
      undefined,
    );
    expect(apiPatchMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/mcp-servers/project/docs/toggle?enabled=false&revision=project-r1',
      undefined,
      undefined,
    );
    expect(apiDeleteMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/mcp-servers/project/docs?revision=project-r1',
      undefined,
      undefined,
    );
  });

  it('sends revision when importing MCP servers', async () => {
    apiPostMock.mockResolvedValue({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r2',
      created: ['docs'],
      updated: [],
      skipped: [],
    });
    const api = createAgentSettingsApi('claude-code');
    const file = new File(['{}'], 'mcp.json', { type: 'application/json' });

    await api.importMcpServers('http://runtime.test', 'ws-1', {
      scope: 'project',
      file,
      overwrite: true,
      revision: 'project-r1',
    });

    const formData = apiPostMock.mock.calls[0][1] as FormData;
    expect(apiPostMock.mock.calls[0][0]).toBe('/api/v1/workspaces/ws-1/claude-code/mcp-import');
    expect(formData.get('scope')).toBe('project');
    expect(formData.get('overwrite')).toBe('true');
    expect(formData.get('revision')).toBe('project-r1');
    expect(formData.get('file')).toBe(file);
  });

  it('loads current MCP scope revision before importing when payload has no revision', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r1',
      mcpServers: {},
    });
    apiPostMock.mockResolvedValue({
      workspaceId: 'ws-1',
      scope: 'project',
      revision: 'project-r2',
      created: ['docs'],
      updated: [],
      skipped: [],
    });
    const api = createAgentSettingsApi('claude-code');
    const file = new File(['{}'], 'mcp.json', { type: 'application/json' });

    await api.importMcpServers('http://runtime.test', 'ws-1', {
      scope: 'project',
      file,
    });

    const formData = apiPostMock.mock.calls[0][1] as FormData;
    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/mcp-servers/project',
      undefined,
    );
    expect(formData.get('revision')).toBe('project-r1');
  });
});

describe('agentSettingsApi subagent updates', () => {
  it('loads subagents by path without ambiguous file lookups', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        items: [
          {
            path: 'drive/search.md',
            name: 'search',
            description: 'Drive search',
            scope: 'project',
            size: '120B',
          },
          {
            path: 'gmail/search.md',
            name: 'search',
            description: 'Gmail search',
            scope: 'project',
            size: '130B',
          },
        ],
        availableScopes: [{ scope: 'project', readOnly: false }],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'project',
        revision: 'drive-r1',
        document: {
          path: 'drive/search.md',
          name: 'search',
          description: 'Drive search',
          scope: 'project',
          size: '120B',
          content: '# Drive',
        },
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'project',
        revision: 'gmail-r1',
        document: {
          path: 'gmail/search.md',
          name: 'search',
          description: 'Gmail search',
          scope: 'project',
          size: '130B',
          content: '# Gmail',
        },
      });

    const api = createAgentSettingsApi('claude-code');
    const documents = await api.listSubagents('http://runtime.test', 'ws-1');
    const loaded = await Promise.all(documents.items.map((document) =>
      api.loadSubagent('http://runtime.test', 'ws-1', document)));

    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/subagents/project/content?path=drive%2Fsearch.md',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/workspaces/ws-1/claude-code/subagents/project/content?path=gmail%2Fsearch.md',
      undefined,
    );
    expect({ ...documents, items: loaded }).toEqual({
      items: [
        expect.objectContaining({
          id: 'project:drive/search.md',
          title: 'search',
          metadata: expect.objectContaining({
            fileName: 'drive/search.md',
            relativePath: 'drive/search.md',
            revision: 'drive-r1',
          }),
        }),
        expect.objectContaining({
          id: 'project:gmail/search.md',
          title: 'search',
          metadata: expect.objectContaining({
            fileName: 'gmail/search.md',
            relativePath: 'gmail/search.md',
            revision: 'gmail-r1',
          }),
        }),
      ],
      availableScopes: [{ scope: 'project', readOnly: false }],
    });
  });

  it('updates and deletes subagents with path body/query and revision token', async () => {
    apiPutMock.mockResolvedValue({
      scope: 'project',
      revision: 'new-r2',
      document: {
        path: 'team/new.md',
        name: 'new',
        description: 'new subagent',
        content: '# New',
        size: '12B',
      },
    });
    apiDeleteMock.mockResolvedValue({ revision: 'scope-r2', deleted: true });
    const api = createAgentSettingsApi('claude-code');

    const document = await api.updateSubagent(
      'http://runtime.test',
      'ws-1',
      {
        id: 'project:new.md',
        title: 'new.md',
        scope: 'project',
        content: '# New',
        metadata: {
          fileName: 'team/new.md',
          relativePath: 'team/new.md',
          revision: 'old-r1',
        },
      },
    );
    await api.deleteSubagent('http://runtime.test', 'ws-1', {
      title: 'new.md',
      scope: 'project',
      metadata: {
        fileName: 'team/new.md',
        relativePath: 'team/new.md',
        revision: 'new-r2',
      },
    });

    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/subagents/project/content',
      {
        path: 'team/new.md',
        content: '# New',
        revision: 'old-r1',
      },
      undefined,
    );
    expect(apiDeleteMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/subagents/project/content?path=team%2Fnew.md&revision=new-r2',
      undefined,
      undefined,
    );
    expect(document).toEqual(expect.objectContaining({
      id: 'project:team/new.md',
      title: 'new',
      content: '# New',
      metadata: expect.objectContaining({
        relativePath: 'team/new.md',
        revision: 'new-r2',
      }),
    }));
  });

  it('fetches scope revision when creating a subagent without a revision', async () => {
    apiGetMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'user',
      revision: 'scope-r1',
      documents: [],
    });
    apiPostMock.mockResolvedValueOnce({
      workspaceId: 'ws-1',
      scope: 'user',
      revision: 'doc-r1',
      document: {
        path: 'ADF.md',
        name: 'ADF',
        description: 'ADF subagent',
        scope: 'user',
        size: '12B',
        content: '# ADF',
      },
    });
    const api = createAgentSettingsApi('claude-code');

    await api.createSubagent('http://runtime.test', 'ws-1', {
      id: 'user:ADF.md',
      title: 'ADF.md',
      scope: 'user',
      content: '# ADF',
      metadata: { fileName: 'ADF.md', relativePath: 'ADF.md' },
    });

    expect(apiGetMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/subagents/user',
      undefined,
    );
    expect(apiPostMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/subagents/user',
      {
        path: 'ADF.md',
        content: '# ADF',
        revision: 'scope-r1',
      },
      undefined,
    );
  });
});

describe('agentSettingsApi memory mapping', () => {
  it('maps flat memory list, resource result detail, and revision metadata', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        revision: 'collection-r1',
        items: [
          {
            path: 'notes/today.md',
            scope: 'user',
            name: 'Today',
            description: 'daily notes',
            size: '12B',
          },
        ],
        availableScopes: [
          { scope: 'project', readOnly: false },
          { scope: 'user', readOnly: false },
        ],
      })
      .mockResolvedValueOnce({
        revision: 'doc-r1',
        resource: {
          path: 'notes/today.md',
          scope: 'user',
          name: 'Today',
          description: 'daily notes',
          size: '12B',
          content: '# Today',
        },
      });

    const api = createAgentSettingsApi('claude-code');
    const result = await api.listMemoryDocuments('http://runtime.test', 'ws-1');
    const loaded = await api.loadMemoryDocument(
      'http://runtime.test',
      'ws-1',
      result.items[0],
    );

    expect(apiGetMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/claude-code/memory',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/memory/user/content?path=notes%2Ftoday.md',
      undefined,
    );
    expect({ ...result, items: [loaded] }).toEqual({
      items: [
        expect.objectContaining({
          id: 'user:notes/today.md',
          title: 'Today',
          scope: 'user',
          content: '# Today',
          metadata: expect.objectContaining({
            fileName: 'notes/today.md',
            relativePath: 'notes/today.md',
            revision: 'doc-r1',
          }),
        }),
      ],
      availableScopes: [
        { scope: 'project', readOnly: false },
        { scope: 'user', readOnly: false },
      ],
    });
  });

  it('updates and deletes memory documents with path query and revision token', async () => {
    apiPutMock.mockResolvedValue({
      revision: 'doc-r2',
      resource: {
        path: 'notes/today.md',
        scope: 'user',
        name: 'Today',
        size: '12B',
        content: '# Updated',
      },
    });
    apiDeleteMock.mockResolvedValue({ revision: 'collection-r2', resource: { deleted: true } });
    const api = createAgentSettingsApi('claude-code');
    const document = {
      id: 'user:notes/today.md',
      title: 'Today',
      scope: 'user' as const,
      content: '# Updated',
      metadata: {
        fileName: 'notes/today.md',
        revision: 'doc-r1',
      },
    };

    await api.updateMemoryDocument('http://runtime.test', 'ws-1', document);
    await api.deleteMemoryDocument('http://runtime.test', 'ws-1', document);

    expect(apiPutMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/memory/user/content',
      {
        path: 'notes/today.md',
        content: '# Updated',
        revision: 'doc-r1',
      },
      undefined,
    );
    expect(apiDeleteMock).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/claude-code/memory/user/content?path=notes%2Ftoday.md&revision=doc-r1',
      undefined,
      undefined,
    );
  });
});
