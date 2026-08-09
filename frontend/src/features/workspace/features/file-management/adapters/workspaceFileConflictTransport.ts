import type { FileConflictWorkflowTransport } from '@/shared/components/file-workbench';
import {
  executeRuntimeFileConflictOperation,
  preflightRuntimeFileConflicts,
  type RuntimeFileConflictPayload,
} from '../../../api/workspaceRuntimeApi';

export interface WorkspaceFileConflictTransportOptions {
  runtimeBaseUrl: string;
  contextId?: string | null;
}

export const createWorkspaceFileConflictTransport = ({
  runtimeBaseUrl,
  contextId,
}: WorkspaceFileConflictTransportOptions): FileConflictWorkflowTransport<RuntimeFileConflictPayload> => ({
  preflight: (request, options) => preflightRuntimeFileConflicts(
    runtimeBaseUrl,
    request,
    { ...options, contextId },
  ),
  execute: (request, options) => executeRuntimeFileConflictOperation(
    runtimeBaseUrl,
    {
      ...request,
      payload: { ...request.payload, contextId },
    },
    options,
  ),
});
