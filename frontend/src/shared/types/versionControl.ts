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

export interface VersionControlRemoteSettings {
  isInitialized: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin?: boolean;
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
  type?: 'added' | 'modified' | 'deleted' | 'renamed' | 'copied' | 'typechange' | 'unmerged' | 'untracked';
  oldPath?: string | null;
  additions?: number;
  deletions?: number;
  diff?: string | null;
  patch?: string | null;
  changeType?: 'staged' | 'unstaged' | 'untracked';
}

export interface VersionControlChangesResponse {
  staged: VersionControlFileChange[];
  unstaged: VersionControlFileChange[];
  untracked: VersionControlFileChange[];
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

export interface VersionControlFetchResponse {
  remote: string;
  fetchedRefs: string[];
}

export interface VersionControlPullResponse {
  remote: string;
  branch: string;
  fastForward: boolean;
  commits: Array<{
    id: string;
    message: string;
    author: string;
  }>;
}

export interface VersionControlPushResponse {
  remote: string;
  branch: string;
  updates: Array<{
    ref: string;
    status: string;
  }>;
}

export interface VersionControlCheckoutRequest {
  branch: string;
  create?: boolean;
  startPoint?: string | null;
  stashChanges?: boolean;
}

export interface VersionControlCheckoutResponse {
  branch: string;
  created: boolean;
  stashedChanges?: string | null;
}
