/**
 * Workspace Layout Storage Utility
 *
 */

import type { WorkspaceLayoutPreferences } from '../providers/workspaceStateTypes';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceLayoutStorage');
const STORAGE_KEY_PREFIX = 'workspace_layout_';
const STORAGE_VERSION = '1';

const isStringArray = (value: unknown): value is string[] => (
  Array.isArray(value) && value.every(item => typeof item === 'string')
);

const isValidCompanionActiveTab = (value: unknown): value is WorkspaceLayoutPreferences['companionActiveTab'] => (
  value === 'ai-chat' || value === 'terminal'
);

const isValidCompanionTerminalPlacement = (
  value: unknown,
): value is WorkspaceLayoutPreferences['companionTerminalPlacement'] => (
  value === 'side' || value === 'bottom'
);

const isValidLayoutPreferences = (value: unknown): value is WorkspaceLayoutPreferences => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return isValidCompanionActiveTab(candidate.companionActiveTab)
    && isValidCompanionTerminalPlacement(candidate.companionTerminalPlacement)
    && isStringArray(candidate.expandedNavigationItems)
    && typeof candidate.fileTreeShowHiddenEntries === 'boolean';
};

export const clearWorkspaceLayoutPreferences = (workspaceId: string): void => {
  try {
    const key = `${STORAGE_KEY_PREFIX}${workspaceId}`;
    localStorage.removeItem(key);
  } catch (error) {
    logger.error(`Failed to clear workspace layout for ${workspaceId}`, { error });
  }
};

/**
 */
export const loadWorkspaceLayoutPreferences = (workspaceId: string): WorkspaceLayoutPreferences | null => {
  try {
    const key = `${STORAGE_KEY_PREFIX}${workspaceId}`;
    const stored = localStorage.getItem(key);

    if (!stored) {
      return null;
    }

    const parsed = JSON.parse(stored) as { version?: string; data?: unknown };

    if (parsed.version !== STORAGE_VERSION || !isValidLayoutPreferences(parsed.data)) {
      logger.warn(`Workspace layout storage invalid for ${workspaceId}, clearing cache`);
      localStorage.removeItem(key);
      return null;
    }

    return {
      companionActiveTab: parsed.data.companionActiveTab,
      companionTerminalPlacement: parsed.data.companionTerminalPlacement,
      expandedNavigationItems: [...parsed.data.expandedNavigationItems],
      fileTreeShowHiddenEntries: parsed.data.fileTreeShowHiddenEntries,
    };
  } catch (error) {
    logger.error(`Failed to load workspace layout for ${workspaceId}`, { error });
    clearWorkspaceLayoutPreferences(workspaceId);
    return null;
  }
};

/**
 */
export const saveWorkspaceLayoutPreferences = (
  workspaceId: string,
  preferences: WorkspaceLayoutPreferences
): void => {
  try {
    const key = `${STORAGE_KEY_PREFIX}${workspaceId}`;
    const data = {
      version: STORAGE_VERSION,
      timestamp: Date.now(),
      data: preferences,
    };

    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    logger.error(`Failed to save workspace layout for ${workspaceId}`, { error });
  }
};
