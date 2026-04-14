/**
 * WorkspaceProvider 型別定義
 */

import type { FileNode, FileTreeState, FileTreeActions } from '../features/file-management/types';
import type React from 'react';

export type WorkspaceTabScope = 'file-management' | 'openspec';
export interface WorkspaceTab {
  id: string;
  name: string;
  path: string;
  content: string;
}

export interface WorkspaceTabState {
  openTabs: WorkspaceTab[];
  activeTabId: string | null;
  modifiedTabs: string[];
  originalContents: Record<string, string>;
}

// Browser 容器狀態類型
export type BrowserContainerStatus = 'stopped' | 'starting' | 'running' | 'error' | 'restarting';

// 工作區功能類型
export type WorkspaceFeature =
  | 'file-management'
  | 'version-control'
  | 'openspec'
  | 'workspace-settings'
  | 'container-management'
  | 'workspace-automation'
  | 'claude-code'
  | 'gemini'
  | 'opencode'
  | 'codex'
  | 'preview';

// 佈局模式類型
export type LayoutMode = 'three-column' | 'four-column';

// 工作區狀態
export interface WorkspaceState {
  currentFeature: WorkspaceFeature;
  layoutMode: LayoutMode;
  sidebarCollapsed: boolean;
  sidebarWidth: number;
  secondColumnCollapsed: boolean;
  secondColumnWidth: number;
  rightChatCollapsed: boolean;
  rightChatWidth: number;
  chatExpanded: boolean;

  // 導航選單展開狀態
  expandedNavigationItems: string[];

  // 各功能的子狀態
  fileManagement: {
    selectedFile: string | null;
    openTabs: WorkspaceTab[];
    activeTabId: string | null;
    modifiedTabs: string[]; // 修改過的標籤頁ID
    originalContents: Record<string, string>; // 原始檔案內容
    mermaidPreviewMode: Record<string, boolean>; // Mermaid 預覽模式狀態
    markdownPreviewMode: Record<string, boolean>; // Markdown 預覽模式狀態
  };

  // Workspace 層級的 tab 狀態持久化
  workspaceTabsCache: Record<string, Partial<Record<WorkspaceTabScope, WorkspaceTabState>>>;

  // 檔案樹狀態
  fileTreeState: FileTreeState;

  versionControl: {
    subView: 'changes' | 'history';
    selectedCommit: string | null;
  };

  openspec: {
    subView: 'in-progress' | 'complete' | 'archived';
    selectedPath: string | null;
    openTabs: WorkspaceTab[];
    activeTabId: string | null;
    modifiedTabs: string[];
    originalContents: Record<string, string>;
  };

  workspaceSettings: {
    subView: 'basic' | 'reset';
  };

  containerManagement: {
    subView: 'runtime' | 'firewall' | 'terminal' | 'browser';
  };

  claudeCodeSettings: {
    subView: 'claude-md' | 'mcp' | 'hooks' | 'slash-commands' | 'output-styles' | 'subagents' | 'skills' | 'scripts' | 'memory' | 'settings';
  };

  agentToolSettings: {
    subView: string;
  };

  preview: {
    subView: 'session-result' | 'web-preview';
    markdownContent: string;
    rawContent?: any; // 預覽用的 usage context（raw SDK / task usage / metadata）
  };
}

