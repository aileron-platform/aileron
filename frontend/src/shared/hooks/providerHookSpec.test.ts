import { describe, expect, it } from 'vitest';

import {
  EVENTS_WITH_CONDITION_SUPPORT,
  HOOK_DEFAULTS,
  HOOK_EVENTS,
  HOOK_EVENT_MATCHER_HINTS,
  HOOK_TIMEOUT_DEFAULTS,
  HOOK_TYPES,
  HOOK_TYPE_FIELDS,
  HOOK_FIELD_SUPPORT,
  getHookEventI18nKey,
  isConditionSupportedForEvent,
  migrateActionToType,
  createEmptyExecution,
  createEmptyHookValue,
  createEmptyMatcher,
  isValidEventForProvider,
} from './providerHookSpec';

describe('providerHookSpec', () => {
  it('defines provider hook event order', () => {
    expect(HOOK_EVENTS['claude-code']).toEqual([
      'SessionStart',
      'Setup',
      'SessionEnd',
      'UserPromptSubmit',
      'UserPromptExpansion',
      'PreToolUse',
      'PostToolUse',
      'PostToolUseFailure',
      'PostToolBatch',
      'PermissionRequest',
      'PermissionDenied',
      'Stop',
      'StopFailure',
      'SubagentStart',
      'SubagentStop',
      'TeammateIdle',
      'TaskCreated',
      'TaskCompleted',
      'ConfigChange',
      'CwdChanged',
      'FileChanged',
      'InstructionsLoaded',
      'PreCompact',
      'PostCompact',
      'WorktreeCreate',
      'WorktreeRemove',
      'Notification',
      'Elicitation',
      'ElicitationResult',
    ]);
    expect(HOOK_EVENTS.gemini).toEqual([
      'BeforeTool',
      'AfterTool',
      'BeforeAgent',
      'AfterAgent',
      'BeforeModel',
      'AfterModel',
      'BeforeToolSelection',
      'SessionStart',
      'SessionEnd',
      'PreCompress',
      'Notification',
    ]);
    expect(HOOK_EVENTS.codex).toEqual([
      'SessionStart',
      'PreToolUse',
      'PostToolUse',
      'PermissionRequest',
      'UserPromptSubmit',
      'Stop',
    ]);
  });

  it('defines provider field support and defaults', () => {
    expect(HOOK_FIELD_SUPPORT['claude-code']).toEqual({
      sequential: false,
      actionMetadata: false,
      condition: true,
      async: true,
      shell: true,
      statusMessage: true,
      once: false,
    });
    expect(HOOK_FIELD_SUPPORT.gemini).toEqual({
      sequential: true,
      actionMetadata: true,
      condition: false,
      async: false,
      shell: false,
      statusMessage: false,
      once: false,
    });
    expect(HOOK_FIELD_SUPPORT.codex).toEqual({
      sequential: false,
      actionMetadata: false,
      condition: false,
      async: false,
      shell: false,
      statusMessage: true,
      once: false,
    });
    expect(HOOK_DEFAULTS).toEqual({
      'claude-code': { timeout: 600, timeoutUnit: 's', timeoutMax: 3600, shell: 'bash' },
      gemini: { timeout: 60000, timeoutUnit: 'ms', timeoutMax: 600000 },
      codex: { timeout: 60, timeoutUnit: 's', timeoutMax: 3600 },
    });
  });

  it('creates provider-specific empty values', () => {
    expect(isValidEventForProvider('gemini', 'AfterModel')).toBe(true);
    expect(isValidEventForProvider('codex', 'AfterModel')).toBe(false);
    expect(createEmptyExecution('claude-code')).toEqual({
      type: 'command',
      command: '',
      timeout: 600,
      shell: 'bash',
    });
    expect(createEmptyExecution('gemini')).toEqual({
      type: 'command',
      command: '',
      timeout: 60000,
    });
    expect(createEmptyMatcher('gemini')).toEqual({
      matcher: '',
      sequential: true,
      hooks: [{ type: 'command', command: '', timeout: 60000 }],
    });
    expect(createEmptyHookValue('codex')).toEqual({
      name: '',
      event: 'SessionStart',
      matchers: [{ matcher: '', hooks: [{ type: 'command', command: '', timeout: 60 }] }],
    });
    expect(HOOK_TYPES['claude-code']).toEqual(['command', 'http', 'mcp_tool', 'prompt', 'agent']);
    expect(HOOK_TYPE_FIELDS.http.url).toBe(true);
    expect(HOOK_TYPE_FIELDS.command.command).toBe(true);
    expect(HOOK_TIMEOUT_DEFAULTS['claude-code'].http).toEqual({ default: 30, max: 600, unit: 's' });
    expect(migrateActionToType({ type: 'command', command: 'npm test', timeout: 600, if: 'env.CI', statusMessage: 'Running' }, 'http', 'claude-code')).toEqual({
      type: 'http',
      url: '',
      headers: {},
      allowedEnvVars: [],
      timeout: 30,
      name: undefined,
      description: undefined,
      if: 'env.CI',
      statusMessage: 'Running',
      once: undefined,
    });
  });

  it('scopes the if field to tool events only', () => {
    expect(EVENTS_WITH_CONDITION_SUPPORT).toEqual(new Set([
      'PreToolUse',
      'PostToolUse',
      'PostToolUseFailure',
      'PermissionRequest',
      'PermissionDenied',
    ]));
    expect(isConditionSupportedForEvent('PreToolUse')).toBe(true);
    expect(isConditionSupportedForEvent('PostToolUseFailure')).toBe(true);
    expect(isConditionSupportedForEvent('PermissionDenied')).toBe(true);
    expect(isConditionSupportedForEvent('SessionStart')).toBe(false);
    expect(isConditionSupportedForEvent('Stop')).toBe(false);
    expect(isConditionSupportedForEvent('Notification')).toBe(false);
  });

  it('marks all 9 matcherless events as not supporting matcher', () => {
    const matcherless = ['UserPromptSubmit', 'PostToolBatch', 'Stop', 'TeammateIdle', 'TaskCreated', 'TaskCompleted', 'WorktreeCreate', 'WorktreeRemove', 'CwdChanged'];
    for (const event of matcherless) {
      expect(HOOK_EVENT_MATCHER_HINTS[event]).toMatchObject({ supportsMatcher: false });
    }
  });

  it('keeps tool events as supporting matcher', () => {
    for (const event of ['PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'PermissionRequest', 'PermissionDenied']) {
      expect(HOOK_EVENT_MATCHER_HINTS[event].supportsMatcher).toBe(true);
    }
  });

  it('builds shared hook event i18n keys', () => {
    expect(getHookEventI18nKey('PreToolUse', 'label')).toBe('common.hookEvents.PreToolUse.label');
    expect(getHookEventI18nKey('Stop', 'description')).toBe('common.hookEvents.Stop.description');
  });
});
