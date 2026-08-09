import { describe, expect, it } from 'vitest';

import { workspaceReducer } from './workspaceStateReducer';
import { initialState } from './workspaceStateConstants';
import type { WorkspaceAction } from './workspaceStateTypes';

describe('workspaceReducer dispatch', () => {
  it('returns the same state for an unknown runtime action', () => {
    const unknownAction = { type: 'UNKNOWN_ACTION' } as unknown as WorkspaceAction;

    expect(workspaceReducer(initialState, unknownAction)).toBe(initialState);
  });
});

describe('workspaceReducer companion active tab', () => {
  it('stores the selected companion tab in workspace state', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'terminal',
    });

    expect(nextState.companionActiveTab).toBe('terminal');
  });

  it('sets companion terminal placement', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'SET_COMPANION_TERMINAL_PLACEMENT',
      payload: 'bottom',
    });

    expect(nextState.companionTerminalPlacement).toBe('bottom');
  });

  it('restores persisted companion and navigation preferences', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'RESTORE_LAYOUT_PREFERENCES',
      payload: {
        companionActiveTab: 'terminal',
        companionTerminalPlacement: 'bottom',
        expandedNavigationItems: ['container-management'],
        fileTreeShowHiddenEntries: true,
      },
    });

    expect(nextState.companionActiveTab).toBe('terminal');
    expect(nextState.companionTerminalPlacement).toBe('bottom');
    expect(nextState.expandedNavigationItems).toEqual(['container-management']);
    expect(nextState.fileTreeShowHiddenEntries).toBe(true);
  });
});

describe('workspaceReducer main content expand', () => {
  it('toggles the full-screen main content flag', () => {
    const expanded = workspaceReducer(initialState, { type: 'TOGGLE_MAIN_CONTENT_EXPANDED' });
    expect(expanded.mainContentExpanded).toBe(true);
    const collapsed = workspaceReducer(expanded, { type: 'TOGGLE_MAIN_CONTENT_EXPANDED' });
    expect(collapsed.mainContentExpanded).toBe(false);
  });

  it('exits full-screen mode when the feature changes', () => {
    const expanded = { ...initialState, mainContentExpanded: true };
    const nextState = workspaceReducer(expanded, {
      type: 'SET_CURRENT_FEATURE',
      payload: 'version-control',
    });
    expect(nextState.mainContentExpanded).toBe(false);
  });
});

describe('workspaceReducer tab reordering', () => {
  it('reorders tabs without changing active or modified state', () => {
    const state = {
      ...initialState,
      fileManagement: {
        ...initialState.fileManagement,
        openTabs: [
          { id: '/src/a.ts', path: '/src/a.ts', name: 'a.ts', content: 'A' },
          { id: '/src/b.ts', path: '/src/b.ts', name: 'b.ts', content: 'B' },
          { id: '/src/c.ts', path: '/src/c.ts', name: 'c.ts', content: 'C' },
        ],
        activeTabId: '/src/b.ts',
        modifiedTabs: ['/src/b.ts'],
        originalContents: {
          '/src/a.ts': 'A',
          '/src/b.ts': 'B0',
          '/src/c.ts': 'C',
        },
      },
    };

    const nextState = workspaceReducer(state, {
      type: 'REORDER_FILE_TABS',
      payload: {
        tabIds: ['/src/c.ts', '/src/a.ts', '/src/b.ts'],
      },
    });

    expect(nextState.fileManagement.openTabs.map(tab => tab.id)).toEqual([
      '/src/c.ts',
      '/src/a.ts',
      '/src/b.ts',
    ]);
    expect(nextState.fileManagement.activeTabId).toBe('/src/b.ts');
    expect(nextState.fileManagement.modifiedTabs).toEqual(['/src/b.ts']);
    expect(nextState.fileManagement.originalContents).toEqual({
      '/src/a.ts': 'A',
      '/src/b.ts': 'B0',
      '/src/c.ts': 'C',
    });
  });
});
