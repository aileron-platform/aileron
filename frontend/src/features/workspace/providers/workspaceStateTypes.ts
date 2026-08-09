/**
 */

import type { FileTreeState, FileTreeActions } from '../features/file-management/model/fileManagementTypes';
import type React from 'react';
import type {
  BrowserConnectivityProjectionResponse,
  WorkspaceRuntimeStatus,
} from '../api/workspaceApiTypes';

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
  revisions: Record<string, string | null | undefined>;
}

export type WorkspaceFeature =
  | 'ai-chat-home'
  | 'file-management'
  | 'version-control'
  | 'workspace-settings'
  | 'container-management'
  | 'workspace-automation'
  | 'claude-code'
  | 'opencode'
  | 'codex'
  | 'browser'
  | 'canvas';

export type WorkspaceCompanionActiveTab = 'ai-chat' | 'terminal';
export type WorkspaceCompanionTerminalPlacement = 'side' | 'bottom';

export interface WorkspaceState {
  currentFeature: WorkspaceFeature;
  companionActiveTab: WorkspaceCompanionActiveTab;
  companionTerminalPlacement: WorkspaceCompanionTerminalPlacement;
  chatExpanded: boolean;
  fileManagementEditorExpanded: boolean;
  // Generic full-screen mode for the third column (hides nav + second column).
  mainContentExpanded: boolean;
  fileTreeShowHiddenEntries: boolean;

  expandedNavigationItems: string[];

  fileManagement: {
    selectedFile: string | null;
    openTabs: WorkspaceTab[];
    activeTabId: string | null;
    modifiedTabs: string[];
    originalContents: Record<string, string>;
    revisions: Record<string, string | null | undefined>;
    mermaidCanvasMode: Record<string, boolean>;
    markdownCanvasMode: Record<string, boolean>;
  };

  workspaceTabsCache: Record<string, Partial<Record<string, WorkspaceTabState>>>;

  versionControl: {
    subView: 'changes' | 'history';
    selectedCommit: string | null;
    selectedGitContextId: string | null;
  };

  workspaceSettings: {
    subView: 'basic' | 'access' | 'knowledge-bases' | 'reset';
  };

  containerManagement: {
    subView: 'runtime' | 'firewall' | 'terminal';
  };

  agentToolSettings: {
    subView: string;
  };
}

