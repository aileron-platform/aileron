/**
 * Workspace Tabs Storage Utility
 *
 * 管理 workspace 層級的 tab 狀態持久化
 * 使用 localStorage 儲存每個 workspace 的開啟檔案 tabs
 */

import { createLogger } from '@/shared/services/logger';
import type { WorkspaceTabScope, WorkspaceTabState } from '../providers/workspaceState.types';

const logger = createLogger('WorkspaceTabsStorage');
const STORAGE_KEY_PREFIX = 'workspace_tabs_';
const STORAGE_VERSION = '1';
const LEGACY_STORAGE_KEY_PREFIX = 'workspace_tabs_';

export type WorkspaceTabsState = WorkspaceTabState;

const normalizeContextId = (contextId?: string | null): string => encodeURIComponent(contextId ?? 'primary');

const getStorageKey = (workspaceId: string, scope: WorkspaceTabScope, contextId?: string | null) =>
  scope === 'file-management'
    ? `${STORAGE_KEY_PREFIX}${scope}_${workspaceId}_ctx_${normalizeContextId(contextId)}`
    : `${STORAGE_KEY_PREFIX}${scope}_${workspaceId}`;

const getLegacyStorageKey = (workspaceId: string) => `${LEGACY_STORAGE_KEY_PREFIX}${workspaceId}`;

/**
 * 從 localStorage 載入指定 workspace 的 tabs 狀態
 */
export const loadWorkspaceTabs = (
  workspaceId: string,
  scope: WorkspaceTabScope,
  contextId?: string | null,
): WorkspaceTabsState | null => {
  try {
    const key = getStorageKey(workspaceId, scope, contextId);
    let stored = localStorage.getItem(key);

    if (!stored && scope === 'file-management' && (!contextId || contextId === 'primary')) {
      const legacyKey = getLegacyStorageKey(workspaceId);
      stored = localStorage.getItem(legacyKey);
      if (stored) {
        localStorage.setItem(key, stored);
        localStorage.removeItem(legacyKey);
      }
    }

    if (!stored) {
      return null;
    }

    const parsed = JSON.parse(stored);

    // 版本檢查
    if (parsed.version !== STORAGE_VERSION) {
      logger.warn(`Workspace tabs storage version mismatch for ${workspaceId}:${scope}, clearing cache`);
      localStorage.removeItem(key);
      return null;
    }

    return parsed.data;
  } catch (error) {
    logger.error(`Failed to load workspace tabs for ${workspaceId}`, { error });
    return null;
  }
};

/**
 * 儲存指定 workspace 的 tabs 狀態到 localStorage
 */
export const saveWorkspaceTabs = (
  workspaceId: string,
  scope: WorkspaceTabScope,
  state: WorkspaceTabsState,
  contextId?: string | null,
): void => {
  try {
    const key = getStorageKey(workspaceId, scope, contextId);
    const data = {
      version: STORAGE_VERSION,
      timestamp: Date.now(),
      data: state,
    };

    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    logger.error(`Failed to save workspace tabs for ${workspaceId}:${scope}`, { error });
  }
};

/**
 * 清除指定 workspace 的 tabs 快取
 */
export const clearWorkspaceTabs = (workspaceId: string, scope?: WorkspaceTabScope): void => {
  try {
    if (scope) {
      if (scope === 'file-management') {
        Object.keys(localStorage)
          .filter((key) => key.startsWith(`${STORAGE_KEY_PREFIX}${scope}_${workspaceId}_ctx_`))
          .forEach((key) => localStorage.removeItem(key));
      } else {
        localStorage.removeItem(getStorageKey(workspaceId, scope));
      }
      return;
    }

    (['file-management', 'openspec'] as const).forEach((tabScope) => {
      if (tabScope === 'file-management') {
        Object.keys(localStorage)
          .filter((key) => key.startsWith(`${STORAGE_KEY_PREFIX}${tabScope}_${workspaceId}_ctx_`))
          .forEach((key) => localStorage.removeItem(key));
      } else {
        localStorage.removeItem(getStorageKey(workspaceId, tabScope));
      }
    });
    localStorage.removeItem(getLegacyStorageKey(workspaceId));
  } catch (error) {
    logger.error(`Failed to clear workspace tabs for ${workspaceId}`, { error });
  }
};

/**
 * 清除所有 workspace 的 tabs 快取
 */
export const clearAllWorkspaceTabs = (): void => {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(STORAGE_KEY_PREFIX) || key.startsWith(LEGACY_STORAGE_KEY_PREFIX)) {
        localStorage.removeItem(key);
      }
    });
  } catch (error) {
    logger.error('Failed to clear all workspace tabs', { error });
  }
};

/**
 * 獲取所有已儲存的 workspace IDs
 */
export const getStoredWorkspaceIds = (): string[] => {
  try {
    const keys = Object.keys(localStorage);
    return keys
      .filter(key => key.startsWith(STORAGE_KEY_PREFIX))
      .map(key => key.replace(STORAGE_KEY_PREFIX, ''))
      .map(key => key.replace(/^(file-management|openspec)_/, ''))
      .map(key => key.replace(/_ctx_.+$/, ''));
  } catch (error) {
    logger.error('Failed to get stored workspace IDs', { error });
    return [];
  }
};
