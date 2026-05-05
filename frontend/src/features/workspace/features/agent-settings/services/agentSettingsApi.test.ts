import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiGetMock = vi.hoisted(() => vi.fn());

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: class MockApiClient {
    get = apiGetMock;
  },
}));

import {
  buildHookRulesFromAgentHook,
  createAgentSettingsApi,
  mapHookScopeDocumentToAgentHooks,
} from './agentSettingsApi';

beforeEach(() => {
  apiGetMock.mockReset();
});

describe('agentSettingsApi hook mapping', () => {
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

  it('preserves extension hook source metadata when loading scope documents', () => {
    const hooks = mapHookScopeDocumentToAgentHooks({
      scope: 'extension',
      hooks: {
        SessionStart: [
          {
            matcher: 'startup|clear|compact',
            extensionName: 'superpowers-zh',
            extensionVersion: '1.1.6',
            hooks: [
              {
                type: 'command',
                command: '"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start',
              },
            ],
          },
        ],
      },
    });

    expect(hooks[0]).toMatchObject({
      scope: 'extension',
      extensionName: 'superpowers-zh',
      extensionVersion: '1.1.6',
    });
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

describe('agentSettingsApi slash command mapping', () => {
  it('preserves Claude plugin slash command source metadata', async () => {
    apiGetMock
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scopes: [
          {
            scope: 'plugin',
            documents: [
              {
                fileName: 'review.md',
                description: 'Review selected code',
                scope: 'plugin',
                size: '120B',
                pluginName: 'quality',
                marketplaceName: 'team-tools',
              },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        workspaceId: 'ws-1',
        scope: 'plugin',
        document: {
          fileName: 'review.md',
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

    expect(apiGetMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands',
      undefined,
    );
    expect(apiGetMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/claude-code/slash-commands/plugin/review.md',
      undefined,
    );
    expect(documents).toEqual([
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
        }),
      }),
    ]);
  });
});
