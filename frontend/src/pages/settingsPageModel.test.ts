import { describe, expect, it } from 'vitest';
import {
  cloneDeep,
  getPartialSyncWorkspaceCount,
  hasSuccessfulSyncDetail,
  normalizeCodexSettings,
  normalizeModelSelection,
  normalizeOpenCodeSettings,
} from './settingsPageModel';
import type { UserSettingsCodex } from '@/shared/types/user';

describe('settingsPageModel', () => {
  it('deep clones values without keeping nested references', () => {
    const source = {
      nested: {
        values: ['a', 'b'],
      },
    };

    const cloned = cloneDeep(source);
    cloned.nested.values.push('c');

    expect(source.nested.values).toEqual(['a', 'b']);
    expect(cloned.nested.values).toEqual(['a', 'b', 'c']);
  });

  it('normalizes Codex settings with defaults and current values', () => {
    const current: UserSettingsCodex = {
      authMethod: 'apikey',
      loginStatus: 'connected',
      account: {
        email: 'current@example.com',
        planType: 'pro',
      },
      model: 'gpt-current',
      environmentVariables: [{ key: 'OPENAI_API_KEY', value: 'current-key' }],
      modelSelection: {
        customModels: ['gpt-custom'],
        availableModels: ['gpt-current', 'gpt-custom'],
        allowedModels: ['gpt-current'],
        defaultModel: 'gpt-current',
      },
      authFlow: null,
      lastSyncedAt: '2026-06-01T00:00:00Z',
      lastSyncError: 'previous-error',
    };

    expect(normalizeCodexSettings({ account: null }, current)).toEqual({
      authMethod: 'apikey',
      loginStatus: 'notConnected',
      account: null,
      model: 'gpt-current',
      environmentVariables: [{ key: 'OPENAI_API_KEY', value: 'current-key' }],
      modelSelection: {
        customModels: ['gpt-custom'],
        availableModels: ['gpt-current', 'gpt-custom'],
        allowedModels: ['gpt-current'],
        defaultModel: 'gpt-current',
      },
      authFlow: null,
      lastSyncedAt: '2026-06-01T00:00:00Z',
      lastSyncError: 'previous-error',
    });
  });

  it('does not synthesize Codex model defaults when settings are unavailable', () => {
    expect(normalizeCodexSettings(null)).toEqual({
      authMethod: 'subscription',
      loginStatus: 'notConnected',
      account: null,
      model: '',
      environmentVariables: [],
      modelSelection: {
        customModels: [],
        availableModels: [],
        allowedModels: [],
        defaultModel: '',
      },
      authFlow: null,
      lastSyncedAt: undefined,
      lastSyncError: undefined,
    });
  });

  it('normalizes model selection with a valid default model', () => {
    expect(normalizeModelSelection({
      customModels: ['custom-model'],
      availableModels: ['global-model', 'custom-model'],
      allowedModels: ['custom-model'],
      defaultModel: 'global-model',
    })).toEqual({
      customModels: ['custom-model'],
      availableModels: ['global-model', 'custom-model'],
      allowedModels: ['custom-model'],
      defaultModel: 'custom-model',
    });
  });

  it('does not synthesize OpenCode model defaults when the backend omits model selection', () => {
    expect(normalizeOpenCodeSettings(null)).toEqual({
      model: '',
      environmentVariables: [],
      modelSelection: {
        customModels: [],
        availableModels: [],
        allowedModels: [],
        defaultModel: '',
      },
    });
  });

  it('detects successful sync details only from detail entries', () => {
    expect(hasSuccessfulSyncDetail({
      workspace_id: 'workspace-1',
      workspace_name: 'Workspace 1',
      success: false,
      details: {
        ssh: { success: false, message: 'Skipped' },
        codex: { success: true, message: 'Synced' },
      },
    })).toBe(true);

    expect(hasSuccessfulSyncDetail({
      workspace_id: 'workspace-2',
      workspace_name: 'Workspace 2',
      success: false,
      error: 'Workspace unavailable',
    })).toBe(false);
  });

  it('counts only failed workspaces that have at least one successful detail', () => {
    expect(getPartialSyncWorkspaceCount([
      {
        workspace_id: 'workspace-1',
        workspace_name: 'Workspace 1',
        success: true,
        details: {
          ssh: { success: false, message: 'No SSH keys need to sync' },
          codex: { success: true, message: 'Synced' },
        },
      },
      {
        workspace_id: 'workspace-2',
        workspace_name: 'Workspace 2',
        success: false,
        details: {
          ssh: { success: false, message: 'SSH sync failed' },
          codex: { success: true, message: 'Synced' },
        },
      },
      {
        workspace_id: 'workspace-3',
        workspace_name: 'Workspace 3',
        success: false,
        error: 'Workspace runtime is unavailable',
      },
    ])).toBe(1);
  });
});
