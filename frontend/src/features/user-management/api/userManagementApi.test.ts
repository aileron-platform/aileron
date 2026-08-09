import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: apiClientMock,
}));

import {
  addUserGroupMembers,
  createUserGroup,
  getAdminUser,
  getUserGroup,
  listAdminUsers,
  listUserGroupMemberCandidates,
  listUserGroupMembers,
  listUserGroups,
  removeUserGroupMembers,
  replaceAdminUserRole,
} from './userManagementApi';

describe('userManagementApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.values(apiClientMock).forEach(mock => mock.mockResolvedValue({}));
  });

  it('uses the complete server-side admin user contract', async () => {
    await listAdminUsers({
      q: 'amelia',
      roleStatus: 'missing,multiple',
      accountState: 'local_disabled,identity_disabled',
      page: 2,
      pageSize: 50,
      sortBy: 'updatedAt',
      sortDirection: 'desc',
    });
    await getAdminUser('user-1');
    await replaceAdminUserRole('user-1', 'member');

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/admin/users?q=amelia&roleStatus=missing%2Cmultiple&accountState=local_disabled%2Cidentity_disabled&page=2&pageSize=50&sortBy=updatedAt&sortDirection=desc',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(2, '/admin/users/user-1');
    expect(apiClientMock.put).toHaveBeenCalledWith('/admin/users/user-1/role', { role: 'member' });
    expect(apiClientMock.post).not.toHaveBeenCalledWith('/admin/users/user-1/role', expect.anything());
  });

  it('uses paged group, member, candidate, and batch membership endpoints', async () => {
    await listUserGroups({ page: 2, pageSize: 25, memberCountRange: '1_10' });
    await getUserGroup('group-1');
    await listUserGroupMembers('group-1', {
      q: 'amelia',
      source: 'manual',
      page: 3,
      pageSize: 50,
    });
    await listUserGroupMemberCandidates('group-1', {
      membership: 'not_member',
      roleStatus: 'valid',
      page: 1,
      pageSize: 25,
    });
    await addUserGroupMembers('group-1', ['user-2', 'user-3']);
    await removeUserGroupMembers('group-1', ['user-4']);

    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      1,
      '/admin/user-groups?page=2&pageSize=25&memberCountRange=1_10',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(2, '/admin/user-groups/group-1');
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      3,
      '/admin/user-groups/group-1/members?q=amelia&source=manual&page=3&pageSize=50',
    );
    expect(apiClientMock.get).toHaveBeenNthCalledWith(
      4,
      '/admin/user-groups/group-1/member-candidates?membership=not_member&roleStatus=valid&page=1&pageSize=25',
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/admin/user-groups/group-1/members',
      { userIds: ['user-2', 'user-3'] },
    );
    expect(apiClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/admin/user-groups/group-1/members/batch-remove',
      { userIds: ['user-4'] },
    );
  });

  it('uses the canonical group creation payload', async () => {
    await createUserGroup({
      name: 'Platform Team',
      description: 'Shared access',
    });

    expect(apiClientMock.post).toHaveBeenNthCalledWith(1, '/admin/user-groups', {
      name: 'Platform Team',
      description: 'Shared access',
    });
  });
});
