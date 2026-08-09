import React from 'react';
import { Users } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import type { AccountState, AdminUser, RoleStatus } from '../api/userManagementTypes';
import {
  defaultUserListViewState,
  resetPage,
  type UserAccountStateFilter,
  type UserListMode,
  type UserListViewState,
  type UserRoleFilter,
  type UserRoleStatusFilter,
  type UserSort,
} from '../model/userManagementQueryModel';
import { getAdminUserDisplayName, PLATFORM_ROLES } from '../model/userManagementUserModel';
import { ListFilterBar } from './ListFilterBar';
import { ListPagination } from './ListPagination';
import { RoleIssueBadge } from './RoleIssueBadge';

interface UserListPanelProps {
  users: AdminUser[];
  total: number;
  allUsersTotal: number;
  selectedUserId: string | null;
  onSelectUser: (user: AdminUser) => void;
  mode: UserListMode;
  viewState: UserListViewState;
  onViewStateChange: (state: UserListViewState) => void;
}

export const UserListPanel: React.FC<UserListPanelProps> = ({
  users,
  total,
  allUsersTotal,
  selectedUserId,
  onSelectUser,
  mode,
  viewState,
  onViewStateChange,
}) => {
  const { t } = useI18n();

  const updateQuery = (patch: Partial<UserListViewState>) => {
    onViewStateChange(resetPage(viewState, patch));
  };

  const hasAppliedFilters = viewState.role !== 'all'
    || viewState.accountState !== 'all'
    || viewState.roleStatus !== 'all';

  const clearFilters = () => {
    const defaults = defaultUserListViewState(mode);
    onViewStateChange({
      ...defaults,
      sort: viewState.sort,
      pageSize: viewState.pageSize,
    });
  };

  return (
    <section className="flex h-full min-h-0 flex-col">
      <FeatureHeader
        title={t('userManagement.users.title')}
        icon={Users}
        breadcrumbs={[t('userManagement.navigation.title')]}
        info={(
          <p className="truncate text-xs text-muted-foreground">
            {t('userManagement.users.count', { count: total })}
          </p>
        )}
      />

      <ListFilterBar
        searchLabel="userManagement.users.searchLabel"
        searchPlaceholder="userManagement.users.searchPlaceholder"
        query={viewState.q}
        onQueryChange={q => updateQuery({ q })}
        selectFilters={[
          {
            id: 'role',
            labelKey: 'userManagement.filters.role',
            value: viewState.role,
            onChange: value => updateQuery({ role: value as UserRoleFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              ...PLATFORM_ROLES.map(role => ({
                value: role,
                labelKey: `userManagement.roles.${role}`,
              })),
              { value: 'none', labelKey: 'userManagement.roles.none' },
            ],
          },
          {
            id: 'accountState',
            labelKey: 'userManagement.filters.accountState',
            value: viewState.accountState,
            onChange: value => updateQuery({ accountState: value as UserAccountStateFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: 'disabled', labelKey: 'userManagement.filters.accountStateValue.disabled' },
              ...([
                'active',
                'local_disabled',
                'identity_disabled',
                'sync_failed',
                'shadow_missing',
              ] satisfies AccountState[]).map(accountState => ({
                value: accountState,
                labelKey: `userManagement.users.accountState.${accountState}`,
              })),
            ],
          },
          {
            id: 'roleStatus',
            labelKey: 'userManagement.filters.roleStatus',
            value: viewState.roleStatus,
            onChange: value => updateQuery({ roleStatus: value as UserRoleStatusFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: 'issue', labelKey: 'userManagement.filters.roleStatusValue.issue' },
              ...(['valid', 'missing', 'multiple'] satisfies RoleStatus[]).map(roleStatus => ({
                value: roleStatus,
                labelKey: roleStatus === 'valid'
                  ? 'userManagement.filters.roleStatusValue.valid'
                  : `userManagement.roleIssues.${roleStatus}`,
              })),
            ],
          },
        ]}
        sortOptions={[
          { value: 'usernameAsc', labelKey: 'userManagement.sort.users.nameAsc' },
          { value: 'createdDesc', labelKey: 'userManagement.sort.users.createdDesc' },
          { value: 'updatedDesc', labelKey: 'userManagement.sort.users.updatedDesc' },
        ]}
        sortValue={viewState.sort}
        onSortChange={value => updateQuery({ sort: value as UserSort })}
        hasAppliedFilters={hasAppliedFilters}
        resultLabelKey="userManagement.filters.summary"
        resultCount={total}
        totalCount={allUsersTotal}
        onClearAll={clearFilters}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {users.map(user => (
          <button
            key={user.id}
            type="button"
            className={`flex w-full flex-col gap-2 border-b px-4 py-3 text-left transition-colors hover:bg-muted/50 ${
              selectedUserId === user.id ? 'bg-primary/5' : ''
            }`}
            aria-label={`${getAdminUserDisplayName(user)} ${user.email ?? user.username}`}
            onClick={() => onSelectUser(user)}
          >
            <div className="flex w-full items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{getAdminUserDisplayName(user)}</div>
                <div className="truncate text-xs text-muted-foreground">{user.email ?? user.username}</div>
              </div>
              <Badge variant={user.enabled ? 'default' : 'outline'} className="shrink-0">
                {t(`userManagement.users.accountState.${user.accountState}`)}
              </Badge>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary">
                {user.role ? t(`userManagement.roles.${user.role}`) : t('userManagement.roles.none')}
              </Badge>
              <RoleIssueBadge user={user} />
            </div>
          </button>
        ))}
      </div>
      <ListPagination
        page={viewState.page}
        pageSize={viewState.pageSize}
        total={total}
        onPageChange={page => onViewStateChange({ ...viewState, page })}
        onPageSizeChange={nextPageSize => updateQuery({ pageSize: nextPageSize })}
      />
    </section>
  );
};
