import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearAllWorkspaceLayoutPreferences,
  clearWorkspaceLayoutPreferences,
  getDefaultWorkspaceLayoutPreferences,
  loadWorkspaceLayoutPreferences,
  saveWorkspaceLayoutPreferences,
} from './workspaceLayoutStorage';

describe('workspaceLayoutStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('stores and loads layout preferences per workspace', () => {
    const workspaceOne = {
      ...getDefaultWorkspaceLayoutPreferences(),
      sidebarCollapsed: true,
      sidebarWidth: 320,
    };
    const workspaceTwo = {
      ...getDefaultWorkspaceLayoutPreferences(),
      rightChatCollapsed: true,
      rightChatWidth: 520,
    };

    saveWorkspaceLayoutPreferences('ws-1', workspaceOne);
    saveWorkspaceLayoutPreferences('ws-2', workspaceTwo);

    expect(loadWorkspaceLayoutPreferences('ws-1')).toEqual(workspaceOne);
    expect(loadWorkspaceLayoutPreferences('ws-2')).toEqual(workspaceTwo);
  });

  it('clears invalid persisted data and returns null', () => {
    localStorage.setItem(
      'workspace_layout_ws-bad',
      JSON.stringify({
        version: '1',
        data: {
          sidebarCollapsed: true,
        },
      })
    );

    expect(loadWorkspaceLayoutPreferences('ws-bad')).toBeNull();
    expect(localStorage.getItem('workspace_layout_ws-bad')).toBeNull();
  });

  it('can clear one workspace or all workspace preferences', () => {
    const defaults = getDefaultWorkspaceLayoutPreferences();

    saveWorkspaceLayoutPreferences('ws-1', defaults);
    saveWorkspaceLayoutPreferences('ws-2', defaults);

    clearWorkspaceLayoutPreferences('ws-1');
    expect(loadWorkspaceLayoutPreferences('ws-1')).toBeNull();
    expect(loadWorkspaceLayoutPreferences('ws-2')).toEqual(defaults);

    clearAllWorkspaceLayoutPreferences();
    expect(loadWorkspaceLayoutPreferences('ws-2')).toBeNull();
  });
});
