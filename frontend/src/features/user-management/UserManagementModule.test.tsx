import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AdminUser,
  GroupMemberCandidate,
  UserGroup,
  UserGroupMember,
  UserGroupListQuery,
  UserGroupMemberCandidateListQuery,
  UserGroupMemberListQuery,
  UserListQuery,
} from './api/userManagementTypes';
import { UserManagementModule } from './UserManagementModule';

const TEST_TIMESTAMP = '2026-06-30T00:00:00Z';

const createTestAdminUser = (
  overrides: Pick<AdminUser, 'id' | 'username'> & Partial<AdminUser>,
): AdminUser => ({
  id: overrides.id,
  issuer: 'https://issuer.example.com/tenant',
  subject: `subject-${overrides.username}`,
  username: overrides.username,
  email: `${overrides.username}@example.com`,
  firstName: null,
  lastName: null,
  enabled: true,
  localActive: true,
  identityEnabled: true,
  accountState: 'active',
  role: 'member',
  roleStatus: 'valid',
  roleIssues: [],
  syncStatus: 'synced',
  createdAt: TEST_TIMESTAMP,
  updatedAt: TEST_TIMESTAMP,
  ...overrides,
});

const initialUsers: AdminUser[] = [
  createTestAdminUser({
    id: 'user-amelia',
    username: 'amelia',
    firstName: 'Amelia',
    lastName: 'Chen',
    role: 'admin',
  }),
  createTestAdminUser({
    id: 'user-brian',
    username: 'brian',
    firstName: 'Brian',
    lastName: 'Wu',
    role: 'member',
  }),
  createTestAdminUser({
    id: 'user-cora',
    username: 'cora',
    firstName: 'Cora',
    lastName: 'Lin',
    role: null,
    roleStatus: 'multiple',
    roleIssues: ['multiple_platform_roles'],
  }),
  createTestAdminUser({
    id: 'user-erin',
    username: 'erin',
    firstName: 'Erin',
    lastName: 'Tsai',
    enabled: false,
    identityEnabled: false,
    accountState: 'identity_disabled',
    role: 'member',
  }),
];

const initialGroups: UserGroup[] = [
  {
    id: 'group-sa',
    name: 'SA Team',
    description: 'Solution architecture reviewers',
    memberCount: 2,
    knowledgeBaseShareCount: 3,
    createdAt: TEST_TIMESTAMP,
    updatedAt: TEST_TIMESTAMP,
  },
  {
    id: 'group-empty',
    name: 'Empty Team',
    description: null,
    memberCount: 0,
    knowledgeBaseShareCount: 0,
    createdAt: TEST_TIMESTAMP,
    updatedAt: TEST_TIMESTAMP,
  },
];

const toastMock = vi.hoisted(() => vi.fn());
const userManagementApiMock = vi.hoisted(() => ({
  addUserGroupMembers: vi.fn(),
  createUserGroup: vi.fn(),
  getAdminUser: vi.fn(),
  getUserGroup: vi.fn(),
  listAdminUsers: vi.fn(),
  listUserGroupMemberCandidates: vi.fn(),
  listUserGroupMembers: vi.fn(),
  listUserGroups: vi.fn(),
  removeUserGroupMembers: vi.fn(),
  replaceAdminUserRole: vi.fn(),
}));

vi.mock('./api/userManagementApi', () => userManagementApiMock);

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    state: { currentLanguage: 'en' },
    t: (key: string, params?: Record<string, string | number>) => {
      if (params?.count !== undefined) {
        return `${key}:${params.count}`;
      }
      return key;
    },
  }),
}));

let users: AdminUser[];
let groups: UserGroup[];
let memberIds: Set<string>;

const paginate = <Item,>(items: Item[], page = 1, pageSize = 25) => ({
  items: items.slice((page - 1) * pageSize, page * pageSize),
  total: items.length,
  page,
  pageSize,
});

const toMember = (user: AdminUser): UserGroupMember => ({
  userId: user.id,
  username: user.username,
  email: user.email,
  firstName: user.firstName,
  lastName: user.lastName,
  enabled: user.enabled,
  accountState: user.accountState,
  role: user.role,
  roleStatus: user.roleStatus,
  source: 'manual',
  joinedAt: TEST_TIMESTAMP,
  updatedAt: user.updatedAt,
});

const toCandidate = (user: AdminUser): GroupMemberCandidate => ({
  userId: user.id,
  username: user.username,
  email: user.email,
  firstName: user.firstName,
  lastName: user.lastName,
  enabled: user.enabled,
  accountState: user.accountState,
  role: user.role,
  roleStatus: user.roleStatus,
  membershipStatus: memberIds.has(user.id) ? 'member' : 'not_member',
  createdAt: user.createdAt,
  updatedAt: user.updatedAt,
});

