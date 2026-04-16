export interface VersionControlStatus {
  branch: string;
  ahead: number;
  behind: number;
  detached: boolean;
  hasConflicts: boolean;
  stagedCount: number;
  unstagedCount: number;
  untrackedCount: number;
  lastFetchedAt?: string | null;
}

export interface GitContext {
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

export interface GitContextListResponse {
  activeContextId: string;
  contexts: GitContext[];
}

export interface VersionControlBranch {
  name: string;
  displayName?: string;
  isActive?: boolean;
  isRemote?: boolean;
  ahead?: number;
  behind?: number;
  lastCommit?: {
    id: string;
    message: string;
    author?: string;
    timestamp?: string;
  } | null;
}

export interface VersionControlFileChange {
  name: string;
  path: string;
  status: string;
  type?: 'added' | 'modified' | 'deleted' | 'renamed' | 'untracked';
  oldPath?: string | null;
  additions?: number;
  deletions?: number;
  diff?: string | null;
  patch?: string | null;
  // 標記檔案來源：staged（已暫存）、unstaged（未暫存）、untracked（未追蹤）
  changeType?: 'staged' | 'unstaged' | 'untracked';
}

export interface VersionControlChangesResponse {
  staged: VersionControlFileChange[];
  unstaged: VersionControlFileChange[];
  untracked: VersionControlFileChange[];
  // 分頁資訊
  untrackedTotal?: number;
  untrackedPage?: number;
  untrackedPageSize?: number;
  untrackedHasMore?: boolean;
}

export interface VersionControlCommitSummary {
  id: string;
  message: string;
  author: string;
  email?: string | null;
  timestamp: number;
  branch?: string | null;
  additions?: number;
  deletions?: number;
  files?: number;
}

export interface VersionControlCommitListResponse {
  page: number;
  pageSize: number;
  total: number;
  items: VersionControlCommitSummary[];
}

export interface VersionControlCommitFilesResponse {
  commitId: string;
  files: VersionControlFileChange[];
}
