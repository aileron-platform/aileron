export type { PlatformRole } from '@/features/auth/public';
import type { PlatformRole } from '@/features/auth/public';
export type RoleStatus = 'valid' | 'missing' | 'multiple';
type SyncStatus = 'synced' | 'local_shadow_imported' | 'local_shadow_missing' | 'identity_sync_failed';
export type AccountState = 'active' | 'local_disabled' | 'identity_disabled' | 'sync_failed' | 'shadow_missing';
type SortDirection = 'asc' | 'desc';
type MembershipStatus = 'member' | 'not_member';
type GroupMemberSource = 'manual';

interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AdminUser {
  id: string;
  issuer: string | null;
  subject: string | null;
  username: string;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  enabled: boolean;
  localActive: boolean;
  identityEnabled: boolean;
  accountState: AccountState;
  role: PlatformRole | null;
  roleStatus: RoleStatus;
  roleIssues: Array<'missing_platform_role' | 'multiple_platform_roles'>;
  syncStatus: SyncStatus;
  createdAt: string;
  updatedAt: string;
}

export interface UserGroup {
  id: string;
  name: string;
  description: string | null;
  memberCount: number;
  knowledgeBaseShareCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface UserGroupMember {
  userId: string;
  username: string;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  enabled: boolean;
  accountState: AccountState;
  role: PlatformRole | null;
  roleStatus: RoleStatus;
  source: GroupMemberSource;
  joinedAt: string;
  updatedAt: string;
}

export interface GroupMemberCandidate {
  userId: string;
  username: string;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  enabled: boolean;
  accountState: AccountState;
  role: PlatformRole | null;
  roleStatus: RoleStatus;
  membershipStatus: MembershipStatus;
  createdAt: string;
  updatedAt: string;
}

interface GroupMemberFailure {
  userId: string;
  errorCode: string;
}

export interface GroupMemberMutationResult {
  skippedUserIds: string[];
  failedUsers: GroupMemberFailure[];
}

export interface BatchAddMembersResult extends GroupMemberMutationResult {
  addedUserIds: string[];
}

export interface BatchRemoveMembersResult extends GroupMemberMutationResult {
  removedUserIds: string[];
}

type CsvFilter<T extends string> = T | `${T},${string}`;

export interface UserListQuery {
  q?: string;
  role?: PlatformRole;
  roleStatus?: CsvFilter<RoleStatus>;
  accountState?: CsvFilter<AccountState>;
  enabled?: boolean;
  groupId?: string;
  page?: number;
  pageSize?: number;
  sortBy?: 'username' | 'createdAt' | 'updatedAt';
  sortDirection?: SortDirection;
}

export type UserListResponse = PageResponse<AdminUser>;

export interface UserGroupListQuery {
  q?: string;
  memberCountRange?: 'empty' | '1_10' | 'gt_10';
  hasDescription?: boolean;
  updatedWithinDays?: number;
  page?: number;
  pageSize?: number;
  sortBy?: 'name' | 'memberCount' | 'createdAt' | 'updatedAt';
  sortDirection?: SortDirection;
}

export type UserGroupListResponse = PageResponse<UserGroup>;

export interface UserGroupMemberListQuery {
  q?: string;
  role?: PlatformRole;
  accountState?: CsvFilter<AccountState>;
  source?: GroupMemberSource;
  page?: number;
  pageSize?: number;
  sortBy?: 'username' | 'email' | 'joinedAt' | 'updatedAt';
  sortDirection?: SortDirection;
}

export type UserGroupMemberListResponse = PageResponse<UserGroupMember>;

export interface UserGroupMemberCandidateListQuery {
  q?: string;
  membership?: MembershipStatus | 'all';
  role?: PlatformRole;
  accountState?: CsvFilter<AccountState>;
  roleStatus?: CsvFilter<RoleStatus>;
  page?: number;
  pageSize?: number;
  sortBy?: 'username' | 'email' | 'createdAt' | 'updatedAt';
  sortDirection?: SortDirection;
}

export type UserGroupMemberCandidateListResponse = PageResponse<GroupMemberCandidate>;

export interface UserGroupCreatePayload {
  name: string;
  description: string | null;
}