// Action 類型定義
export type WorkspaceAction =
  | { type: 'SET_CURRENT_FEATURE'; payload: WorkspaceFeature }
  | { type: 'SET_LAYOUT_MODE'; payload: LayoutMode }
  | { type: 'TOGGLE_SIDEBAR' }
  | { type: 'TOGGLE_SECOND_COLUMN' }
  | { type: 'TOGGLE_RIGHT_CHAT' }
  | { type: 'TOGGLE_CHAT_EXPANDED' }
  | { type: 'SET_SIDEBAR_COLLAPSED'; payload: boolean }
  | { type: 'SET_SECOND_COLUMN_COLLAPSED'; payload: boolean }
  | { type: 'SET_RIGHT_CHAT_COLLAPSED'; payload: boolean }
  | { type: 'SET_CHAT_EXPANDED'; payload: boolean }
  | { type: 'TOGGLE_NAVIGATION_ITEM'; payload: string }
  | { type: 'ENSURE_NAVIGATION_ITEM_EXPANDED'; payload: string }
  | { type: 'SET_SIDEBAR_WIDTH'; payload: number }
  | { type: 'SET_SECOND_COLUMN_WIDTH'; payload: number }
  | { type: 'SET_RIGHT_CHAT_WIDTH'; payload: number }
  | { type: 'SET_VERSION_CONTROL_SUB_VIEW'; payload: 'changes' | 'history' }
  | { type: 'SET_OPENSPEC_SUB_VIEW'; payload: WorkspaceState['openspec']['subView'] }
  | { type: 'SET_OPENSPEC_SELECTED_PATH'; payload: string | null }
  | { type: 'SET_WORKSPACE_SETTINGS_SUB_VIEW'; payload: 'basic' | 'reset' }
  | { type: 'SET_CONTAINER_MANAGEMENT_SUB_VIEW'; payload: 'runtime' | 'firewall' | 'terminal' | 'browser' }
  | { type: 'SET_CLAUDE_CODE_SUB_VIEW'; payload: WorkspaceState['claudeCodeSettings']['subView'] }
  | { type: 'SET_AGENT_TOOL_SUB_VIEW'; payload: string }
  | { type: 'SET_PREVIEW_SUB_VIEW'; payload: WorkspaceState['preview']['subView'] }
  | {
      type: 'SET_PREVIEW_SESSION_RESULT';
      payload: {
        markdownContent: string;
        rawContent?: WorkspaceState['preview']['rawContent'];
      };
    }
  | { type: 'SET_PREVIEW_MARKDOWN'; payload: string }
  | { type: 'SET_PREVIEW_RAW_CONTENT'; payload: any }
  | { type: 'OPEN_FILE_TAB'; payload: WorkspaceTab & { scope?: WorkspaceTabScope } }
  | { type: 'CLOSE_FILE_TAB'; payload: { tabId: string; scope?: WorkspaceTabScope } }
  | { type: 'CLOSE_ALL_TABS'; payload?: { scope?: WorkspaceTabScope } }
  | { type: 'SET_ACTIVE_TAB'; payload: { tabId: string; scope?: WorkspaceTabScope } }
  | { type: 'UPDATE_TAB_CONTENT'; payload: { tabId: string; content: string; scope?: WorkspaceTabScope } }
  | { type: 'SET_TAB_MODIFIED'; payload: { tabId: string; isModified: boolean; scope?: WorkspaceTabScope } }
  | { type: 'SET_ORIGINAL_CONTENT'; payload: { tabId: string; content: string; scope?: WorkspaceTabScope } }
  | { type: 'TOGGLE_MERMAID_PREVIEW'; payload: string }
  | { type: 'TOGGLE_MARKDOWN_PREVIEW'; payload: string }
  // 檔案樹相關 Actions
  | { type: 'SET_FILE_TREE_NODES'; payload: FileNode[] }
  | { type: 'SET_FILE_TREE_LOADING'; payload: boolean }
  | { type: 'SET_FILE_TREE_ERROR'; payload: string | null }
  | { type: 'SELECT_FILE'; payload: string }
  | { type: 'SELECT_FILE_WITH_MODIFIER'; payload: { filePath: string; modifier: import('../features/file-management/types').SelectionModifier } }
  | { type: 'SELECT_RANGE'; payload: { fromPath: string; toPath: string } }
  | { type: 'SET_LAST_SELECTED_FILE'; payload: string | null }
  | { type: 'TOGGLE_MULTI_SELECT'; payload: string }
  | { type: 'CLEAR_SELECTION' }
  | { type: 'SELECT_ALL_FILES'; payload: string[] }
  | { type: 'EXPAND_NODE'; payload: string }
  | { type: 'COLLAPSE_NODE'; payload: string }
  | { type: 'SET_NODE_LOADING'; payload: { path: string; isLoading: boolean } }
  | { type: 'SET_NODE_CHILDREN'; payload: { path: string; children: FileNode[] } }
  | { type: 'SET_PENDING_FILE_ACTION'; payload: import('../features/file-management/types').PendingFileAction | null }
  | { type: 'SET_DRAGGED_NODE'; payload: string | null }
  | { type: 'SET_DROP_TARGET'; payload: string | null }
  | { type: 'SAVE_WORKSPACE_TABS'; payload: { workspaceId: string; scope: WorkspaceTabScope } }
  | {
    type: 'RESTORE_WORKSPACE_TABS'; payload: {
      workspaceId: string;
      scope: WorkspaceTabScope;
      tabsState?: WorkspaceTabState;
    }
  }
  | { type: 'CLEAR_WORKSPACE_TABS_CACHE'; payload: { workspaceId: string; scope?: WorkspaceTabScope } }
  | { type: 'RESTORE_LAYOUT_PREFERENCES'; payload: WorkspaceLayoutPreferences };

