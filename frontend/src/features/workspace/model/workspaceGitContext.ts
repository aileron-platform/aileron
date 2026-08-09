export interface WorkspaceGitContext {
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

export interface WorkspaceGitContextListResponse {
  activeContextId: string;
  contexts: WorkspaceGitContext[];
}
