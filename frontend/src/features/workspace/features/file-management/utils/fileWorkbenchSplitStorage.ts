import { SPLIT_PANE_MAX_COUNT } from '@/shared/components/split-pane';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileWorkbenchSplitStorage');
const STORAGE_KEY_PREFIX = 'file_workbench_split_';
const STORAGE_VERSION = '1';

export interface FileWorkbenchSplitStorageEntry {
  direction: 'horizontal' | 'vertical';
  panes: Array<{ tabIds: string[]; activeTabId: string | null }>;
  sizes: number[];
}

const isValidEntry = (value: unknown): value is FileWorkbenchSplitStorageEntry => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  if (candidate.direction !== 'horizontal' && candidate.direction !== 'vertical') {
    return false;
  }

  if (!Array.isArray(candidate.panes) || candidate.panes.length === 0 || candidate.panes.length > SPLIT_PANE_MAX_COUNT) {
    return false;
  }

  if (!Array.isArray(candidate.sizes) || candidate.sizes.length !== candidate.panes.length) {
    return false;
  }

  return candidate.sizes.every((size) => typeof size === 'number' && Number.isFinite(size))
    && candidate.panes.every((pane) => {
      if (!pane || typeof pane !== 'object') {
        return false;
      }

      const paneCandidate = pane as Record<string, unknown>;
      return Array.isArray(paneCandidate.tabIds)
        && paneCandidate.tabIds.every((tabId) => typeof tabId === 'string')
        && (paneCandidate.activeTabId === null || typeof paneCandidate.activeTabId === 'string');
    });
};

const keyFor = (workspaceId: string): string => `${STORAGE_KEY_PREFIX}${workspaceId}`;

const clear = (workspaceId: string): void => {
  try {
    localStorage.removeItem(keyFor(workspaceId));
  } catch (error) {
    logger.error('Failed to clear file workbench split state', { error, workspaceId });
  }
};

const load = (workspaceId: string): FileWorkbenchSplitStorageEntry | null => {
  try {
    const stored = localStorage.getItem(keyFor(workspaceId));
    if (!stored) {
      return null;
    }

    const parsed = JSON.parse(stored) as { version?: string; data?: unknown };
    if (parsed.version !== STORAGE_VERSION || !isValidEntry(parsed.data)) {
      logger.warn('File workbench split state invalid, clearing cache', { workspaceId });
      clear(workspaceId);
      return null;
    }

    return parsed.data;
  } catch (error) {
    logger.error('Failed to load file workbench split state', { error, workspaceId });
    clear(workspaceId);
    return null;
  }
};

const save = (workspaceId: string, entry: FileWorkbenchSplitStorageEntry): void => {
  try {
    localStorage.setItem(keyFor(workspaceId), JSON.stringify({ version: STORAGE_VERSION, data: entry }));
  } catch (error) {
    logger.error('Failed to save file workbench split state', { error, workspaceId });
  }
};

export const fileWorkbenchSplitStorage = { load, save, clear };
