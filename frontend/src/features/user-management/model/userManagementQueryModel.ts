import type {
  AccountState,
  PlatformRole,
  RoleStatus,
  UserGroupListQuery,
  UserGroupMemberCandidateListQuery,
  UserGroupMemberListQuery,
  UserListQuery,
} from '../api/userManagementTypes';
import { PLATFORM_ROLES } from './userManagementUserModel';

export type UserListMode = 'all' | 'roleIssues' | 'disabled';
export type UserRoleFilter = 'all' | PlatformRole | 'none';
export type UserAccountStateFilter = 'all' | AccountState | 'disabled';
export type UserRoleStatusFilter = 'all' | RoleStatus | 'issue';
export type UserSort = 'usernameAsc' | 'createdDesc' | 'updatedDesc';

export interface UserListViewState {
  q: string;
  role: UserRoleFilter;
  accountState: UserAccountStateFilter;
  roleStatus: UserRoleStatusFilter;
  sort: UserSort;
  page: number;
  pageSize: number;
}

export type GroupListMode = 'all' | 'empty';
export type GroupMemberCountFilter = 'all' | 'empty' | 'small' | 'large';
export type GroupDescriptionFilter = 'all' | 'withDescription' | 'withoutDescription';
export type GroupUpdatedFilter = 'all' | '7d' | '30d';
export type GroupSort = 'nameAsc' | 'membersDesc' | 'updatedDesc';

export interface GroupListViewState {
  q: string;
  memberCount: GroupMemberCountFilter;
  description: GroupDescriptionFilter;
  updated: GroupUpdatedFilter;
  sort: GroupSort;
  page: number;
  pageSize: number;
}

export type MemberAccountStateFilter = 'all' | AccountState;
export type MemberSort = 'usernameAsc' | 'emailAsc' | 'joinedDesc' | 'updatedDesc';

export interface GroupMemberListViewState {
  q: string;
  role: 'all' | PlatformRole;
  accountState: MemberAccountStateFilter;
  source: 'all' | 'manual';
  sort: MemberSort;
  page: number;
  pageSize: number;
}

type CandidateSort = 'usernameAsc' | 'emailAsc' | 'createdDesc' | 'updatedDesc';

export interface GroupCandidateListViewState {
  q: string;
  role: 'all' | PlatformRole;
  accountState: MemberAccountStateFilter;
  roleStatus: 'all' | RoleStatus | 'issue';
  sort: CandidateSort;
  page: number;
  pageSize: number;
}

const ACCOUNT_STATE_VALUES = ['active', 'local_disabled', 'identity_disabled', 'sync_failed', 'shadow_missing'] as const;
const ROLE_STATUS_VALUES = ['valid', 'missing', 'multiple'] as const;
const PAGE_SIZE_VALUES = [25, 50, 100] as const;

const isOneOf = <Value extends string>(value: string | null, values: readonly Value[]): value is Value => (
  value !== null && values.some(candidate => candidate === value)
);

const positiveInteger = (value: string | null, fallback: number): number => {
  if (!value || !/^\d+$/.test(value)) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback;
};

const pageSize = (value: string | null): number => {
  const parsed = positiveInteger(value, 25);
  return PAGE_SIZE_VALUES.includes(parsed as (typeof PAGE_SIZE_VALUES)[number]) ? parsed : 25;
};

export const defaultUserListViewState = (mode: UserListMode): UserListViewState => ({
  q: '',
  role: 'all',
  accountState: mode === 'disabled' ? 'disabled' : 'all',
  roleStatus: mode === 'roleIssues' ? 'issue' : 'all',
  sort: 'usernameAsc',
  page: 1,
  pageSize: 25,
});

export const parseUserListViewState = (
  search: string,
  mode: UserListMode,
): UserListViewState => {
  const defaults = defaultUserListViewState(mode);
  const params = new URLSearchParams(search);
  const role = params.get('role');
  const accountState = params.get('accountState');
  const roleStatus = params.get('roleStatus');
  const sort = params.get('sort');
  return {
    q: params.get('q')?.trim() ?? defaults.q,
    role: role === 'none' || isOneOf(role, PLATFORM_ROLES) ? role : defaults.role,
    accountState: accountState === 'disabled' || isOneOf(accountState, ACCOUNT_STATE_VALUES)
      ? accountState
      : defaults.accountState,
    roleStatus: roleStatus === 'issue' || isOneOf(roleStatus, ROLE_STATUS_VALUES)
      ? roleStatus
      : defaults.roleStatus,
    sort: isOneOf(sort, ['usernameAsc', 'createdDesc', 'updatedDesc'] as const) ? sort : defaults.sort,
    page: positiveInteger(params.get('page'), defaults.page),
    pageSize: pageSize(params.get('pageSize')),
  };
};

