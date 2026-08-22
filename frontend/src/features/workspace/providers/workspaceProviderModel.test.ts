import { describe, expect, it } from 'vitest';
import {
  FILE_EDITOR_ERROR_KEYS,
  buildWorkspaceLayoutPreferences,
} from './workspaceProviderModel';

describe('workspaceProviderModel', () => {
  it('builds persisted layout preferences from workspace state', () => {
    const expandedNavigationItems = ['file-management', 'codex'];
    const preferences = buildWorkspaceLayoutPreferences({
      companionActiveTab: 'terminal',
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems,
      fileTreeShowHiddenEntries: true,
    });

    expect(preferences).toEqual({
      companionActiveTab: 'terminal',
      companionTerminalPlacement: 'bottom',
      expandedNavigationItems: ['file-management', 'codex'],
      fileTreeShowHiddenEntries: true,
    });

    expandedNavigationItems.push('reports');
    expect(preferences.expandedNavigationItems).toEqual(['file-management', 'codex']);
  });

  it('exposes i18n keys for file editor fallback errors', () => {
    expect(FILE_EDITOR_ERROR_KEYS).toEqual({
      saveFileMissing: 'workspace.fileManagement.editor.errors.saveFileMissing',
      saveFailed: 'workspace.fileManagement.tree.notifications.saveFailed',
      reloadFileMissing: 'workspace.fileManagement.editor.errors.reloadFileMissing',
      reloadFailed: 'workspace.fileManagement.editor.errors.reloadFailed',
      originalContentMissing: 'workspace.fileManagement.editor.errors.originalContentMissing',
    });
  });
});
