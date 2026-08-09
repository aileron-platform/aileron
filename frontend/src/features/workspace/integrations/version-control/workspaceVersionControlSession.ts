import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { createWorkspaceChangesCapability } from '@/shared/version-control/versionControlChangesCapability';
import { createWorkspaceHistoryCapability } from '@/shared/version-control/versionControlHistoryCapability';
import { createWorkspaceRemoteCapability } from '@/shared/version-control/versionControlRemoteCapability';
import {
  createVersionControlCore,
  shouldRetryVersionControlQuery,
} from '@/shared/version-control/versionControlSessionCore';

export interface WorkspaceGitTarget {
  id: string;
  kind: 'primary' | 'worktree';
  displayName: string;
  repoPath: string;
  branch?: string | null;
  headRef?: string | null;
  detached: boolean;
  headSha?: string | null;
  locked: boolean;
  prunable: boolean;
}

interface WorkspaceGitTargetListResponse {
  activeContextId: string;
  contexts: WorkspaceGitTarget[];
}

interface WorkspaceVersionControlSessionOptions {
  workspaceId: string;
  runtimeBaseUrl: string;
  contextId?: string | null;
}

const OPERATIONS_WITHOUT_TARGET = new Set(['init', 'clone', 'contexts', 'remote-branches']);

const appendTargetContext = (operation: string, contextId?: string | null): string => {
  if (!contextId || OPERATIONS_WITHOUT_TARGET.has(operation.split('?')[0] ?? operation)) {
    return operation;
  }
  const separator = operation.includes('?') ? '&' : '?';
  return `${operation}${separator}contextId=${encodeURIComponent(contextId)}`;
};

export const createWorkspaceVersionControlSession = ({
  workspaceId,
  runtimeBaseUrl,
  contextId,
}: WorkspaceVersionControlSessionOptions) => {
  const baseUrl = runtimeBaseUrl ? `${runtimeBaseUrl}/api/v1` : '';
  const core = createVersionControlCore({
    baseUrl,
    scope: 'workspaces',
    id: workspaceId,
    targetIdentity: contextId ?? 'primary',
    resolveOperation: operation => appendTargetContext(operation, contextId),
    gitQueriesEnabled: true,
    unauthorizedBehavior: 'propagate',
    executionAudience: 'workspace-runtime',
  });
  const history = createWorkspaceHistoryCapability(core);

  const useContextsQuery = () => useQuery({
    queryKey: ['workspace-version-control-targets', workspaceId],
    queryFn: () => core.request<WorkspaceGitTargetListResponse>('contexts'),
    enabled: Boolean(baseUrl && workspaceId),
    retry: shouldRetryVersionControlQuery,
  });

  return {
    changes: createWorkspaceChangesCapability(core),
    history: { ...history, useContextsQuery },
    remote: createWorkspaceRemoteCapability(core),
    refresh: core.refresh,
  };
};

export const useWorkspaceVersionControlSession = (
  options: WorkspaceVersionControlSessionOptions,
) => {
  const { contextId, runtimeBaseUrl, workspaceId } = options;
  return useMemo(
    () => createWorkspaceVersionControlSession({ contextId, runtimeBaseUrl, workspaceId }),
    [contextId, runtimeBaseUrl, workspaceId],
  );
};

export type WorkspaceVersionControlSession = ReturnType<typeof createWorkspaceVersionControlSession>;
