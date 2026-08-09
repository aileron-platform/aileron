import type { FileConflictWorkflowTransport } from '@/shared/components/file-workbench';
import {
  executeKnowledgeBaseFileConflictOperation,
  preflightKnowledgeBaseFileConflicts,
  type KnowledgeBaseFileConflictPayload,
} from '../../api/knowledgeBaseApi';

export const createKnowledgeBaseFileConflictTransport = (
  knowledgeBaseId: string,
): FileConflictWorkflowTransport<KnowledgeBaseFileConflictPayload> => ({
  preflight: (request, options) => preflightKnowledgeBaseFileConflicts(
    knowledgeBaseId,
    request,
    options,
  ),
  execute: (request, options) => executeKnowledgeBaseFileConflictOperation(
    knowledgeBaseId,
    request,
    options,
  ),
});
