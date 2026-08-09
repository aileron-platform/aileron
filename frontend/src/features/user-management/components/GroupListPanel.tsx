import React from 'react';
import { Plus, UsersRound } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import type { UserGroup } from '../api/userManagementTypes';
import {
  defaultGroupListViewState,
  resetPage,
  type GroupDescriptionFilter,
  type GroupListMode,
  type GroupListViewState,
  type GroupMemberCountFilter,
  type GroupSort,
  type GroupUpdatedFilter,
} from '../model/userManagementQueryModel';
import {
  CreateUserGroupDialog,
  type CreateUserGroupRequest,
} from './CreateUserGroupDialog';
import { ListFilterBar } from './ListFilterBar';
import { ListPagination } from './ListPagination';

interface GroupListPanelProps {
  groups: UserGroup[];
  total: number;
  allGroupsTotal: number;
  selectedGroupId: string | null;
  onSelectGroup: (group: UserGroup) => void;
  onCreateGroup: (request: CreateUserGroupRequest) => Promise<void>;
  mode: GroupListMode;
  viewState: GroupListViewState;
  onViewStateChange: (state: GroupListViewState) => void;
}

export const GroupListPanel: React.FC<GroupListPanelProps> = ({
  groups,
  total,
  allGroupsTotal,
  selectedGroupId,
  onSelectGroup,
  onCreateGroup,
  mode,
  viewState,
  onViewStateChange,
}) => {
  const { t } = useI18n();
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);

  const updateQuery = (patch: Partial<GroupListViewState>) => {
    onViewStateChange(resetPage(viewState, patch));
  };

  const hasAppliedFilters = viewState.memberCount !== 'all'
    || viewState.description !== 'all'
    || viewState.updated !== 'all';

  const clearFilters = () => {
    const defaults = defaultGroupListViewState(mode);
    onViewStateChange({
      ...defaults,
      sort: viewState.sort,
      pageSize: viewState.pageSize,
    });
  };

  return (
    <section className="flex h-full min-h-0 flex-col">
      <FeatureHeader
        title={t('userManagement.groups.title')}
        icon={UsersRound}
        breadcrumbs={[t('userManagement.navigation.title')]}
        info={(
          <p className="truncate text-xs text-muted-foreground">
            {t('userManagement.groups.count', { count: total })}
          </p>
        )}
        actions={(
          <Button type="button" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={() => setCreateDialogOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            {t('userManagement.groups.actions.create')}
          </Button>
        )}
      />
      <CreateUserGroupDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={onCreateGroup}
      />

      <ListFilterBar
        searchLabel="userManagement.groups.searchLabel"
        searchPlaceholder="userManagement.groups.searchPlaceholder"
        query={viewState.q}
        onQueryChange={q => updateQuery({ q })}
        selectFilters={[
          {
            id: 'memberCount',
            labelKey: 'userManagement.filters.memberCount',
            value: viewState.memberCount,
            onChange: value => updateQuery({ memberCount: value as GroupMemberCountFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: 'empty', labelKey: 'userManagement.filters.memberCountRange.empty' },
              { value: 'small', labelKey: 'userManagement.filters.memberCountRange.small' },
              { value: 'large', labelKey: 'userManagement.filters.memberCountRange.large' },
            ],
          },
          {
            id: 'description',
            labelKey: 'userManagement.filters.hasDescription',
            value: viewState.description,
            onChange: value => updateQuery({ description: value as GroupDescriptionFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: 'withDescription', labelKey: 'userManagement.filters.description.withDescription' },
              { value: 'withoutDescription', labelKey: 'userManagement.filters.description.withoutDescription' },
            ],
          },
          {
            id: 'updated',
            labelKey: 'userManagement.filters.updatedWithinDays',
            value: viewState.updated,
            onChange: value => updateQuery({ updated: value as GroupUpdatedFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: '7d', labelKey: 'userManagement.filters.updated.7d' },
              { value: '30d', labelKey: 'userManagement.filters.updated.30d' },
            ],
          },
        ]}
        sortOptions={[
          { value: 'nameAsc', labelKey: 'userManagement.sort.groups.nameAsc' },
          { value: 'membersDesc', labelKey: 'userManagement.sort.groups.membersDesc' },
          { value: 'updatedDesc', labelKey: 'userManagement.sort.groups.updatedDesc' },
        ]}
        sortValue={viewState.sort}
        onSortChange={value => updateQuery({ sort: value as GroupSort })}
        hasAppliedFilters={hasAppliedFilters}
        resultLabelKey="userManagement.filters.summary"
        resultCount={total}
        totalCount={allGroupsTotal}
        onClearAll={clearFilters}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {groups.map(group => (
          <button
            key={group.id}
            type="button"
            className={`flex w-full flex-col gap-2 border-b px-4 py-3 text-left transition-colors hover:bg-muted/50 ${
              selectedGroupId === group.id ? 'bg-primary/5' : ''
            }`}
            aria-label={group.name}
            onClick={() => onSelectGroup(group)}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{group.name}</div>
                {group.description ? (
                  <div className="truncate text-xs text-muted-foreground">{group.description}</div>
                ) : null}
              </div>
              <Badge variant="secondary" className="shrink-0 gap-1">
                <UsersRound className="h-3 w-3" />
                {group.memberCount}
              </Badge>
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
