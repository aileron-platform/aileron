import { describe, expect, it, vi } from 'vitest';
import { createCodexHookSource } from './codexHookSource';

describe('createCodexHookSource', () => {
  it('shares one scopes request between the list and feature state', async () => {
    const api = {
      listCodexHooksScopes: vi.fn().mockResolvedValue({
        workspaceId: 'ws-1',
        scopes: [{
          scope: 'project',
          source: 'hooks_json',
          path: '.codex/hooks.json',
          content: '',
          exists: false,
          revision: 'project-r1',
          featureEnabled: true,
          inlineHooks: [],
          entries: [],
          eventMetadata: [],
        }],
      }),
      upsertCodexHookEntry: vi.fn(),
      deleteCodexHookEntry: vi.fn(),
      enableCodexHooks: vi.fn(),
      disableCodexHooks: vi.fn(),
      updateCodexPluginHookTrust: vi.fn(),
    };
    const source = createCodexHookSource(api, 'http://runtime.test', 'ws-1');

    await Promise.all([
      source.list(),
      source.featureEnablement!.isEnabled(),
    ]);

    expect(api.listCodexHooksScopes).toHaveBeenCalledTimes(1);
  });

  it('lists Codex entries and writes through structured endpoints', async () => {
    const api = {
      listCodexHooksScopes: vi.fn().mockResolvedValue({
        scopes: [
          {
            scope: 'project',
            source: 'hooks_json',
            path: '.codex/hooks.json',
            content: '',
            exists: false,
            revision: 'project-r1',
            featureEnabled: false,
            inlineHooks: [],
            entries: [
              {
                id: 'project:PreToolUse:0',
                event: 'PreToolUse',
                index: 0,
                matcher: 'Bash',
                actions: [{ type: 'command', command: 'echo project', statusMessage: 'Checking' }],
                source: 'hooks_json',
                layer: 'project',
                readOnly: false,
                raw: { matcher: 'Bash', hooks: [{ type: 'command', command: 'echo project' }] },
              },
            ],
            eventMetadata: [],
          },
          {
            scope: 'user',
            source: 'hooks_json',
            path: '~/.codex/hooks.json',
            content: '',
            exists: false,
            revision: 'user-r1',
            featureEnabled: false,
            inlineHooks: [],
            entries: [],
            eventMetadata: [],
          },
          {
            scope: 'plugin',
            source: 'plugin',
            path: '',
            content: '',
            exists: false,
            revision: 'plugin-r1',
            featureEnabled: false,
            inlineHooks: [],
            entries: [
              {
                id: 'plugin:demo:SessionStart:0',
                event: 'SessionStart',
                index: 0,
                matcher: '*',
                actions: [{ type: 'command', command: 'echo plugin' }],
                source: 'plugin',
                layer: null,
                readOnly: true,
                pluginId: 'demo@local',
                pluginName: 'Demo',
                marketplaceName: 'local',
                trustState: 'untrusted',
                trusted: false,
                effective: false,
                trustRevision: 'trust-r1',
                generation: 7,
                raw: { matcher: '*', hooks: [{ type: 'command', command: 'echo plugin' }] },
              },
            ],
            eventMetadata: [],
          },
        ],
        workspaceId: 'ws-1',
      }),
      upsertCodexHookEntry: vi.fn().mockResolvedValue({}),
      deleteCodexHookEntry: vi.fn().mockResolvedValue({}),
      enableCodexHooks: vi.fn().mockResolvedValue({}),
      disableCodexHooks: vi.fn().mockResolvedValue({}),
      updateCodexPluginHookTrust: vi.fn().mockResolvedValue({}),
    };
    const source = createCodexHookSource(api, 'http://runtime.test', 'ws-1');

    const hooks = await source.list();
    expect(hooks).toEqual(expect.arrayContaining([
      expect.objectContaining({ eventName: 'PreToolUse', scope: 'project' }),
      expect.objectContaining({
        eventName: 'SessionStart',
        scope: 'plugin',
        pluginId: 'demo@local',
        trustRevision: 'trust-r1',
      }),
    ]));
    await source.save(hooks[0]);
    await source.remove(hooks[0]);
    await source.pluginTrust!.update(
      hooks.find((hook) => hook.scope === 'plugin')!,
      true,
    );
    await expect(source.pluginTrust!.update({
      ...hooks[0],
      scope: 'plugin',
      pluginId: undefined,
      trustRevision: undefined,
    }, true)).rejects.toMatchObject({
      errorCode: 'marketplace.settings.plugin_hook_trust_invalid',
    });
    await expect(source.featureEnablement!.isEnabled()).resolves.toBe(false);
    await source.featureEnablement!.enable();

    expect(api.upsertCodexHookEntry).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      expect.objectContaining({ event: 'PreToolUse', source: 'hooks_json' }),
      'project-r1',
      null,
    );
    expect(api.deleteCodexHookEntry).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
      expect.objectContaining({ event: 'PreToolUse', source: 'hooks_json' }),
      'project-r1',
    );
    expect(api.enableCodexHooks).toHaveBeenCalledWith('http://runtime.test', 'ws-1', 'project');
    expect(api.updateCodexPluginHookTrust).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'demo@local',
      true,
      'trust-r1',
    );
  });
});
