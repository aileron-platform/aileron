import { describe, expect, it } from 'vitest';
import type { CodexHookEntry } from '../../api/agentSettingsApi';
import {
  mapCodexHookEntriesToItems,
  toCodexHookEntry,
  toHookDialogData,
} from './codexHooksPageModel';

const projectHookEntry: CodexHookEntry = {
  id: 'project:PreToolUse:0',
  event: 'PreToolUse',
  index: 0,
  matcher: 'Bash',
  actions: [{
    type: 'command',
    command: 'echo project',
    timeout: 600,
    statusMessage: 'Checking project',
    raw: {
      type: 'command',
      command: 'echo project',
      timeout: 600,
      statusMessage: 'Checking project',
      unknownField: true,
    },
  }],
  action: {
    type: 'command',
    command: 'echo project',
    timeout: 600,
    statusMessage: 'Checking project',
    raw: {
      type: 'command',
      command: 'echo project',
      timeout: 600,
      statusMessage: 'Checking project',
      unknownField: true,
    },
  },
  source: 'hooks_json',
  layer: 'project',
  readOnly: false,
  raw: { matcher: 'Bash', hooks: [{ type: 'command', command: 'echo project' }] },
};

const pluginHookEntry: CodexHookEntry = {
  id: 'plugin:demo@local:SessionStart:0',
  event: 'SessionStart',
  index: 0,
  matcher: 'startup',
  actions: [{ type: 'command', command: 'echo plugin', statusMessage: 'Loading plugin' }],
  action: { type: 'command', command: 'echo plugin', statusMessage: 'Loading plugin' },
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
  raw: { matcher: 'startup', hooks: [{ type: 'command', command: 'echo plugin' }] },
};

describe('codexHooksPageModel', () => {
  it('groups Codex hook entries by source, layer, event, plugin, and source path', () => {
    const items = mapCodexHookEntriesToItems([
      projectHookEntry,
      { ...projectHookEntry, id: 'project:PreToolUse:1', index: 1, matcher: 'Read' },
      pluginHookEntry,
    ]);

    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({
      scope: 'project',
      layer: 'project',
      eventName: 'PreToolUse',
      readOnly: false,
    });
    expect(items[0].matchers).toHaveLength(2);
    expect(items[1]).toMatchObject({
      scope: 'plugin',
      layer: null,
      eventName: 'SessionStart',
      readOnly: true,
      pluginName: 'Demo',
      pluginId: 'demo@local',
      trustState: 'untrusted',
      trusted: false,
      effective: false,
      trustRevision: 'trust-r1',
      generation: 7,
    });
    expect(toHookDialogData(items[1])).toMatchObject({
      pluginId: 'demo@local',
      trustState: 'untrusted',
      trusted: false,
      effective: false,
      trustRevision: 'trust-r1',
      generation: 7,
    });
  });

  it('maps editable Codex hook items to structured entry requests', () => {
    const item = mapCodexHookEntriesToItems([projectHookEntry])[0];
    const workspaceHook = toHookDialogData(item);

    expect(workspaceHook).toMatchObject({
      scope: 'project',
      eventName: 'PreToolUse',
      source: 'hooks_json',
      readOnly: false,
    });
    const editedHook = {
      ...workspaceHook!,
      matchers: [{
        ...workspaceHook!.matchers[0],
        hooks: [{
          ...workspaceHook!.matchers[0].hooks[0],
          command: 'echo updated',
          statusMessage: 'Updated',
          timeout: 30,
        }],
      }],
    };
    expect(toCodexHookEntry(editedHook)).toMatchObject({
      id: item.id,
      event: 'PreToolUse',
      matcher: 'Bash',
      source: 'hooks_json',
      layer: 'project',
      readOnly: false,
      actions: [
        expect.objectContaining({
          type: 'command',
          command: 'echo updated',
          statusMessage: 'Updated',
          timeout: 30,
          unknownField: true,
        }),
      ],
    });
  });
});
