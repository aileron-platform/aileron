import { describe, expect, it } from 'vitest';
import {
  getAgentDocumentActionPolicy,
  getWritableAgentScopes,
  isReadOnlyAgentScope,
  resolveAgentSettingsSelectedScope,
  toCodexFileScope,
} from './agentSettingsScopeModel';
import type { AgentScope } from './model/documents';

describe('agentSettingsScopeModel', () => {
  it('treats plugin scope as a read-only source', () => {
    expect(isReadOnlyAgentScope('plugin')).toBe(true);
    expect(isReadOnlyAgentScope('project')).toBe(false);
    expect(isReadOnlyAgentScope('user')).toBe(false);
    expect(isReadOnlyAgentScope('local')).toBe(false);
  });

  it('filters writable scopes while preserving their display order', () => {
    const scopes: AgentScope[] = ['project', 'plugin', 'user', 'local'];

    expect(getWritableAgentScopes(scopes)).toEqual(['project', 'user', 'local']);
  });

  it('resets an unavailable selected scope back to all', () => {
    expect(resolveAgentSettingsSelectedScope('plugin', ['project', 'user'])).toBe('all');
    expect(resolveAgentSettingsSelectedScope('project', ['project', 'user'])).toBe('project');
    expect(resolveAgentSettingsSelectedScope('all', ['project'])).toBe('all');
  });

  it('maps selected files to Codex file API scopes', () => {
    expect(toCodexFileScope('plugin')).toBe('plugin');
    expect(toCodexFileScope('user')).toBe('user');
    expect(toCodexFileScope('project')).toBe('project');
  });

  it('resolves document action policy from the document scope', () => {
    expect(getAgentDocumentActionPolicy({ scope: 'project' })).toEqual({
      canEdit: true,
      canDelete: true,
      canCopy: true,
      canDownload: true,
      readOnly: false,
    });
    expect(getAgentDocumentActionPolicy({ scope: 'plugin' })).toEqual({
      canEdit: false,
      canDelete: false,
      canCopy: true,
      canDownload: true,
      readOnly: true,
    });
  });
});
