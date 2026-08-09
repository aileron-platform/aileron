import React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { User, UsersRound } from 'lucide-react';
import {
  addUserGroupMembers,
  createUserGroup,
  getAdminUser,
  getUserGroup,
  listAdminUsers,
  listUserGroupMembers,
  listUserGroupMemberCandidates,
  listUserGroups,
  removeUserGroupMembers,
  replaceAdminUserRole,
} from './api/userManagementApi';
import { userManagementQueryKeys } from './api/userManagementQueryKeys';
import type {
  AdminUser,
  GroupMemberMutationResult,
  PlatformRole,
} from './api/userManagementTypes';
import { GroupDetailPanel } from './components/GroupDetailPanel';
import { GroupListPanel } from './components/GroupListPanel';
import { GroupMemberWorkbench } from './components/GroupMemberWorkbench';
import { UserDetailPanel } from './components/UserDetailPanel';
import { UserListPanel } from './components/UserListPanel';
import { UserManagementShell, type UserManagementSection } from './components/UserManagementShell';
import {
  getUserManagementErrorCodeI18nKey,
  getUserManagementErrorI18nKey,
} from './model/userManagementErrorI18n';
import {
  defaultGroupCandidateListViewState,
  groupListViewStateToSearchParams,
  groupMemberListViewStateToSearchParams,
  parseGroupListViewState,
  parseGroupMemberListViewState,
  parseUserListViewState,
  toUserGroupListQuery,
  toUserGroupMemberCandidateListQuery,
  toUserGroupMemberListQuery,
  toUserListQuery,
  userListViewStateToSearchParams,
  type GroupListMode,
  type GroupListViewState,
  type GroupMemberListViewState,
  type GroupCandidateListViewState,
  type UserListMode,
  type UserListViewState,
} from './model/userManagementQueryModel';
import { getAdminUserDisplayName } from './model/userManagementUserModel';
import { useToast } from '@/shared/components/ui/use-toast';
import { ROUTES } from '@/shared/constants/routes';
import { useI18n } from '@/shared/hooks/useI18n';

const resolveGroupMembersGroupId = (pathname: string): string | null => {
  const match = pathname.match(/\/groups\/([^/]+)\/members$/);
  return match?.[1] ?? null;
};

const resolveSection = (pathname: string): UserManagementSection => {
  if (resolveGroupMembersGroupId(pathname)) {
    return 'groupMembers';
  }
  if (pathname.endsWith('/groups/empty')) {
    return 'emptyGroups';
  }
  if (pathname.endsWith('/groups')) {
    return 'groups';
  }
  if (pathname.endsWith('/role-issues')) {
    return 'roleIssues';
  }
  if (pathname.endsWith('/disabled')) {
    return 'disabledUsers';
  }
  return 'users';
};

const userListMode = (section: UserManagementSection): UserListMode => {
  if (section === 'roleIssues') return 'roleIssues';
  if (section === 'disabledUsers') return 'disabled';
  return 'all';
};

const groupListMode = (section: UserManagementSection): GroupListMode => (
  section === 'emptyGroups' ? 'empty' : 'all'
);

const useReportQueryError = (
  error: unknown,
  reportError: (error: unknown) => void,
): void => {
  React.useEffect(() => {
    if (error) {
      reportError(error);
    }
  }, [error, reportError]);
};

interface UserManagementPageProps {
  navigationSlot: React.ReactNode;
}

