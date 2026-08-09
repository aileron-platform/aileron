import { describe, expect, it } from 'vitest';
import type { HookMatcher } from './hookTypes';
import {
  buildHookDialogSubmitPayload,
  createHookDialogDefaultForm,
  getHookDialogScopeValues,
  hasDuplicateHookDialogEvent,
  hydrateHookDialogForm,
  isHookDialogActionValid,
  sanitizeHookDialogAction,
} from './hookDialogModel';

describe('hookDialogModel', () => {
  it('creates default forms with provider defaults', () => {
    const form = createHookDialogDefaultForm('claude-code', 'SessionStart', 'local', 'sync');

    expect(form).toMatchObject({
      id: '',
      name: 'sync',
      scope: 'local',
      eventName: 'SessionStart',
    });
    expect(form.matchers).toHaveLength(1);
  });

  it('filters available scopes while preserving supported order', () => {
    expect(getHookDialogScopeValues(['plugin', 'local', 'project'])).toEqual(['project', 'local']);
    expect(getHookDialogScopeValues(undefined)).toEqual(['project', 'user', 'local']);
  });

  it('hydrates edit forms according to provider field support', () => {
    const matchers: HookMatcher[] = [{
      matcher: 'Write',
      sequential: true,
      hooks: [{
        type: 'command',
        command: ' echo write ',
        timeout: 60000,
        name: 'security',
        description: 'Check commands',
        statusMessage: 'Checking',
      }],
    }];

    expect(hydrateHookDialogForm({
      id: 'hook-1',
      scope: 'project',
      eventName: 'PreToolUse',
      matchers,
    }, 'codex').matchers[0].hooks[0]).not.toHaveProperty('name', 'security');

    expect(hydrateHookDialogForm({
      id: 'hook-1',
      scope: 'project',
      eventName: 'SessionStart',
      matchers,
    }, 'claude-code').matchers[0].hooks[0]).toMatchObject({
      name: 'security',
      description: 'Check commands',
      statusMessage: 'Checking',
    });
  });

  it('detects duplicate event and scope only during creation', () => {
    const existingHooks = [{
      id: 'project:SessionStart',
      scope: 'project' as const,
      eventName: 'SessionStart',
      matchers: [],
    }];

    expect(hasDuplicateHookDialogEvent(existingHooks, 'SessionStart', 'project', false)).toBe(true);
    expect(hasDuplicateHookDialogEvent(existingHooks, 'SessionStart', 'project', true)).toBe(false);
    expect(hasDuplicateHookDialogEvent(existingHooks, 'Stop', 'project', false)).toBe(false);
  });

  it('validates action types by required fields', () => {
    expect(isHookDialogActionValid({ type: 'http', url: 'https://example.test', timeout: 1 })).toBe(true);
    expect(isHookDialogActionValid({ type: 'mcp_tool', server: 'fs', tool: 'read', timeout: 1 })).toBe(true);
    expect(isHookDialogActionValid({ type: 'prompt', prompt: 'Review this', timeout: 1 })).toBe(true);
    expect(isHookDialogActionValid({ type: 'command', command: '   ', timeout: 1 })).toBe(false);
  });

  it('sanitizes command actions according to provider support', () => {
    expect(sanitizeHookDialogAction({
      type: 'command',
      command: ' echo write ',
      timeout: 60000,
      name: 'security',
      description: 'Check commands',
      statusMessage: 'Checking',
      async: true,
      asyncRewake: true,
    }, 'codex')).toMatchObject({
      type: 'command',
      command: 'echo write',
      timeout: 60000,
    });

    expect(sanitizeHookDialogAction({
      type: 'command',
      command: ' echo write ',
      timeout: 600,
      statusMessage: 'Checking',
      shell: 'bash',
      async: true,
      asyncRewake: false,
    }, 'claude-code')).toMatchObject({
      type: 'command',
      command: 'echo write',
      statusMessage: 'Checking',
      shell: 'bash',
      async: true,
      asyncRewake: false,
    });
  });

  it('builds submit payload without invalid actions or empty matchers', () => {
    const payload = buildHookDialogSubmitPayload({
      id: 'hook-1',
      name: '  Deploy hook  ',
      scope: 'project',
      eventName: 'SessionStart',
      matchers: [
        {
          matcher: '  ',
          hooks: [{ type: 'command', command: ' echo ok ', timeout: 600, shell: 'bash' }],
        },
        {
          matcher: 'Write',
          hooks: [{ type: 'command', command: ' ', timeout: 600 }],
        },
      ],
    }, 'claude-code', true);

    expect(payload).toMatchObject({
      id: 'hook-1',
      name: 'Deploy hook',
      scope: 'project',
      eventName: 'SessionStart',
      matchers: [{
        matcher: '*',
        hooks: [expect.objectContaining({ command: 'echo ok' })],
      }],
    });
  });
});
