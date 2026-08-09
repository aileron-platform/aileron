import { beforeEach, describe, expect, it } from 'vitest';
import {
  loadWorkspaceLayoutPreferences,
  saveWorkspaceLayoutPreferences,
} from './workspaceLayoutStorage';
import type { WorkspaceLayoutPreferences } from '../providers/workspaceStateTypes';

const createLayoutPreferences = (
  overrides: Partial<WorkspaceLayoutPreferences> = {},
): WorkspaceLayoutPreferences => ({
  companionActiveTab: 'ai-chat',
  companionTerminalPlacement: 'side',
  expandedNavigationItems: ['claude-code'],
  fileTreeShowHiddenEntries: false,
  ...overrides,
});

describe('workspaceLayoutStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and loads layout preferences per workspace', () => {
    const workspaceOne = createLayoutPreferences({
      companionActiveTab: 'terminal' as const,
      fileTreeShowHiddenEntries: true,
    });
    const workspaceTwo = createLayoutPreferences({
      companionTerminalPlacement: 'bottom' as const,
      expandedNavigationItems: ['container-management'],
    });

    saveWorkspaceLayoutPreferences('ws-1', workspaceOne);
    saveWorkspaceLayoutPreferences('ws-2', workspaceTwo);

    expect(loadWorkspaceLayoutPreferences('ws-1')).toEqual(workspaceOne);
    expect(loadWorkspaceLayoutPreferences('ws-2')).toEqual(workspaceTwo);
  });

  it('clears incomplete cached data instead of backfilling legacy fields', () => {
    localStorage.setItem(
      'workspace_layout_ws-legacy',
      JSON.stringify({
        version: '1',
        data: {
          expandedNavigationItems: ['claude-code'],
        },
      })
    );

    expect(loadWorkspaceLayoutPreferences('ws-legacy')).toBeNull();
    expect(localStorage.getItem('workspace_layout_ws-legacy')).toBeNull();
  });

  it('clears invalid persisted data and returns null', () => {
    localStorage.setItem(
      'workspace_layout_ws-bad',
      JSON.stringify({
        version: '1',
        data: {
          expandedNavigationItems: 'broken',
        },
      })
    );

    expect(loadWorkspaceLayoutPreferences('ws-bad')).toBeNull();
    expect(localStorage.getItem('workspace_layout_ws-bad')).toBeNull();
  });

  it('clears persisted data with an unsupported version', () => {
    localStorage.setItem('workspace_layout_ws-old-version', JSON.stringify({
      version: '0',
      data: createLayoutPreferences(),
    }));

    expect(loadWorkspaceLayoutPreferences('ws-old-version')).toBeNull();
    expect(localStorage.getItem('workspace_layout_ws-old-version')).toBeNull();
  });

  it('clears malformed JSON through the load failure path without affecting other workspaces', () => {
    const retainedPreferences = createLayoutPreferences({
      companionTerminalPlacement: 'bottom',
    });
    localStorage.setItem('workspace_layout_ws-1', '{invalid-json');
    saveWorkspaceLayoutPreferences('ws-2', retainedPreferences);

    expect(loadWorkspaceLayoutPreferences('ws-1')).toBeNull();
    expect(localStorage.getItem('workspace_layout_ws-1')).toBeNull();
    expect(loadWorkspaceLayoutPreferences('ws-2')).toEqual(retainedPreferences);
  });
});
