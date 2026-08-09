import { describe, expect, it, vi } from 'vitest';
import { createClaudeHookSource } from './claudeHookSource';

describe('createClaudeHookSource', () => {
  it('lists, saves, moves, and removes Claude hooks through scope documents', async () => {
    const api = {
      listHookScopes: vi.fn().mockResolvedValue({
        scopes: [
          {
            scope: 'project',
            revision: 'project-r1',
            hooks: {
              PreToolUse: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'echo project' }] }],
            },
          },
          { scope: 'user', revision: 'user-r1', hooks: {} },
        ],
      }),
      updateHookScope: vi.fn().mockResolvedValue({}),
      deleteHookScope: vi.fn().mockResolvedValue({}),
    };
    const source = createClaudeHookSource(api, 'http://runtime.test', 'ws-1');

    await expect(source.list()).resolves.toEqual([
      expect.objectContaining({ scope: 'project', eventName: 'PreToolUse' }),
    ]);

    await source.save(
      { id: 'user:SessionStart', scope: 'user', eventName: 'SessionStart', matchers: [{ matcher: 'startup', hooks: [{ type: 'command', command: 'echo user' }] }] },
      { id: 'project:PreToolUse', scope: 'project', eventName: 'PreToolUse', matchers: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'echo project' }] }] },
    );

    expect(api.deleteHookScope).toHaveBeenCalledWith('http://runtime.test', 'ws-1', 'project');
    expect(api.updateHookScope).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'user',
      { SessionStart: [{ matcher: 'startup', hooks: [expect.objectContaining({ command: 'echo user' })] }] },
      'user-r1',
    );

    await source.remove({ id: 'project:PreToolUse', scope: 'project', eventName: 'PreToolUse', matchers: [] });
    expect(api.deleteHookScope).toHaveBeenLastCalledWith('http://runtime.test', 'ws-1', 'project');
  });
});
