import { apiClient } from '@/shared/api/apiClient';
import type {
  AdminUser,
  BatchAddMembersResult,
  BatchRemoveMembersResult,
  PlatformRole,
  UserGroup,
  UserGroupCreatePayload,
  UserGroupListQuery,
  UserGroupListResponse,
  UserGroupMemberCandidateListQuery,
  UserGroupMemberCandidateListResponse,
  UserGroupMemberListQuery,
  UserGroupMemberListResponse,
  UserListQuery,
  UserListResponse,
} from './userManagementTypes';

type QueryValue = string | number | boolean | undefined;

const toSearchParams = (params: object): string => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    const queryValue = value as QueryValue;
    if (queryValue !== undefined) {
      searchParams.set(key, String(queryValue));
    }
  });
  const query = searchParams.toString();
  return query ? `?${query}` : '';
};

export async function listAdminUsers(params: UserListQuery = {}): Promise<UserListResponse> {
  return apiClient.get<UserListResponse>(`/admin/users${toSearchParams(params)}`);
}

export async function getAdminUser(userId: string): Promise<AdminUser> {
  return apiClient.get<AdminUser>(`/admin/users/${userId}`);
}

export async function replaceAdminUserRole(userId: string, role: PlatformRole): Promise<AdminUser> {
  return apiClient.put<AdminUser>(`/admin/users/${userId}/role`, { role });
}

export async function listUserGroups(params: UserGroupListQuery = {}): Promise<UserGroupListResponse> {
  return apiClient.get<UserGroupListResponse>(`/admin/user-groups${toSearchParams(params)}`);
}

export async function getUserGroup(groupId: string): Promise<UserGroup> {
  return apiClient.get<UserGroup>(`/admin/user-groups/${groupId}`);
}

export async function createUserGroup(payload: UserGroupCreatePayload): Promise<UserGroup> {
  return apiClient.post<UserGroup>('/admin/user-groups', payload);
}

export async function listUserGroupMembers(
  groupId: string,
  params: UserGroupMemberListQuery = {},
): Promise<UserGroupMemberListResponse> {
  return apiClient.get<UserGroupMemberListResponse>(
    `/admin/user-groups/${groupId}/members${toSearchParams(params)}`,
  );
}

export async function listUserGroupMemberCandidates(
  groupId: string,
  params: UserGroupMemberCandidateListQuery = {},
): Promise<UserGroupMemberCandidateListResponse> {
  return apiClient.get<UserGroupMemberCandidateListResponse>(
    `/admin/user-groups/${groupId}/member-candidates${toSearchParams(params)}`,
  );
}

export async function addUserGroupMembers(
  groupId: string,
  userIds: string[],
): Promise<BatchAddMembersResult> {
  return apiClient.post<BatchAddMembersResult>(`/admin/user-groups/${groupId}/members`, { userIds });
}

export async function removeUserGroupMembers(
  groupId: string,
  userIds: string[],
): Promise<BatchRemoveMembersResult> {
  return apiClient.post<BatchRemoveMembersResult>(`/admin/user-groups/${groupId}/members/batch-remove`, { userIds });
}
