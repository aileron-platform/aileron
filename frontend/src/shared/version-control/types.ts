export interface VersionControlStatus {
  isInitialized: boolean;
  currentBranch: string | null;
  detachedHead: boolean;
  headSha: string | null;
  hasOrigin: boolean;
  upstream: string | null;
  ahead: number;
  behind: number;
  hasConflicts: boolean;
  stagedTotal: number;
  unstagedTotal: number;
  untrackedTotal: number;
  conflictTotal: number;
  operationStatus: VersionControlOperationStatus | null;
}

export interface VersionControlOperationStatus {
  isActive: boolean;
  operation: string | null;
  actorDisplayName: string | null;
  startedAt: string | null;
  blockingScope: 'working_tree_target' | 'common_repository' | null;
  stale: boolean;
  retryable: boolean;
  progressCurrent: number;
  progressTotal: number;
  phase: string;
  cancellable: boolean;
  cancelRequested: boolean;
}

export interface VersionControlRemoteSettings {
  isInitialized: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin?: boolean;
}

export interface VersionControlRemoteBranches {
  branches: string[];
  defaultBranch: string | null;
}

export interface VersionControlRepositoryStatus {
  isGitRepo: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin: boolean;
  hasLocalContent: boolean;
  canCloneSafely: boolean;
  canInitSafely: boolean;
  cloneBlockedReason?: string | null;
}

export interface VersionControlBranch {
  name: string;
  displayName: string;
  kind: 'local' | 'remote';
  isCurrent: boolean;
  upstream: string | null;
  checkedOutTarget: string | null;
  capabilities: {
    switch: VersionControlActionCapability;
    rename: VersionControlActionCapability;
    delete: VersionControlActionCapability;
  };
  ahead: number;
  behind: number;
}

export interface VersionControlActionCapability {
  allowed: boolean;
  disabledReasonKey?: string | null;
}

export interface VersionControlBranchListResponse {
  isInitialized?: boolean;
  branches: VersionControlBranch[];
}

export interface VersionControlFileChange {
  name: string;
  path: string;
  status: string;
  type?: 'added' | 'modified' | 'deleted' | 'renamed' | 'copied' | 'typechange' | 'unmerged' | 'untracked';
  oldPath?: string | null;
  additions?: number;
  deletions?: number;
  diff?: string | null;
  patch?: string | null;
  changeType?: 'staged' | 'unstaged' | 'untracked';
}

export interface VersionControlChangesResponse {
  staged: VersionControlChangePage;
  unstaged: VersionControlChangePage;
  untracked: VersionControlChangePage;
  conflicts: VersionControlChangePage;
}

export interface VersionControlChangePage {
  items: VersionControlFileChange[];
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
}

export interface VersionControlNumstatEntry {
  additions: number;
  deletions: number;
}

export interface VersionControlNumstatParams {
  stagedPaths: string[];
  unstagedPaths: string[];
}

export interface VersionControlNumstatResponse {
  stats: Record<string, VersionControlNumstatEntry>;
}

export type VersionControlStagePayload = string[] | { all: true };

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
  items: VersionControlCommitSummary[];
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
  queryScope: 'current' | 'all' | 'local' | 'remote';
}

export interface VersionControlDiffResponse {
  path: string;
  patch?: string;
  diff?: string;
  binary?: boolean;
}

export interface VersionControlBlobResponse {
  path: string;
  revision?: string | null;
  content: string;
}

export interface VersionControlMutationResult {
  commandId: string;
  headSha: string | null;
  branch: string | null;
  affectedTotal: number;
  skippedTotal: number;
  output: string;
}

export type VersionControlConflictSource = 'collision' | 'stale';