export const userListViewStateToSearchParams = (
  state: UserListViewState,
  mode: UserListMode,
): URLSearchParams => {
  const defaults = defaultUserListViewState(mode);
  const params = new URLSearchParams();
  const q = state.q.trim();
  if (q) params.set('q', q);
  if (state.role !== defaults.role) params.set('role', state.role);
  if (state.accountState !== defaults.accountState) params.set('accountState', state.accountState);
  if (state.roleStatus !== defaults.roleStatus) params.set('roleStatus', state.roleStatus);
  if (state.sort !== defaults.sort) params.set('sort', state.sort);
  if (state.page !== defaults.page) params.set('page', String(state.page));
  if (state.pageSize !== defaults.pageSize) params.set('pageSize', String(state.pageSize));
  return params;
};

export const toUserListQuery = (state: UserListViewState): Required<Pick<
  UserListQuery,
  'page' | 'pageSize' | 'sortBy' | 'sortDirection'
>> & UserListQuery => {
  const sort = {
    usernameAsc: { sortBy: 'username', sortDirection: 'asc' },
    createdDesc: { sortBy: 'createdAt', sortDirection: 'desc' },
    updatedDesc: { sortBy: 'updatedAt', sortDirection: 'desc' },
  } as const;
  const q = state.q.trim();
  const roleStatus = state.role === 'none' || state.roleStatus === 'issue'
    ? 'missing,multiple'
    : state.roleStatus === 'all' ? undefined : state.roleStatus;
  const accountState = state.accountState === 'disabled'
    ? 'local_disabled,identity_disabled'
    : state.accountState === 'all' ? undefined : state.accountState;
  return {
    ...(q ? { q } : {}),
    ...(isOneOf(state.role, PLATFORM_ROLES) ? { role: state.role } : {}),
    ...(roleStatus ? { roleStatus } : {}),
    ...(accountState ? { accountState } : {}),
    page: state.page,
    pageSize: state.pageSize,
    ...sort[state.sort],
  };
};

export const defaultGroupListViewState = (mode: GroupListMode): GroupListViewState => ({
  q: '',
  memberCount: mode === 'empty' ? 'empty' : 'all',
  description: 'all',
  updated: 'all',
  sort: 'nameAsc',
  page: 1,
  pageSize: 25,
});

export const parseGroupListViewState = (
  search: string,
  mode: GroupListMode,
): GroupListViewState => {
  const defaults = defaultGroupListViewState(mode);
  const params = new URLSearchParams(search);
  const memberCount = params.get('memberCount');
  const description = params.get('description');
  const updated = params.get('updated');
  const sort = params.get('sort');
  return {
    q: params.get('q')?.trim() ?? defaults.q,
    memberCount: isOneOf(memberCount, ['all', 'empty', 'small', 'large'] as const)
      ? memberCount
      : defaults.memberCount,
    description: isOneOf(description, ['all', 'withDescription', 'withoutDescription'] as const)
      ? description
      : defaults.description,
    updated: isOneOf(updated, ['all', '7d', '30d'] as const) ? updated : defaults.updated,
    sort: isOneOf(sort, ['nameAsc', 'membersDesc', 'updatedDesc'] as const) ? sort : defaults.sort,
    page: positiveInteger(params.get('page'), defaults.page),
    pageSize: pageSize(params.get('pageSize')),
  };
};

export const groupListViewStateToSearchParams = (
  state: GroupListViewState,
  mode: GroupListMode,
): URLSearchParams => {
  const defaults = defaultGroupListViewState(mode);
  const params = new URLSearchParams();
  const q = state.q.trim();
  if (q) params.set('q', q);
  if (state.memberCount !== defaults.memberCount) params.set('memberCount', state.memberCount);
  if (state.description !== defaults.description) params.set('description', state.description);
  if (state.updated !== defaults.updated) params.set('updated', state.updated);
  if (state.sort !== defaults.sort) params.set('sort', state.sort);
  if (state.page !== defaults.page) params.set('page', String(state.page));
  if (state.pageSize !== defaults.pageSize) params.set('pageSize', String(state.pageSize));
  return params;
};

export const toUserGroupListQuery = (state: GroupListViewState): UserGroupListQuery => {
  const q = state.q.trim();
  const memberCountRange = {
    all: undefined,
    empty: 'empty',
    small: '1_10',
    large: 'gt_10',
  } as const;
  const sort = {
    nameAsc: { sortBy: 'name', sortDirection: 'asc' },
    membersDesc: { sortBy: 'memberCount', sortDirection: 'desc' },
    updatedDesc: { sortBy: 'updatedAt', sortDirection: 'desc' },
  } as const;
  return {
    ...(q ? { q } : {}),
    ...(memberCountRange[state.memberCount]
      ? { memberCountRange: memberCountRange[state.memberCount] }
      : {}),
    ...(state.description === 'withDescription' ? { hasDescription: true } : {}),
    ...(state.description === 'withoutDescription' ? { hasDescription: false } : {}),
    ...(state.updated === '7d' ? { updatedWithinDays: 7 } : {}),
    ...(state.updated === '30d' ? { updatedWithinDays: 30 } : {}),
    page: state.page,
    pageSize: state.pageSize,
    ...sort[state.sort],
  };
};

