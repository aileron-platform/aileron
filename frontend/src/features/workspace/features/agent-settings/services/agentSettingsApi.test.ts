import { describe, expect, it } from 'vitest';
import {
  buildHookRulesFromAgentHook,
  mapHookScopeDocumentToAgentHooks,
} from './agentSettingsApi';

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
