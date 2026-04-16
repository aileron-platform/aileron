/**
 * WorkspaceProvider 常數定義
 */

import type { WorkspaceState, WorkspaceFeature, LayoutMode, WorkspaceTabScope } from './workspaceState.types';

// 初始狀態
export const initialState: WorkspaceState = {
  currentFeature: 'file-management',
  layoutMode: 'four-column',
  sidebarCollapsed: false,
  sidebarWidth: 240,
  secondColumnCollapsed: false,
  secondColumnWidth: 320,
  rightChatCollapsed: false,
  rightChatWidth: 400,
  chatExpanded: false,
  expandedNavigationItems: ['claude-code'],

  fileManagement: {
    selectedFile: null,
    openTabs: [],
    activeTabId: null,
    modifiedTabs: [],
    originalContents: {},
    mermaidPreviewMode: {},
    markdownPreviewMode: {},
  },

  workspaceTabsCache: {},

  fileTreeState: {
    nodes: [],
    selectedFile: null,
    selectedFiles: new Set<string>(),
    lastSelectedFile: null,
    isLoading: false,
    error: null,
    expandedNodes: new Set<string>(),
    pendingAction: null,
    draggedNode: null,
    dropTarget: null,
  },

  versionControl: {
    subView: 'changes',
    selectedCommit: null,
    selectedGitContextId: null,
  },

  openspec: {
    subView: 'in-progress',
    selectedPath: null,
    openTabs: [],
    activeTabId: null,
    modifiedTabs: [],
    originalContents: {},
  },

  workspaceSettings: {
    subView: 'basic',
  },

  containerManagement: {
    subView: 'runtime',
  },

  claudeCodeSettings: {
    subView: 'claude-md',
  },

  agentToolSettings: {
    subView: '',
  },

  preview: {
    subView: 'session-result',
    markdownContent: '',
  },
};

// 根據路由路徑決定當前功能的輔助函數
export const getFeatureFromPath = (pathname: string): WorkspaceFeature => {
  if (pathname.includes('/preview')) return 'preview';
  if (pathname.includes('/version-control')) return 'version-control';
  if (pathname.includes('/openspec')) return 'openspec';
  if (pathname.includes('/workspace-settings')) return 'workspace-settings';
  if (pathname.includes('/container-management')) return 'container-management';
  if (pathname.includes('/workspace-automation')) return 'workspace-automation';
  if (pathname.includes('/claude-code')) return 'claude-code';
  if (pathname.includes('/gemini')) return 'gemini';
  if (pathname.includes('/opencode')) return 'opencode';
  if (pathname.includes('/codex')) return 'codex';
  return 'file-management'; // 預設值
};

export const getTabScopeForFeature = (feature: WorkspaceFeature): WorkspaceTabScope => {
  return feature === 'openspec' ? 'openspec' : 'file-management';
};

// 根據路由路徑決定版本控制子視圖
export const getVersionControlSubView = (pathname: string): 'changes' | 'history' => {
  if (pathname.includes('/history')) return 'history';
  return 'changes'; // 預設值
};

// 根據路由路徑決定 OpenSpec 子視圖
export const getOpenSpecSubView = (
  pathname: string,
): 'in-progress' | 'complete' | 'archived' => {
  if (pathname.includes('/archived')) return 'archived';
  if (pathname.includes('/complete')) return 'complete';
  return 'in-progress'; // 預設值
};

// 根據路由路徑決定工作區設定子視圖
export const getWorkspaceSettingsSubView = (pathname: string): 'basic' | 'reset' => {
  if (pathname.includes('/reset')) return 'reset';
  return 'basic'; // 預設值
};

// 根據路由路徑決定容器管理子視圖
export const getContainerManagementSubView = (pathname: string): 'runtime' | 'firewall' | 'terminal' | 'browser' => {
  if (pathname.includes('/firewall')) return 'firewall';
  if (pathname.includes('/terminal')) return 'terminal';
  if (pathname.includes('/browser')) return 'browser';
  return 'runtime'; // 預設值
};

// 根據路由路徑決定 Claude Code 設定子視圖
export const getClaudeCodeSubView = (pathname: string): WorkspaceState['claudeCodeSettings']['subView'] => {
  if (pathname.includes('/mcp')) return 'mcp';
  if (pathname.includes('/hooks')) return 'hooks';
  if (pathname.includes('/slash-commands')) return 'slash-commands';
  if (pathname.includes('/output-styles')) return 'output-styles';
  if (pathname.includes('/subagents')) return 'subagents';
  if (pathname.includes('/skills')) return 'skills';
  if (pathname.includes('/scripts')) return 'scripts';
  if (pathname.includes('/memory')) return 'memory';
  if (pathname.includes('/claude-code/settings')) return 'settings';
  if (pathname.includes('/claude-code/permissions')) return 'settings';
  return 'claude-md'; // 預設值
};

// 根據路由路徑決定 Agent 工具設定子視圖（gemini/opencode/codex 共用）
export const getAgentToolSubView = (pathname: string): string => {
  if (pathname.includes('/mcp')) return 'mcp';
  if (pathname.includes('/hooks')) return 'hooks';
  if (pathname.includes('/slash-commands')) return 'slash-commands';
  if (pathname.includes('/skills')) return 'skills';
  if (pathname.includes('/gemini-md')) return 'gemini-md';
  if (pathname.includes('/agents-md')) return 'agents-md';
  // 根據 Agent 類型決定預設指令檔案子視圖
  if (pathname.includes('/gemini')) return 'gemini-md';
  return 'agents-md'; // codex / opencode 預設值
};

// 根據路由路徑決定預覽子視圖
export const getPreviewSubView = (pathname: string): WorkspaceState['preview']['subView'] => {
  if (pathname.includes('/web-preview')) return 'web-preview';
  return 'session-result'; // 預設值
};

// 根據功能決定佈局模式
export const getLayoutModeForFeature = (feature: WorkspaceFeature): LayoutMode => {
  return feature === 'file-management' || feature === 'version-control' || feature === 'openspec'
    ? 'four-column'
    : 'three-column';
};