// Workspace 佈局偏好（持久化至 localStorage）
export interface WorkspaceLayoutPreferences {
  sidebarCollapsed: boolean;
  sidebarWidth: number;
  secondColumnCollapsed: boolean;
  secondColumnWidth: number;
  rightChatCollapsed: boolean;
  rightChatWidth: number;
  expandedNavigationItems: string[];
}

// API Response 類型
export interface WorkspaceListResponse {
  items: Array<{
    id: string;
    name?: string;
    description?: string | null;
    provisioner?: 'docker' | 'kubernetes';
    targetNamespace?: string | null;
    overallPhase?: string;
    runtimeStatus?: string | null;
    owner?: {
      id: string;
      displayName: string;
      avatarUrl?: string | null;
    };
  }>;
}

export interface WorkspaceComponentStatusResponse {
  phase?: string;
  internalUrl?: string | null;
  externalUrl?: string | null;
  lastSeen?: string | null;
  lastRestartRequestedAt?: string | null;
}

export interface WorkspaceComponentsResponse {
  runtime?: WorkspaceComponentStatusResponse;
  browser?: WorkspaceComponentStatusResponse;
  nextjs?: WorkspaceComponentStatusResponse;
}

export interface WorkspaceResourceValuesResponse {
  cpu: string;
  memory: string;
}

export interface WorkspaceResourceRequirementsResponse {
  requests: WorkspaceResourceValuesResponse;
  limits: WorkspaceResourceValuesResponse;
}

export interface WorkspaceRuntimeStatus {
  status?: string;
  containerId?: string | null;
  internalUrl?: string | null;
  externalUrl?: string | null;
  internalPort?: number;
  externalPort?: number | null;
  lastSeen?: string | null;
  webPreviewInternalPort?: number;
  webPreviewExternalPort?: number | null;
  webPreviewInternalUrl?: string | null;
  webPreviewExternalUrl?: string | null;
  terminalExternalPort?: number | null;
  terminalExternalUrl?: string | null;
  // Browser container fields
  browserContainerId?: string | null;
  browserStatus?: BrowserContainerStatus;
  browserCreatedAt?: string | null;
  browserLastSeen?: string | null;

  // Browser WebRTC fields
  browserWebrtcInternalUrl?: string | null;
  browserWebrtcExternalUrl?: string | null;
  browserWebrtcInternalPort?: number;
  browserWebrtcExternalPort?: number | null;

  // Browser CDP fields
  browserCdpInternalPort?: number;
  browserCdpExternalPort?: number | null;

  // Next.js container fields
  nextjsContainerId?: string | null;
  nextjsStatus?: 'stopped' | 'starting' | 'running' | 'error' | 'restarting';
  nextjsCreatedAt?: string | null;
  nextjsLastSeen?: string | null;
  nextjsInternalUrl?: string | null;
  nextjsExternalUrl?: string | null;
  nextjsInternalPort?: number;
  nextjsExternalPort?: number | null;
  nextjsApiInternalPort?: number;
  nextjsApiExternalPort?: number | null;
}

export interface WorkspaceDetailResponse {
  id: string;
  name?: string;
  description?: string | null;
  owner?: {
    id: string;
    displayName: string;
    avatarUrl?: string | null;
    username?: string;
    email?: string;
  };
  templateId?: string | null;
  gitUrl?: string | null;
  branch?: string;
  runtime?: string;
  provisioner?: 'docker' | 'kubernetes';
  targetNamespace?: string | null;
  overallPhase?: string;
  cliType?: string;
  setupScript?: string | null;
  envVars?: Array<{ key: string; value: string }>;
  runtimeResources?: WorkspaceResourceRequirementsResponse | null;
  portMappings?: Array<{
    containerPort: number;
    hostPort?: number | null;
    protocol?: string;
  }>;
  runtimeStatus?: WorkspaceRuntimeStatus;
  components?: WorkspaceComponentsResponse;
  firewallAvailable?: boolean;
  firewallUnavailableReason?: string | null;
  firewall?: {
    workspace?: {
      networkAccessEnabled?: boolean;
      domainAccessMode?: string;
      allowedDomains?: string[];
      effectiveAllowedDomains?: string[];
    };
    browser?: {
      networkAccessEnabled?: boolean;
      domainAccessMode?: string;
      allowedDomains?: string[];
      effectiveAllowedDomains?: string[];
    };
  };
  preferredCli?: string;
  fallbackEnabled?: boolean;
  workspacePath?: string;
  createdAt?: string;
  updatedAt?: string;
  runtimeJob?: any;
}

