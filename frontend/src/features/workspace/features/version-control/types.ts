export type {
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitFilesResponse,
  VersionControlCommitListResponse,
  VersionControlCommitSummary,
  VersionControlCheckoutRequest,
  VersionControlCheckoutResponse,
  VersionControlFileChange,
  VersionControlFetchResponse,
  VersionControlPullResponse,
  VersionControlPushResponse,
  VersionControlRemoteSettings,
  VersionControlStatus,
} from '@/shared/types/versionControl';

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
