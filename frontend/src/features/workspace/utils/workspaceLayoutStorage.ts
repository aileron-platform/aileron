/**
 * Workspace Layout Storage Utility
 *
 * 管理 workspace 層級的 layout 狀態持久化
 * 使用 localStorage 儲存每個 workspace 的欄位收合狀態與欄寬
 */

import type { WorkspaceLayoutPreferences } from '../providers/workspaceState.types';
import { initialState } from '../providers/workspaceState.constants';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceLayoutStorage');
const STORAGE_KEY_PREFIX = 'workspace_layout_';
const STORAGE_VERSION = '1';

const isStringArray = (value: unknown): value is string[] => (
  Array.isArray(value) && value.every(item => typeof item === 'string')
);

const isValidLayoutPreferences = (value: unknown): value is WorkspaceLayoutPreferences => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return typeof candidate.sidebarCollapsed === 'boolean'
    && typeof candidate.sidebarWidth === 'number'
    && typeof candidate.secondColumnCollapsed === 'boolean'
    && typeof candidate.secondColumnWidth === 'number'
    && typeof candidate.rightChatCollapsed === 'boolean'
    && typeof candidate.rightChatWidth === 'number'
    && isStringArray(candidate.expandedNavigationItems)
    && (candidate.fileTreeShowHiddenEntries === undefined || typeof candidate.fileTreeShowHiddenEntries === 'boolean');
};

export const getDefaultWorkspaceLayoutPreferences = (): WorkspaceLayoutPreferences => ({
  sidebarCollapsed: initialState.sidebarCollapsed,
  sidebarWidth: initialState.sidebarWidth,
  secondColumnCollapsed: initialState.secondColumnCollapsed,
  secondColumnWidth: initialState.secondColumnWidth,
  rightChatCollapsed: initialState.rightChatCollapsed,
  rightChatWidth: initialState.rightChatWidth,
  expandedNavigationItems: [...initialState.expandedNavigationItems],
  fileTreeShowHiddenEntries: initialState.fileTreeShowHiddenEntries,
});

/**
 * 從 localStorage 載入指定 workspace 的 layout 狀態
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

    const defaults = getDefaultWorkspaceLayoutPreferences();

    return {
      ...defaults,
      ...parsed.data,
      expandedNavigationItems: [...parsed.data.expandedNavigationItems],
      fileTreeShowHiddenEntries:
        parsed.data.fileTreeShowHiddenEntries ?? defaults.fileTreeShowHiddenEntries,
    };
  } catch (error) {
    logger.error(`Failed to load workspace layout for ${workspaceId}`, { error });
    clearWorkspaceLayoutPreferences(workspaceId);
    return null;
  }
};

/**
 * 儲存指定 workspace 的 layout 狀態到 localStorage
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

/**
 * 清除指定 workspace 的 layout 快取
 */
export const clearWorkspaceLayoutPreferences = (workspaceId: string): void => {
  try {
    const key = `${STORAGE_KEY_PREFIX}${workspaceId}`;
    localStorage.removeItem(key);
  } catch (error) {
    logger.error(`Failed to clear workspace layout for ${workspaceId}`, { error });
  }
};

/**
 * 清除所有 workspace 的 layout 快取
 */
export const clearAllWorkspaceLayoutPreferences = (): void => {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(STORAGE_KEY_PREFIX)) {
        localStorage.removeItem(key);
      }
    });
  } catch (error) {
    logger.error('Failed to clear all workspace layouts', { error });
  }
};
