import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceSelectionStorage');
const SELECTED_WORKSPACE_KEY = 'selectedWorkspaceId';

const getStorage = (): Storage | null => (
  typeof window === 'undefined' ? null : window.localStorage
);

export const readSelectedWorkspaceId = (): string | null => {
  try {
    return getStorage()?.getItem(SELECTED_WORKSPACE_KEY) || null;
  } catch (error) {
    logger.error('Failed to read selected workspace from localStorage', { error });
    return null;
  }
};

export const writeSelectedWorkspaceId = (workspaceId: string | null): void => {
  try {
    const storage = getStorage();
    if (!storage) return;

    if (workspaceId) {
      storage.setItem(SELECTED_WORKSPACE_KEY, workspaceId);
    } else {
      storage.removeItem(SELECTED_WORKSPACE_KEY);
    }
  } catch (error) {
    logger.error('Failed to write selected workspace to localStorage', { error });
  }
};

export const clearSelectedWorkspaceIdIfMatches = (workspaceId: string): void => {
  if (readSelectedWorkspaceId() === workspaceId) {
    writeSelectedWorkspaceId(null);
  }
};
