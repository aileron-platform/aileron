import type {
  UserGroupListQuery,
  UserGroupMemberCandidateListQuery,
  UserGroupMemberListQuery,
  UserListQuery,
} from './userManagementTypes';

export const userManagementQueryKeys = {
  users: () => ['user-management', 'users'] as const,
  userList: (query: UserListQuery) => ['user-management', 'users', query] as const,
  userDetail: (userId: string) => ['user-management', 'user', userId] as const,
  groups: () => ['user-management', 'groups'] as const,
  groupList: (query: UserGroupListQuery) => ['user-management', 'groups', query] as const,
  groupDetail: (groupId: string) => ['user-management', 'group', groupId] as const,
  groupMembers: (groupId: string) => ['user-management', 'group', groupId, 'members'] as const,
  groupMemberList: (groupId: string, query: UserGroupMemberListQuery) => (
    ['user-management', 'group', groupId, 'members', query] as const
  ),
  groupCandidates: (groupId: string) => ['user-management', 'group', groupId, 'candidates'] as const,
  groupCandidateList: (groupId: string, query: UserGroupMemberCandidateListQuery) => (
    ['user-management', 'group', groupId, 'candidates', query] as const
  ),
};
