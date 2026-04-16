import type { GitContext } from '@/features/workspace/features/version-control/types';

export const resolveDefaultTerminalWorkspacePath = (
  contexts: GitContext[] | undefined,
  selectedGitContextId?: string | null,
): string => {
  const resolvedContextId = selectedGitContextId ?? 'primary';
  const selectedContext = contexts?.find((context) => context.id === resolvedContextId);
  return selectedContext?.repoPath ?? '/workspace';
};
