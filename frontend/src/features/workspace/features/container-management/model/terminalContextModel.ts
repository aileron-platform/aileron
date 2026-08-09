import type { WorkspaceGitContext } from '../../../model/workspaceGitContext';

export const resolveDefaultTerminalWorkspacePath = (
  contexts: WorkspaceGitContext[] | undefined,
  selectedGitContextId?: string | null,
): string => {
  const resolvedContextId = selectedGitContextId ?? 'primary';
  const selectedContext = contexts?.find((context) => context.id === resolvedContextId);
  return selectedContext?.repoPath ?? '/workspace';
};