export interface RuntimeFileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  lastModified?: string;
  depth: number;
  children?: RuntimeFileTreeNode[];
  hasChildren?: boolean;
}

export interface RuntimeFileTreeResponse {
  nodes: RuntimeFileTreeNode[];
}

export interface RuntimeFileContentResponse {
  path: string;
  content: string;
  encoding: string;
  size: number;
  lastModified: string;
  versionId?: string;
  contentHash?: string;
  language?: string | null;
}

export interface RuntimeDuplicateResponse {
  destinationPath: string;
}

export interface RuntimeArchiveTicketResponse {
  operationId: string;
  status: 'succeeded';
  statusUrl: string;
  archiveFormat: 'zip' | 'tar';
}

export interface RuntimeSaveFileResponse {
  versionId: string;
}

export interface RuntimeBatchDeleteResponse {
  deleted: string[];
  failed: string[];
}

export interface RuntimeDeleteResponse {
  deleted: string[];
  warnings: string[];
}

// Context 類型定義
export interface WorkspaceContextType {
  state: WorkspaceState;
  dispatch: React.Dispatch<WorkspaceAction>;

  // 便利方法
  workspace: {
    tabScope: WorkspaceTabScope;
    openTabs: WorkspaceTab[];
    activeTabId: string | null;
    versionControl: WorkspaceState['versionControl'];
    workspaceSettings: WorkspaceState['workspaceSettings'];
    containerManagement: WorkspaceState['containerManagement'];
  };
  workspaceRuntime: {
    workspaceId: string | null;
    runtimeBaseUrl: string | null;
    terminalExternalUrl: string | null;
    cliType: string | null;
    runtimeStatus: WorkspaceRuntimeStatus | null;
    isLoading: boolean;
    error: string | null;
    reload: () => Promise<void>;
    changeWorkspace: (workspaceId: string) => Promise<void>;
  };
  layout: {
    secondColumnCollapsed: boolean;
  };
  fileTreeState: FileTreeState;
  fileTreeActions: FileTreeActions;

  preview: {
    subView: WorkspaceState['preview']['subView'];
    markdownContent: WorkspaceState['preview']['markdownContent'];
    rawContent?: WorkspaceState['preview']['rawContent'];
    renderMarkdown: (content?: string) => React.ReactNode;
  };

  // 檔案標籤頁操作
  openFileInTab: (filePath: string, content?: string, scope?: WorkspaceTabScope) => void;
  closeTab: (tabId: string, scope?: WorkspaceTabScope) => void;
  closeAllTabs: (scope?: WorkspaceTabScope) => void;
  switchToTab: (tabId: string, scope?: WorkspaceTabScope) => void;

  // 檔案編輯器操作
  fileEditor: {
    scope: WorkspaceTabScope;
    modifiedTabs: string[];
    originalContents: Record<string, string>;
    updateTabContent: (tabId: string, content: string, scope?: WorkspaceTabScope) => void;
    setTabModified: (tabId: string, isModified: boolean, scope?: WorkspaceTabScope) => void;
    setOriginalContent: (tabId: string, content: string, scope?: WorkspaceTabScope) => void;
    saveFile: (tabId: string, scope?: WorkspaceTabScope) => Promise<{ success: boolean; error?: string }>;
    saveAllFiles: (scope?: WorkspaceTabScope) => Promise<{ success: boolean; failed: string[] }>;
    reloadCurrentFile: (scope?: WorkspaceTabScope) => Promise<{ success: boolean; error?: string }>;
    revertFile: (tabId: string, scope?: WorkspaceTabScope) => { success: boolean; error?: string };
    revertAllFiles: (scope?: WorkspaceTabScope) => { success: boolean; failed: string[] };
  };

  // Mermaid 預覽操作
  mermaidPreview: {
    isPreviewMode: (tabId: string) => boolean;
    togglePreview: (tabId: string) => void;
  };

  // Markdown 預覽操作
  markdownPreview: {
    isPreviewMode: (tabId: string) => boolean;
    togglePreview: (tabId: string) => void;
  };

  // 佈局操作
  toggleSecondColumn: () => void;
}

// ===== Preview 相關類型 =====

export interface PreviewSyncResponse {
  workspaceId: string;
  operationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
  startedAt: string;
}

export interface PreviewSyncStatusResponse {
  workspaceId: string;
  operationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number; // 0.0 - 1.0
  message: string;
  startedAt: string;
  completedAt?: string;
  error?: string;
}
