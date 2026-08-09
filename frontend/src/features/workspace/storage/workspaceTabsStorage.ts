import { createLogger } from '@/shared/services/logger';
import type { WorkspaceTabState } from '../providers/workspaceStateTypes';

const logger = createLogger('WorkspaceTabsStorage');
const STORAGE_KEY_PREFIX = 'workspace_tabs_file-management_';
const STORAGE_VERSION = '1';

const normalizeContextId = (contextId?: string | null): string =>
  encodeURIComponent(contextId ?? 'primary');

const getStorageKey = (workspaceId: string, contextId?: string | null): string =>
  `${STORAGE_KEY_PREFIX}${workspaceId}_ctx_${normalizeContextId(contextId)}`;

export const loadWorkspaceTabs = (
  workspaceId: string,
  contextId?: string | null,
): WorkspaceTabState | null => {
  try {
    const key = getStorageKey(workspaceId, contextId);
    const stored = localStorage.getItem(key);
    if (!stored) {
      return null;
    }

    const parsed = JSON.parse(stored);
    if (parsed.version !== STORAGE_VERSION) {
      logger.warn(`Workspace tabs storage version mismatch for ${workspaceId}, clearing cache`);
      localStorage.removeItem(key);
      return null;
    }

    return parsed.data;
  } catch (error) {
    logger.error(`Failed to load workspace tabs for ${workspaceId}`, { error });
    return null;
  }
};

export const saveWorkspaceTabs = (
  workspaceId: string,
  state: WorkspaceTabState,
  contextId?: string | null,
): void => {
  try {
    const key = getStorageKey(workspaceId, contextId);
    const data = {
      version: STORAGE_VERSION,
      timestamp: Date.now(),
      data: state,
    };

    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    logger.error(`Failed to save workspace tabs for ${workspaceId}`, { error });
  }
};

export const clearWorkspaceTabs = (workspaceId: string): void => {
  try {
    const workspaceKeyPrefix = `${STORAGE_KEY_PREFIX}${workspaceId}_ctx_`;
    const keysToRemove = Array.from(
      { length: localStorage.length },
      (_, index) => localStorage.key(index),
    ).filter((key): key is string => key?.startsWith(workspaceKeyPrefix) ?? false);

    keysToRemove.forEach((key) => localStorage.removeItem(key));
  } catch (error) {
    logger.error(`Failed to clear workspace tabs for ${workspaceId}`, { error });
  }
};
