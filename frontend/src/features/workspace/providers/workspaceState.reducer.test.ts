import { describe, expect, it } from 'vitest';

import { workspaceReducer } from './workspaceState.reducer';
import { initialState } from './workspaceState.constants';

describe('workspaceReducer canvas state', () => {
  it('updates markdown and raw canvas content atomically for session results', () => {
    const nextState = workspaceReducer(initialState, {
      type: 'SET_CANVAS_SESSION_RESULT',
      payload: {
        markdownContent: '# Final answer',
        rawContent: {
          usage: {
            input_tokens: 10,
            output_tokens: 5,
            total_tokens: 15,
          },
        },
      },
    });

    expect(nextState.canvas).toEqual({
      subView: 'session-result',
      markdownContent: '# Final answer',
      rawContent: {
        usage: {
          input_tokens: 10,
          output_tokens: 5,
          total_tokens: 15,
        },
      },
    });
  });
});

describe('workspaceReducer tab reordering', () => {
  it('reorders tabs inside the requested scope without changing active or modified state', () => {
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
      openspec: {
        ...initialState.openspec,
        openTabs: [
          {
            id: '/openspec/changes/demo/tasks.md',
            path: '/openspec/changes/demo/tasks.md',
            name: 'tasks.md',
            content: 'tasks',
          },
        ],
        activeTabId: '/openspec/changes/demo/tasks.md',
      },
    };

    const nextState = workspaceReducer(state, {
      type: 'REORDER_FILE_TABS',
      payload: {
        scope: 'file-management',
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
    expect(nextState.openspec.openTabs.map(tab => tab.id)).toEqual([
      '/openspec/changes/demo/tasks.md',
    ]);
  });
});