export const UserManagementPage: React.FC<UserManagementPageProps> = ({ navigationSlot }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { t } = useI18n();
  const section = resolveSection(location.pathname);
  const [selectedUserId, setSelectedUserId] = React.useState<string | null>(null);
  const [selectedGroupId, setSelectedGroupId] = React.useState<string | null>(null);
  const [candidateViewState, setCandidateViewState] = React.useState<GroupCandidateListViewState>(
    defaultGroupCandidateListViewState,
  );
  const groupMembersGroupId = resolveGroupMembersGroupId(location.pathname);
  const activeGroupId = groupMembersGroupId ?? selectedGroupId;
  const currentUserMode = userListMode(section);
  const currentGroupMode = groupListMode(section);

  const userViewState = React.useMemo(
    () => parseUserListViewState(location.search, currentUserMode),
    [currentUserMode, location.search],
  );
  const groupViewState = React.useMemo(
    () => parseGroupListViewState(location.search, currentGroupMode),
    [currentGroupMode, location.search],
  );
  const memberViewState = React.useMemo(
    () => parseGroupMemberListViewState(location.search),
    [location.search],
  );
  const userQuery = React.useMemo(() => toUserListQuery(userViewState), [userViewState]);
  const groupQuery = React.useMemo(() => toUserGroupListQuery(groupViewState), [groupViewState]);
  const memberQuery = React.useMemo(
    () => toUserGroupMemberListQuery(memberViewState),
    [memberViewState],
  );
  const candidateQuery = React.useMemo(
    () => toUserGroupMemberCandidateListQuery(candidateViewState),
    [candidateViewState],
  );

  React.useEffect(() => {
    setCandidateViewState(defaultGroupCandidateListViewState());
  }, [activeGroupId]);

  const reportError = React.useCallback((error: unknown) => {
    toast({
      variant: 'destructive',
      title: t('userManagement.errors.title'),
      description: t(getUserManagementErrorI18nKey(error)),
    });
  }, [t, toast]);

  const reportBatchFailures = React.useCallback((result: GroupMemberMutationResult) => {
    const firstFailure = result.failedUsers[0];
    if (!firstFailure) {
      return;
    }
    toast({
      variant: 'destructive',
      title: t('userManagement.errors.title'),
      description: t(getUserManagementErrorCodeI18nKey(firstFailure.errorCode)),
    });
  }, [t, toast]);

  const allUsersQuery = useQuery({
    queryKey: userManagementQueryKeys.userList({
      page: 1,
      pageSize: 1,
      sortBy: 'username',
      sortDirection: 'asc',
    }),
    queryFn: () => listAdminUsers({
      page: 1,
      pageSize: 1,
      sortBy: 'username',
      sortDirection: 'asc',
    }),
  });
  const roleIssuesQuery = useQuery({
    queryKey: userManagementQueryKeys.userList({
      roleStatus: 'missing,multiple',
      page: 1,
      pageSize: 1,
      sortBy: 'username',
      sortDirection: 'asc',
    }),
    queryFn: () => listAdminUsers({
      roleStatus: 'missing,multiple',
      page: 1,
      pageSize: 1,
      sortBy: 'username',
      sortDirection: 'asc',
    }),
  });
  const allGroupsQuery = useQuery({
    queryKey: userManagementQueryKeys.groupList({
      page: 1,
      pageSize: 1,
      sortBy: 'name',
      sortDirection: 'asc',
    }),
    queryFn: () => listUserGroups({
      page: 1,
      pageSize: 1,
      sortBy: 'name',
      sortDirection: 'asc',
    }),
  });

  const showUserList = section === 'users' || section === 'roleIssues' || section === 'disabledUsers';
  const showGroupList = section === 'groups' || section === 'emptyGroups';
  const usersQuery = useQuery({
    queryKey: userManagementQueryKeys.userList(userQuery),
    queryFn: () => listAdminUsers(userQuery),
    enabled: showUserList,
    placeholderData: previous => previous,
  });
  const groupsQuery = useQuery({
    queryKey: userManagementQueryKeys.groupList(groupQuery),
    queryFn: () => listUserGroups(groupQuery),
    enabled: showGroupList,
    placeholderData: previous => previous,
  });
  const selectedUserQuery = useQuery({
    queryKey: userManagementQueryKeys.userDetail(selectedUserId ?? ''),
    queryFn: () => getAdminUser(selectedUserId ?? ''),
    enabled: selectedUserId !== null,
  });
  const activeGroupQuery = useQuery({
    queryKey: userManagementQueryKeys.groupDetail(activeGroupId ?? ''),
    queryFn: () => getUserGroup(activeGroupId ?? ''),
    enabled: activeGroupId !== null,
  });
  const groupMembersQuery = useQuery({
    queryKey: userManagementQueryKeys.groupMemberList(activeGroupId ?? '', memberQuery),
    queryFn: () => listUserGroupMembers(activeGroupId ?? '', memberQuery),
    enabled: section === 'groupMembers' && activeGroupId !== null,
    placeholderData: previous => previous,
  });
  const groupCandidatesQuery = useQuery({
    queryKey: userManagementQueryKeys.groupCandidateList(activeGroupId ?? '', candidateQuery),
    queryFn: () => listUserGroupMemberCandidates(activeGroupId ?? '', candidateQuery),
    enabled: section === 'groupMembers' && activeGroupId !== null,
    placeholderData: previous => previous,
  });

  useReportQueryError(usersQuery.error, reportError);
  useReportQueryError(groupsQuery.error, reportError);
  useReportQueryError(selectedUserQuery.error, reportError);
  useReportQueryError(activeGroupQuery.error, reportError);
  useReportQueryError(groupMembersQuery.error, reportError);
  useReportQueryError(groupCandidatesQuery.error, reportError);

  const setUserViewState = React.useCallback((state: UserListViewState) => {
    setSearchParams(userListViewStateToSearchParams(state, currentUserMode), { replace: true });
  }, [currentUserMode, setSearchParams]);
  const setGroupViewState = React.useCallback((state: GroupListViewState) => {
    setSearchParams(groupListViewStateToSearchParams(state, currentGroupMode), { replace: true });
  }, [currentGroupMode, setSearchParams]);
  const setMemberViewState = React.useCallback((state: GroupMemberListViewState) => {
    setSearchParams(groupMemberListViewStateToSearchParams(state), { replace: true });
  }, [setSearchParams]);

  const handleSectionChange = (nextSection: UserManagementSection) => {
    setSelectedUserId(null);
    setSelectedGroupId(null);
    if (nextSection === 'groups') {
      navigate(ROUTES.userManagement.groups);
    } else if (nextSection === 'emptyGroups') {
      navigate(ROUTES.userManagement.emptyGroups);
    } else if (nextSection === 'roleIssues') {
      navigate(ROUTES.userManagement.roleIssues);
    } else if (nextSection === 'disabledUsers') {
      navigate(ROUTES.userManagement.disabledUsers);
    } else {
      navigate(ROUTES.userManagement.users);
    }
  };

  const invalidateUsers = React.useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.users() }),
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groups() }),
    ]);
  }, [queryClient]);

  const invalidateGroup = React.useCallback(async (groupId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groups() }),
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groupDetail(groupId) }),
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groupMembers(groupId) }),
      queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groupCandidates(groupId) }),
    ]);
  }, [queryClient]);

  const runMutation = React.useCallback(async <Result,>(operation: () => Promise<Result>): Promise<Result> => {
    try {
      return await operation();
    } catch (error) {
      reportError(error);
      throw error;
    }
  }, [reportError]);

  const handleAddGroupMembers = async (userIds: string[]) => {
    if (!activeGroupId || userIds.length === 0) {
      return;
    }
    const result = await runMutation(() => addUserGroupMembers(activeGroupId, userIds));
    reportBatchFailures(result);
    await invalidateGroup(activeGroupId);
  };

  const handleRemoveGroupMembers = async (userIds: string[]) => {
    if (!activeGroupId || userIds.length === 0) {
      return;
    }
    const result = await runMutation(() => removeUserGroupMembers(activeGroupId, userIds));
    reportBatchFailures(result);
    await invalidateGroup(activeGroupId);
  };

  const handleCreateGroup = async (request: { name: string; description: string }) => {
    await runMutation(() => createUserGroup({
      name: request.name.trim(),
      description: request.description.trim() || null,
    }));
    await queryClient.invalidateQueries({ queryKey: userManagementQueryKeys.groups() });
    setSelectedUserId(null);
    setSelectedGroupId(null);
  };

  const handleAssignUserRole = async (userId: string, role: PlatformRole) => {
    const nextUser = await runMutation(() => replaceAdminUserRole(userId, role));
    queryClient.setQueryData(userManagementQueryKeys.userDetail(userId), nextUser);
    await invalidateUsers();
    setSelectedUserId(nextUser.id);
  };

  const selectedUser: AdminUser | null = selectedUserQuery.data
    ?? usersQuery.data?.items.find(user => user.id === selectedUserId)
    ?? null;
  const selectedGroup = activeGroupQuery.data
    ?? groupsQuery.data?.items.find(group => group.id === activeGroupId)
    ?? null;

  const main = section === 'groupMembers' && selectedGroup
    ? (
      <GroupMemberWorkbench
        group={selectedGroup}
        members={groupMembersQuery.data?.items ?? []}
        membersTotal={groupMembersQuery.data?.total ?? 0}
        memberViewState={memberViewState}
        onMemberViewStateChange={setMemberViewState}
        candidates={groupCandidatesQuery.data?.items ?? []}
        candidatesTotal={groupCandidatesQuery.data?.total ?? 0}
        candidateViewState={candidateViewState}
        onCandidateViewStateChange={setCandidateViewState}
        onAddMembers={handleAddGroupMembers}
        onRemoveMembers={handleRemoveGroupMembers}
        onBack={() => navigate(ROUTES.userManagement.groups)}
      />
    )
    : showGroupList
      ? (
        <GroupListPanel
          groups={groupsQuery.data?.items ?? []}
          total={groupsQuery.data?.total ?? 0}
          allGroupsTotal={allGroupsQuery.data?.total ?? 0}
          mode={currentGroupMode}
          viewState={groupViewState}
          onViewStateChange={setGroupViewState}
          selectedGroupId={selectedGroupId}
          onSelectGroup={group => {
            setSelectedUserId(null);
            setSelectedGroupId(group.id);
          }}
          onCreateGroup={handleCreateGroup}
        />
      )
      : (
        <UserListPanel
          users={usersQuery.data?.items ?? []}
          total={usersQuery.data?.total ?? 0}
          allUsersTotal={allUsersQuery.data?.total ?? 0}
          mode={currentUserMode}
          viewState={userViewState}
          onViewStateChange={setUserViewState}
          selectedUserId={selectedUserId}
          onSelectUser={user => {
            setSelectedGroupId(null);
            setSelectedUserId(user.id);
          }}
        />
      );

  const detail = selectedUser
    ? (
      <UserDetailPanel
        user={selectedUser}
        onAssignRole={handleAssignUserRole}
      />
    )
    : selectedGroup && section !== 'groupMembers'
      ? (
        <GroupDetailPanel
          group={selectedGroup}
          onManageMembers={() => navigate(ROUTES.userManagement.groupMembers(selectedGroup.id))}
        />
      )
      : undefined;
  const detailTitle = selectedUser
    ? getAdminUserDisplayName(selectedUser)
    : section !== 'groupMembers'
      ? selectedGroup?.name
      : undefined;
  const detailIcon = selectedUser ? User : UsersRound;

  return (
    <UserManagementShell
      navigationSlot={navigationSlot}
      activeSection={section}
      onSectionChange={handleSectionChange}
      usersCount={allUsersQuery.data?.total ?? 0}
      roleIssuesCount={roleIssuesQuery.data?.total ?? 0}
      groupsCount={allGroupsQuery.data?.total ?? 0}
      main={main}
      detail={detail}
      detailTitle={detailTitle}
      detailIcon={detailIcon}
    />
  );
};
