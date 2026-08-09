import type { WorkspaceLayoutPreferences } from './workspaceStateTypes';

export const FILE_EDITOR_ERROR_KEYS = {
  saveFileMissing: 'workspace.fileManagement.editor.errors.saveFileMissing',
  saveFailed: 'workspace.fileManagement.tree.notifications.saveFailed',
  reloadFileMissing: 'workspace.fileManagement.editor.errors.reloadFileMissing',
  reloadFailed: 'workspace.fileManagement.editor.errors.reloadFailed',
  originalContentMissing: 'workspace.fileManagement.editor.errors.originalContentMissing',
} as const;

type WorkspaceLayoutPreferenceSource = WorkspaceLayoutPreferences;

export const buildWorkspaceLayoutPreferences = ({
  companionActiveTab,
  companionTerminalPlacement,
  expandedNavigationItems,
  fileTreeShowHiddenEntries,
}: WorkspaceLayoutPreferenceSource): WorkspaceLayoutPreferences => ({
  companionActiveTab,
  companionTerminalPlacement,
  expandedNavigationItems: [...expandedNavigationItems],
  fileTreeShowHiddenEntries,
});
