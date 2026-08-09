import { removePersistedArchiveOperationsForResource } from '@/shared/components/file-workbench';

export const WORKSPACE_ARCHIVE_OPERATIONS_STORAGE_KEY =
  'workspace.fileManagement.archiveOperations.v1';

export const clearWorkspaceArchiveOperations = (workspaceId: string): void => {
  removePersistedArchiveOperationsForResource({
    storageKey: WORKSPACE_ARCHIVE_OPERATIONS_STORAGE_KEY,
    resourceKey: 'workspaceId',
    resourceId: workspaceId,
  });
};
