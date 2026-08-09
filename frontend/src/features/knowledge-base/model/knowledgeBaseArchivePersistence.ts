import { removePersistedArchiveOperationsForResource } from '@/shared/components/file-workbench';

export const KNOWLEDGE_BASE_ARCHIVE_OPERATIONS_STORAGE_KEY =
  'knowledgeBase.files.archiveOperations.v1';

export const clearKnowledgeBaseArchiveOperations = (knowledgeBaseId: string): void => {
  removePersistedArchiveOperationsForResource({
    storageKey: KNOWLEDGE_BASE_ARCHIVE_OPERATIONS_STORAGE_KEY,
    resourceKey: 'knowledgeBaseId',
    resourceId: knowledgeBaseId,
  });
};
