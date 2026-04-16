import React from 'react';
import { GitBranch } from 'lucide-react';

import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useGitContextsQuery } from '../hooks/useVersionControlQueries';

export const GitContextSelector: React.FC = () => {
  const { workspaceRuntime, state, dispatch } = useWorkspace();
  const workspaceId = workspaceRuntime.workspaceId ?? '';
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl ?? '';
  const contextsQuery = useGitContextsQuery({ workspaceId, runtimeBaseUrl });
  const contexts = contextsQuery.data?.contexts ?? [];
  const selectedGitContextId = state.versionControl.selectedGitContextId;

  React.useEffect(() => {
    const fallbackContextId = selectedGitContextId && contexts.some((context) => context.id === selectedGitContextId)
      ? selectedGitContextId
      : contextsQuery.data?.activeContextId ?? contexts[0]?.id ?? null;

    if (fallbackContextId && fallbackContextId !== selectedGitContextId) {
      dispatch({ type: 'SET_SELECTED_GIT_CONTEXT', payload: fallbackContextId });
    }
  }, [contexts, contextsQuery.data?.activeContextId, dispatch, selectedGitContextId]);

  if (contextsQuery.isLoading || contexts.length === 0) {
    return null;
  }

  return (
    <div className="px-3 py-2 border-b border-border bg-muted/20">
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        <GitBranch className="h-3.5 w-3.5" />
        <span>工作樹</span>
      </label>
      <select
        aria-label="工作樹"
        className="mt-1 w-full rounded border border-input bg-background px-2 py-1 text-sm"
        value={selectedGitContextId ?? contextsQuery.data?.activeContextId ?? contexts[0]?.id ?? ''}
        onChange={(event) => dispatch({ type: 'SET_SELECTED_GIT_CONTEXT', payload: event.target.value })}
      >
        {contexts.map((context) => (
          <option key={context.id} value={context.id}>
            {context.kind === 'primary' ? `主要工作樹 · ${context.displayName}` : `工作樹 · ${context.displayName}`}
          </option>
        ))}
      </select>
    </div>
  );
};
