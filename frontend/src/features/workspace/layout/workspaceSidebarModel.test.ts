import { describe, expect, it } from 'vitest';
import type { WorkspaceState } from '../providers/workspaceStateTypes';
import {
  buildWorkspaceNavigationPath,
  isWorkspaceNavigationItemActive,
  isWorkspaceSubItemActive,
} from './workspaceSidebarModel';
import {
  MAIN_NAVIGATION_ITEMS,
  type NavigationConfig,
} from './workspaceNavigationModel';

const createState = (overrides: Partial<WorkspaceState> = {}): WorkspaceState => ({
  currentFeature: 'file-management',
  chatExpanded: false,
  fileManagementEditorExpanded: false,
  mainContentExpanded: false,
  fileTreeShowHiddenEntries: false,
  expandedNavigationItems: [],
  fileManagement: {
    selectedFile: null,
    openTabs: [],
    activeTabId: null,
    modifiedTabs: [],
    originalContents: {},
    mermaidCanvasMode: {},
    markdownCanvasMode: {},
  },
  workspaceTabsCache: {},
  versionControl: {
    subView: 'changes',
    selectedCommit: null,
    selectedGitContextId: null,
  },
  workspaceSettings: {
    subView: 'basic',
  },
  containerManagement: {
    subView: 'runtime',
  },
  agentToolSettings: {
    subView: 'agents-md',
  },
  ...overrides,
});

describe('workspaceSidebarModel', () => {
  it('resolves active subitems from the matching workspace feature state', () => {
    expect(isWorkspaceSubItemActive(createState({
      currentFeature: 'version-control',
      versionControl: { subView: 'history', selectedCommit: null, selectedGitContextId: null },
    }), 'version-control', 'history')).toBe(true);

    expect(isWorkspaceSubItemActive(createState({
      currentFeature: 'codex',
      agentToolSettings: { subView: 'rules' },
    }), 'codex', 'rules')).toBe(true);

    expect(isWorkspaceSubItemActive(createState({
      currentFeature: 'claude-code',
      agentToolSettings: { subView: 'memory' },
    }), 'claude-code', 'memory')).toBe(true);

  });

  it('does not mark a subitem active when the parent feature is not current', () => {
    expect(isWorkspaceSubItemActive(createState({
      currentFeature: 'version-control',
      containerManagement: { subView: 'terminal' },
    }), 'container-management', 'terminal')).toBe(false);
  });

  it('builds workspace navigation paths for feature routes', () => {
    expect(buildWorkspaceNavigationPath('codex', 'rules', 'ws-1')).toBe('/workspaces/ws-1/codex/rules');
    expect(buildWorkspaceNavigationPath('canvas', undefined, 'ws-1')).toBe('/workspaces/ws-1/canvas');
    expect(buildWorkspaceNavigationPath('browser', undefined, 'ws-1')).toBe('/workspaces/ws-1/browser');
  });

  it('routes file-management navigation to the canonical workspace files route', () => {
    expect(buildWorkspaceNavigationPath('file-management', undefined, 'ws-1')).toBe('/workspaces/ws-1/files');
  });

  it('routes AI Agent subitems to their owned workspace features', () => {
    expect(buildWorkspaceNavigationPath('ai-agent', {
      id: 'ai-chat-home',
      labelKey: 'workspace.navigation.sub.aiAgent.aiChat',
      parentId: 'ai-agent',
      targetFeature: 'ai-chat-home',
    }, 'ws-1')).toBe('/workspaces/ws-1/home');

    expect(buildWorkspaceNavigationPath('ai-agent', {
      id: 'terminal',
      labelKey: 'workspace.navigation.sub.aiAgent.terminal',
      parentId: 'ai-agent',
      targetFeature: 'container-management',
      targetSubView: 'terminal',
    }, 'ws-1')).toBe('/workspaces/ws-1/container-management/terminal');
  });

  it('treats AI Agent terminal as active from the container terminal route', () => {
    const state = createState({
      currentFeature: 'container-management',
      containerManagement: { subView: 'terminal' },
    });

    expect(isWorkspaceSubItemActive(state, 'ai-agent', {
      id: 'terminal',
      labelKey: 'workspace.navigation.sub.aiAgent.terminal',
      parentId: 'ai-agent',
      targetFeature: 'container-management',
      targetSubView: 'terminal',
    })).toBe(true);
  });

  it('treats a navigation parent as active when one child target is active', () => {
    const state = createState({
      currentFeature: 'container-management',
      containerManagement: { subView: 'terminal' },
    });

    expect(isWorkspaceNavigationItemActive(state, {
      id: 'ai-agent',
      labelKey: 'workspace.navigation.main.aiAgent',
      hasSubMenu: true,
      subItems: [{
        id: 'terminal',
        labelKey: 'workspace.navigation.sub.aiAgent.terminal',
        parentId: 'ai-agent',
        targetFeature: 'container-management',
        targetSubView: 'terminal',
      }],
    } as NavigationConfig)).toBe(true);
  });

  it('does not mark Container Management active for the terminal route moved under AI Agent', () => {
    const state = createState({
      currentFeature: 'container-management',
      containerManagement: { subView: 'terminal' },
    });

    expect(isWorkspaceNavigationItemActive(state, {
      id: 'container-management',
      labelKey: 'workspace.navigation.main.containerManagement',
      hasSubMenu: true,
      subItems: [
        {
          id: 'runtime',
          labelKey: 'workspace.navigation.sub.containerManagement.runtime',
          parentId: 'container-management',
        },
        {
          id: 'firewall',
          labelKey: 'workspace.navigation.sub.containerManagement.firewall',
          parentId: 'container-management',
        },
      ],
    } as NavigationConfig)).toBe(false);
  });

  it('marks Canvas and Browser active only for their own top-level routes', () => {
    const canvasItem = MAIN_NAVIGATION_ITEMS.find((item) => item.id === 'canvas');
    const browserItem = MAIN_NAVIGATION_ITEMS.find((item) => item.id === 'browser');

    expect(canvasItem).toMatchObject({ hasSubMenu: false });
    expect(canvasItem?.subItems).toBeUndefined();
    expect(browserItem).toMatchObject({ hasSubMenu: false });
    expect(browserItem?.subItems).toBeUndefined();

    expect(isWorkspaceNavigationItemActive(
      createState({ currentFeature: 'canvas' }),
      canvasItem as NavigationConfig,
    )).toBe(true);
    expect(isWorkspaceNavigationItemActive(
      createState({ currentFeature: 'canvas' }),
      browserItem as NavigationConfig,
    )).toBe(false);
    expect(isWorkspaceNavigationItemActive(
      createState({ currentFeature: 'browser' }),
      browserItem as NavigationConfig,
    )).toBe(true);
  });
});