const renderModule = (path = '/user-management/users') => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/user-management/*"
            element={<UserManagementModule navigationSlot={<nav>global-navigation</nav>} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('UserManagementModule', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    users = initialUsers.map(user => ({ ...user }));
    groups = initialGroups.map(group => ({ ...group }));
    memberIds = new Set(['user-amelia', 'user-brian']);

    userManagementApiMock.listAdminUsers.mockImplementation(async (query: UserListQuery = {}) => {
      let filtered = [...users];
      if (query.q) {
        const normalized = query.q.toLowerCase();
        filtered = filtered.filter(user => [user.username, user.email, user.firstName, user.lastName]
          .some(value => value?.toLowerCase().includes(normalized)));
      }
      if (query.role) filtered = filtered.filter(user => user.role === query.role);
      if (query.roleStatus) {
        const statuses = query.roleStatus.split(',');
        filtered = filtered.filter(user => statuses.includes(user.roleStatus));
      }
      if (query.accountState) {
        const states = query.accountState.split(',');
        filtered = filtered.filter(user => states.includes(user.accountState));
      }
      return paginate(filtered, query.page, query.pageSize);
    });
    userManagementApiMock.getAdminUser.mockImplementation(async (userId: string) => (
      users.find(user => user.id === userId)
    ));
    userManagementApiMock.listUserGroups.mockImplementation(async (query: UserGroupListQuery = {}) => {
      let filtered = [...groups];
      if (query.q) {
        const normalized = query.q.toLowerCase();
        filtered = filtered.filter(group => [group.name, group.description]
          .some(value => value?.toLowerCase().includes(normalized)));
      }
      if (query.memberCountRange === 'empty') filtered = filtered.filter(group => group.memberCount === 0);
      if (query.memberCountRange === '1_10') filtered = filtered.filter(group => group.memberCount >= 1 && group.memberCount <= 10);
      if (query.memberCountRange === 'gt_10') filtered = filtered.filter(group => group.memberCount >= 11);
      return paginate(filtered, query.page, query.pageSize);
    });
    userManagementApiMock.getUserGroup.mockImplementation(async (groupId: string) => (
      groups.find(group => group.id === groupId)
    ));
    userManagementApiMock.listUserGroupMembers.mockImplementation(async (
      _groupId: string,
      query: UserGroupMemberListQuery = {},
    ) => paginate(
      users.filter(user => memberIds.has(user.id)).map(toMember),
      query.page,
      query.pageSize,
    ));
    userManagementApiMock.listUserGroupMemberCandidates.mockImplementation(async (
      _groupId: string,
      query: UserGroupMemberCandidateListQuery = {},
    ) => paginate(
      users.filter(user => !memberIds.has(user.id)).map(toCandidate),
      query.page,
      query.pageSize,
    ));
    userManagementApiMock.addUserGroupMembers.mockImplementation(async (_groupId: string, userIds: string[]) => {
      userIds.forEach(userId => memberIds.add(userId));
      return { addedUserIds: userIds, skippedUserIds: [], failedUsers: [] };
    });
    userManagementApiMock.removeUserGroupMembers.mockImplementation(async (_groupId: string, userIds: string[]) => {
      userIds.forEach(userId => memberIds.delete(userId));
      return { removedUserIds: userIds, skippedUserIds: [], failedUsers: [] };
    });
    userManagementApiMock.createUserGroup.mockImplementation(async request => {
      const created: UserGroup = {
        id: 'group-platform-team',
        name: request.name,
        description: request.description,
        memberCount: 0,
        knowledgeBaseShareCount: 0,
        createdAt: TEST_TIMESTAMP,
        updatedAt: TEST_TIMESTAMP,
      };
      groups = [created, ...groups];
      return created;
    });
    userManagementApiMock.replaceAdminUserRole.mockImplementation(async (userId: string, role: AdminUser['role']) => {
      const user = users.find(item => item.id === userId)!;
      const updated = { ...user, role, roleStatus: 'valid' as const, roleIssues: [] };
      users = users.map(item => item.id === userId ? updated : item);
      return updated;
    });
  });

  it('persists and restores the navigation sidebar width', async () => {
    const { unmount } = renderModule();
    const sidebar = await screen.findByTestId('user-management-sidebar');
    vi.useFakeTimers();
    try {
      const handle = within(screen.getByTestId('product-shell')).getByRole('separator');
      fireEvent.mouseDown(handle, { clientX: 256 });
      fireEvent.mouseMove(document, { clientX: 340 });
      fireEvent.mouseUp(document);
      vi.advanceTimersByTime(600);
    } finally {
      vi.useRealTimers();
    }
    expect(JSON.parse(localStorage.getItem('shell_layout_user-management_default') ?? '{}').data.navSidebarWidth)
      .toBe(340);
    unmount();

    renderModule();
    expect(screen.getByTestId('product-shell').querySelector('[data-shell-region="navigation"]'))
      .toHaveStyle({ width: '340px' });
  });

  it('loads a true server page with a fully normalized query key contract', async () => {
    renderModule();
    expect(await screen.findByText('Amelia Chen')).toBeInTheDocument();
    expect(userManagementApiMock.listAdminUsers).toHaveBeenCalledWith({
      page: 1,
      pageSize: 25,
      sortBy: 'username',
      sortDirection: 'asc',
    });
    expect(screen.getByText('userManagement.users.count:4')).toBeInTheDocument();
  });

  it('sends search and filters to the backend instead of filtering the first page locally', async () => {
    const user = userEvent.setup();
    renderModule();
    await screen.findByText('Amelia Chen');
    await user.type(screen.getByLabelText('userManagement.users.searchLabel'), 'cora');
    await waitFor(() => expect(userManagementApiMock.listAdminUsers).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'cora', page: 1, pageSize: 25 }),
    ));

    await user.click(screen.getByLabelText('userManagement.filters.advanced'));
    await user.selectOptions(screen.getByLabelText('userManagement.filters.roleStatus'), 'multiple');
    await waitFor(() => expect(userManagementApiMock.listAdminUsers).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'cora', roleStatus: 'multiple', page: 1 }),
    ));
  });

  it('uses route presets as canonical backend filters', async () => {
    const first = renderModule('/user-management/role-issues');
    await waitFor(() => expect(userManagementApiMock.listAdminUsers).toHaveBeenCalledWith(
      expect.objectContaining({ roleStatus: 'missing,multiple' }),
    ));
    first.unmount();

    renderModule('/user-management/disabled');
    await waitFor(() => expect(userManagementApiMock.listAdminUsers).toHaveBeenCalledWith(
      expect.objectContaining({ accountState: 'local_disabled,identity_disabled' }),
    ));
  });

  it('loads identity details and only exposes local platform role mutation', async () => {
    const user = userEvent.setup();
    renderModule();
    await user.click(await screen.findByRole('button', { name: /Amelia Chen/ }));
    await waitFor(() => expect(userManagementApiMock.getAdminUser).toHaveBeenCalledWith('user-amelia'));

    await user.click(screen.getByRole('button', { name: 'userManagement.users.actions.assignRole' }));
    await user.selectOptions(screen.getByLabelText('userManagement.users.assignRoleDialog.fields.role'), 'member');
    await user.click(screen.getByRole('button', { name: 'userManagement.users.assignRoleDialog.actions.save' }));
    await waitFor(() => expect(userManagementApiMock.replaceAdminUserRole)
      .toHaveBeenCalledWith('user-amelia', 'member'));
    expect(screen.getByTestId('user-detail-identity-status')).toHaveTextContent('userManagement.users.fields.identityEnabled');
    expect(screen.getByText('https://issuer.example.com/tenant')).toBeInTheDocument();
    expect(screen.getByText('subject-amelia')).toBeInTheDocument();
  }, 60_000);

  it('queries groups and group members through server-side contracts', async () => {
    const user = userEvent.setup();
    const groupsView = renderModule('/user-management/groups');
    expect(await screen.findByText('SA Team')).toBeInTheDocument();
    await user.click(screen.getByLabelText('userManagement.filters.advanced'));
    await user.selectOptions(screen.getByLabelText('userManagement.filters.memberCount'), 'small');
    await waitFor(() => expect(userManagementApiMock.listUserGroups).toHaveBeenCalledWith(
      expect.objectContaining({ memberCountRange: '1_10', page: 1 }),
    ));
    groupsView.unmount();

    renderModule('/user-management/groups/group-sa/members');
    expect(await screen.findByText('Amelia Chen')).toBeInTheDocument();
    expect(userManagementApiMock.listUserGroupMembers).toHaveBeenCalledWith(
      'group-sa',
      expect.objectContaining({ page: 1, pageSize: 25, sortBy: 'username' }),
    );
    expect(userManagementApiMock.listUserGroupMemberCandidates).toHaveBeenCalledWith(
      'group-sa',
      expect.objectContaining({ membership: 'not_member', page: 1, pageSize: 25 }),
    );
  });
});