export const defaultGroupMemberListViewState = (): GroupMemberListViewState => ({
  q: '',
  role: 'all',
  accountState: 'all',
  source: 'all',
  sort: 'usernameAsc',
  page: 1,
  pageSize: 25,
});

export const parseGroupMemberListViewState = (search: string): GroupMemberListViewState => {
  const defaults = defaultGroupMemberListViewState();
  const params = new URLSearchParams(search);
  const role = params.get('role');
  const accountState = params.get('accountState');
  const source = params.get('source');
  const sort = params.get('sort');
  return {
    q: params.get('q')?.trim() ?? defaults.q,
    role: isOneOf(role, PLATFORM_ROLES) ? role : defaults.role,
    accountState: isOneOf(accountState, ACCOUNT_STATE_VALUES) ? accountState : defaults.accountState,
    source: source === 'manual' ? source : defaults.source,
    sort: isOneOf(sort, ['usernameAsc', 'emailAsc', 'joinedDesc', 'updatedDesc'] as const)
      ? sort
      : defaults.sort,
    page: positiveInteger(params.get('page'), defaults.page),
    pageSize: pageSize(params.get('pageSize')),
  };
};

export const groupMemberListViewStateToSearchParams = (
  state: GroupMemberListViewState,
): URLSearchParams => {
  const defaults = defaultGroupMemberListViewState();
  const params = new URLSearchParams();
  const q = state.q.trim();
  if (q) params.set('q', q);
  if (state.role !== defaults.role) params.set('role', state.role);
  if (state.accountState !== defaults.accountState) params.set('accountState', state.accountState);
  if (state.source !== defaults.source) params.set('source', state.source);
  if (state.sort !== defaults.sort) params.set('sort', state.sort);
  if (state.page !== defaults.page) params.set('page', String(state.page));
  if (state.pageSize !== defaults.pageSize) params.set('pageSize', String(state.pageSize));
  return params;
};

export const toUserGroupMemberListQuery = (
  state: GroupMemberListViewState,
): UserGroupMemberListQuery => {
  const q = state.q.trim();
  const sort = {
    usernameAsc: { sortBy: 'username', sortDirection: 'asc' },
    emailAsc: { sortBy: 'email', sortDirection: 'asc' },
    joinedDesc: { sortBy: 'joinedAt', sortDirection: 'desc' },
    updatedDesc: { sortBy: 'updatedAt', sortDirection: 'desc' },
  } as const;
  return {
    ...(q ? { q } : {}),
    ...(state.role !== 'all' ? { role: state.role } : {}),
    ...(state.accountState !== 'all' ? { accountState: state.accountState } : {}),
    ...(state.source !== 'all' ? { source: state.source } : {}),
    page: state.page,
    pageSize: state.pageSize,
    ...sort[state.sort],
  };
};

export const defaultGroupCandidateListViewState = (): GroupCandidateListViewState => ({
  q: '',
  role: 'all',
  accountState: 'all',
  roleStatus: 'all',
  sort: 'usernameAsc',
  page: 1,
  pageSize: 25,
});

export const toUserGroupMemberCandidateListQuery = (
  state: GroupCandidateListViewState,
): UserGroupMemberCandidateListQuery => {
  const q = state.q.trim();
  const sort = {
    usernameAsc: { sortBy: 'username', sortDirection: 'asc' },
    emailAsc: { sortBy: 'email', sortDirection: 'asc' },
    createdDesc: { sortBy: 'createdAt', sortDirection: 'desc' },
    updatedDesc: { sortBy: 'updatedAt', sortDirection: 'desc' },
  } as const;
  return {
    ...(q ? { q } : {}),
    membership: 'not_member',
    ...(state.role !== 'all' ? { role: state.role } : {}),
    ...(state.accountState !== 'all' ? { accountState: state.accountState } : {}),
    ...(state.roleStatus === 'issue' ? { roleStatus: 'missing,multiple' } : {}),
    ...(state.roleStatus !== 'all' && state.roleStatus !== 'issue'
      ? { roleStatus: state.roleStatus }
      : {}),
    page: state.page,
    pageSize: state.pageSize,
    ...sort[state.sort],
  };
};

export const resetPage = <State extends { page: number }>(
  state: State,
  patch: Partial<State>,
): State => ({ ...state, ...patch, page: 1 });
