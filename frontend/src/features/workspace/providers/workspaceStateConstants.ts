/**
 */

import type { WorkspaceState, WorkspaceFeature } from './workspaceStateTypes';

export const WORKSPACE_LAYOUT_WIDTH_LIMITS = {
  mainContent: {
    min: 320,
  },
} as const;

export const WORKSPACE_LAYOUT_HEIGHT_LIMITS = {
  mainContent: {
    preferredMin: 240,
  },
} as const;

export const initialState: WorkspaceState = {
  currentFeature: 'file-management',
  companionActiveTab: 'ai-chat',
  companionTerminalPlacement: 'side',
  chatExpanded: false,
  fileManagementEditorExpanded: false,
  mainContentExpanded: false,
  fileTreeShowHiddenEntries: false,
  expandedNavigationItems: ['claude-code'],

  fileManagement: {
    selectedFile: null,
    openTabs: [],
    activeTabId: null,
    modifiedTabs: [],
    originalContents: {},
    revisions: {},
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
    subView: '',
  },
};

const getWorkspaceRouteSegments = (pathname: string): string[] => {
  const pathOnly = pathname.split(/[?#]/, 1)[0];
  const segments = pathOnly.split('/').filter(Boolean);

  if (segments[0] !== 'workspaces' || !segments[1]) {
    return [];
  }

  return segments.slice(2);
};

const getWorkspaceFeatureSubView = (
  pathname: string,
  expectedFeature: string,
): string | undefined => {
  const [feature, subView] = getWorkspaceRouteSegments(pathname);
  return feature === expectedFeature ? subView : undefined;
};

export const getFeatureFromPath = (pathname: string): WorkspaceFeature => {
  const segments = getWorkspaceRouteSegments(pathname);
  const [feature] = segments;

  switch (feature) {
    case 'home':
      return 'ai-chat-home';
    case 'version-control':
    case 'workspace-settings':
    case 'container-management':
    case 'workspace-automation':
    case 'claude-code':
    case 'opencode':
    case 'codex':
      return feature;
    case 'canvas':
    case 'browser':
      return segments.length === 1 ? feature : 'file-management';
    case 'files':
    default:
      return 'file-management';
  }
};

export const getVersionControlSubView = (pathname: string): 'changes' | 'history' => {
  return getWorkspaceFeatureSubView(pathname, 'version-control') === 'history'
    ? 'history'
    : 'changes';
};

export const getWorkspaceSettingsSubView = (
  pathname: string,
): 'basic' | 'access' | 'knowledge-bases' | 'reset' => {
  const subView = getWorkspaceFeatureSubView(pathname, 'workspace-settings');
  if (subView === 'access') return 'access';
  if (subView === 'knowledge-bases') return 'knowledge-bases';
  if (subView === 'reset') return 'reset';
  return 'basic';
};

export const getContainerManagementSubView = (pathname: string): 'runtime' | 'firewall' | 'terminal' => {
  const subView = getWorkspaceFeatureSubView(pathname, 'container-management');
  if (subView === 'firewall') return 'firewall';
  if (subView === 'terminal') return 'terminal';
  return 'runtime';
};

export const getAgentToolSubView = (pathname: string): string => {
  const [agent, subView] = getWorkspaceRouteSegments(pathname);

  if (agent === 'claude-code' || agent === 'opencode' || agent === 'codex') {
    if (agent === 'claude-code') {
      if (subView === 'permissions') return 'settings';
      const allowedClaudeSubViews = new Set([
        'claude-md',
        'mcp',
        'hooks',
        'slash-commands',
        'output-styles',
        'subagents',
        'skills',
        'memory',
        'plugins',
        'settings',
      ]);
      return subView && allowedClaudeSubViews.has(subView) ? subView : 'claude-md';
    }
    if (agent === 'codex') {
      const allowedCodexSubViews = new Set([
        'agents-md',
        'skills',
        'subagents',
        'prompts',
        'mcp',
        'hooks',
        'rules',
        'plugins',
        'settings',
      ]);
      return subView && allowedCodexSubViews.has(subView) ? subView : 'agents-md';
    }
    if (subView) {
      return subView;
    }
    return 'agents-md';
  }

  return 'agents-md';
};