export type WorkspaceAction =
  | { type: 'SET_CURRENT_FEATURE'; payload: WorkspaceFeature }
  | { type: 'TOGGLE_CHAT_EXPANDED' }
  | { type: 'TOGGLE_FILE_MANAGEMENT_EDITOR_EXPANDED' }
  | { type: 'SET_COMPANION_ACTIVE_TAB'; payload: WorkspaceCompanionActiveTab }
  | { type: 'SET_COMPANION_TERMINAL_PLACEMENT'; payload: WorkspaceCompanionTerminalPlacement }
  | { type: 'SET_CHAT_EXPANDED'; payload: boolean }
  | { type: 'SET_FILE_MANAGEMENT_EDITOR_EXPANDED'; payload: boolean }
  | { type: 'TOGGLE_MAIN_CONTENT_EXPANDED' }
  | { type: 'SET_MAIN_CONTENT_EXPANDED'; payload: boolean }
  | { type: 'TOGGLE_NAVIGATION_ITEM'; payload: string }
  | { type: 'ENSURE_NAVIGATION_ITEM_EXPANDED'; payload: string }
  | { type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES'; payload: boolean }
  | { type: 'SET_VERSION_CONTROL_SUB_VIEW'; payload: 'changes' | 'history' }
  | { type: 'SET_SELECTED_GIT_CONTEXT'; payload: string | null }
  | { type: 'SET_WORKSPACE_SETTINGS_SUB_VIEW'; payload: WorkspaceState['workspaceSettings']['subView'] }
  | { type: 'SET_CONTAINER_MANAGEMENT_SUB_VIEW'; payload: 'runtime' | 'firewall' | 'terminal' }
  | { type: 'SET_AGENT_TOOL_SUB_VIEW'; payload: string }
  | { type: 'OPEN_FILE_TAB'; payload: WorkspaceTab }
  | { type: 'CLOSE_FILE_TAB'; payload: { tabId: string } }
  | { type: 'CLOSE_ALL_TABS' }
  | { type: 'CLEAR_WORKSPACE_FILE_STATE'; payload: { workspaceId: string } }
  | { type: 'REORDER_FILE_TABS'; payload: { tabIds: string[] } }
  | { type: 'SET_ACTIVE_TAB'; payload: { tabId: string } }
  | { type: 'UPDATE_TAB_CONTENT'; payload: { tabId: string; content: string } }
  | { type: 'SET_TAB_MODIFIED'; payload: { tabId: string; isModified: boolean } }
  | { type: 'SET_ORIGINAL_CONTENT'; payload: { tabId: string; content: string } }
  | { type: 'SET_FILE_VERSION_ID'; payload: { tabId: string; revision?: string | null } }
  | { type: 'REMAP_FILE_TABS'; payload: { sourcePath: string; targetPath: string } }
  | { type: 'TOGGLE_MERMAID_PREVIEW'; payload: string }
  | { type: 'TOGGLE_MARKDOWN_PREVIEW'; payload: string }
  | { type: 'SAVE_WORKSPACE_TABS'; payload: { workspaceId: string; contextId?: string | null } }
  | {
    type: 'RESTORE_WORKSPACE_TABS'; payload: {
      workspaceId: string;
      contextId?: string | null;
      tabsState?: WorkspaceTabState;
    }
  }
  | { type: 'RESTORE_LAYOUT_PREFERENCES'; payload: WorkspaceLayoutPreferences };

export interface WorkspaceLayoutPreferences {
  companionActiveTab: WorkspaceCompanionActiveTab;
  companionTerminalPlacement: WorkspaceCompanionTerminalPlacement;
  expandedNavigationItems: string[];
  fileTreeShowHiddenEntries: boolean;
}

export interface WorkspaceContextType {
  state: WorkspaceState;
  dispatch: React.Dispatch<WorkspaceAction>;
  permissions: import('../model/workspacePermissions').WorkspacePermissions;
  fileManagementTabsRestoreStatus: {
    ready: boolean;
    workspaceId: string | null;
    workspaceName: string | null;
    contextId?: string | null;
  };

  workspace: {
    openTabs: WorkspaceTab[];
    activeTabId: string | null;
    versionControl: WorkspaceState['versionControl'];
    workspaceSettings: WorkspaceState['workspaceSettings'];
    containerManagement: WorkspaceState['containerManagement'];
  };
  workspaceRuntime: {
    workspaceId: string | null;
    runtimeBaseUrl: string | null;
    agenticTools: import('@/shared/types/agenticTool').AgenticTool[];
    accessRole: import('@/shared/authorization/resourceAccessRole').ResourceAccessRole | null;
    accessSource: import('@/shared/authorization/resourceAuthorization').ResourceAccessSource | null;
    accessSources: import('@/shared/authorization/resourceAuthorization').ResourceAccessSource[];
    allowedOperations: import('@/shared/authorization/operationIds').OperationId[];
    runtimeStatus: WorkspaceRuntimeStatus | null;
    browserConnectivity: BrowserConnectivityProjectionResponse | null;
    isLoading: boolean;
    isAuthorizationResolved: boolean;
    error: string | null;
    errorCode: string | null;
    reload: () => Promise<void>;
    changeWorkspace: (workspaceId: string) => Promise<void>;
  };
  layout: {
    fileManagementEditorExpanded: boolean;
    fileManagementFocusMode: boolean;
  };
  fileTreeState: FileTreeState;
  fileTreeActions: FileTreeActions;

  openFileInTab: (filePath: string, content?: string) => void;
  closeTab: (tabId: string) => void;
  closeAllTabs: () => void;
  switchToTab: (tabId: string) => void;

  fileEditor: {
    modifiedTabs: string[];
    originalContents: Record<string, string>;
    revisions: Record<string, string | null | undefined>;
    updateTabContent: (tabId: string, content: string) => void;
    reorderTabs: (tabIds: string[]) => void;
    setTabModified: (tabId: string, isModified: boolean) => void;
    setOriginalContent: (tabId: string, content: string) => void;
    setFileRevision: (tabId: string, revision?: string | null) => void;
    saveFile: (tabId: string) => Promise<{ success: boolean; error?: string }>;
    saveAllFiles: () => Promise<{ success: boolean; failed: string[] }>;
    reloadCurrentFile: () => Promise<{ success: boolean; error?: string }>;
    revertFile: (tabId: string) => { success: boolean; error?: string };
    revertAllFiles: () => { success: boolean; failed: string[] };
  };

  mermaidCanvas: {
    isCanvasMode: (tabId: string) => boolean;
    toggleCanvas: (tabId: string) => void;
  };

  markdownCanvas: {
    isCanvasMode: (tabId: string) => boolean;
    toggleCanvas: (tabId: string) => void;
  };

  toggleFileManagementEditorExpanded: () => void;
  toggleFileManagementFocusMode: () => void;
}
