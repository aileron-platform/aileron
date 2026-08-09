import { beforeEach, describe, expect, it } from 'vitest';
import {
  WORKSPACE_SHELL_LAYOUT_DEFAULTS,
  WORKSPACE_SHELL_LAYOUT_LIMITS,
  workspaceShellLayoutStorage,
} from './workspaceShellLayoutStorage';

describe('workspaceShellLayoutStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('has workspace-specific limits, wider than this package default for the companion side width', () => {
    expect(WORKSPACE_SHELL_LAYOUT_LIMITS.navSidebarWidth).toEqual({ min: 240, max: 500 });
    expect(WORKSPACE_SHELL_LAYOUT_LIMITS.secondColumnWidth).toEqual({ min: 270, max: 600 });
    expect(WORKSPACE_SHELL_LAYOUT_LIMITS.companionWidth).toEqual({ min: 408, max: 800 });
    expect(WORKSPACE_SHELL_LAYOUT_LIMITS.companionHeight).toEqual({ min: 160, max: 520 });
  });

  it('has defaults matching today\'s initialState values', () => {
    expect(WORKSPACE_SHELL_LAYOUT_DEFAULTS).toEqual({
      navSidebarCollapsed: false,
      navSidebarWidth: 240,
      secondColumnCollapsed: false,
      secondColumnWidth: 270,
      companionCollapsed: false,
      companionWidth: 408,
      companionHeight: 240,
      companionPlacement: 'side',
    });
  });

  it('round-trips saved preferences under the workspace feature key', () => {
    workspaceShellLayoutStorage.save('ws-1', {
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      navSidebarWidth: 280,
    });

    expect(workspaceShellLayoutStorage.load('ws-1')).toEqual({
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      navSidebarWidth: 280,
    });
    expect(localStorage.getItem('shell_layout_workspace_ws-1')).not.toBeNull();
  });

  it('clamps persisted navigation widths during load without rewriting the stored preferences', () => {
    const persisted = {
      ...WORKSPACE_SHELL_LAYOUT_DEFAULTS,
      navSidebarWidth: 120,
      secondColumnWidth: 160,
    };
    workspaceShellLayoutStorage.save('ws-clamped', persisted);
    const rawStoredPreferences = localStorage.getItem('shell_layout_workspace_ws-clamped');

    expect(workspaceShellLayoutStorage.load('ws-clamped')).toEqual({
      ...persisted,
      navSidebarWidth: 240,
      secondColumnWidth: 270,
    });
    expect(localStorage.getItem('shell_layout_workspace_ws-clamped')).toBe(rawStoredPreferences);
  });
});
