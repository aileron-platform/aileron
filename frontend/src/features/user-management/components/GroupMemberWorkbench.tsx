import React from 'react';
import { ArrowLeft, Search, UserMinus, UserPlus, UsersRound } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  AccountState,
  GroupMemberCandidate,
  PlatformRole,
  UserGroup,
  UserGroupMember,
} from '../api/userManagementTypes';
import {
  defaultGroupMemberListViewState,
  resetPage,
  type GroupCandidateListViewState,
  type GroupMemberListViewState,
  type MemberAccountStateFilter,
  type MemberSort,
} from '../model/userManagementQueryModel';
import {
  getAdminUserDisplayName,
  PLATFORM_ROLES,
} from '../model/userManagementUserModel';
import { ListFilterBar } from './ListFilterBar';
import { ListPagination } from './ListPagination';

interface GroupMemberWorkbenchProps {
  group: UserGroup;
  members: UserGroupMember[];
  membersTotal: number;
  memberViewState: GroupMemberListViewState;
  onMemberViewStateChange: (state: GroupMemberListViewState) => void;
  candidates: GroupMemberCandidate[];
  candidatesTotal: number;
  candidateViewState: GroupCandidateListViewState;
  onCandidateViewStateChange: (state: GroupCandidateListViewState) => void;
  onAddMembers: (userIds: string[]) => Promise<void>;
  onRemoveMembers: (userIds: string[]) => Promise<void>;
  onBack?: () => void;
}

export const GroupMemberWorkbench: React.FC<GroupMemberWorkbenchProps> = ({
  group,
  members,
  membersTotal,
  memberViewState,
  onMemberViewStateChange,
  candidates,
  candidatesTotal,
  candidateViewState,
  onCandidateViewStateChange,
  onAddMembers,
  onRemoveMembers,
  onBack,
}) => {
  const { t } = useI18n();
  const [selectedMemberIds, setSelectedMemberIds] = React.useState<string[]>([]);
  const [selectedCandidateIds, setSelectedCandidateIds] = React.useState<string[]>([]);
  const [addDialogOpen, setAddDialogOpen] = React.useState(false);

  const selectableAutocompleteCandidates = React.useMemo(
    () => candidates.filter(candidate => candidate.enabled && candidate.roleStatus === 'valid').slice(0, 6),
    [candidates],
  );

  const updateMemberQuery = (patch: Partial<GroupMemberListViewState>) => {
    onMemberViewStateChange(resetPage(memberViewState, patch));
  };

  const updateCandidateQuery = (patch: Partial<GroupCandidateListViewState>) => {
    onCandidateViewStateChange(resetPage(candidateViewState, patch));
  };

  const toggleMember = (userId: string, checked: boolean) => {
    setSelectedMemberIds(current => (
      checked ? [...current, userId] : current.filter(id => id !== userId)
    ));
  };

  const toggleCandidate = (userId: string, checked: boolean) => {
    setSelectedCandidateIds(current => (
      checked ? [...current, userId] : current.filter(id => id !== userId)
    ));
  };

  const selectCandidate = (userId: string) => {
    setSelectedCandidateIds(current => (
      current.includes(userId) ? current : [...current, userId]
    ));
    updateCandidateQuery({ q: '' });
  };

  const handleCandidateSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter' || selectableAutocompleteCandidates.length === 0) {
      return;
    }
    event.preventDefault();
    selectCandidate(selectableAutocompleteCandidates[0].userId);
  };

  const handleAddMembers = async () => {
    try {
      await onAddMembers(selectedCandidateIds);
      setSelectedCandidateIds([]);
      updateCandidateQuery({ q: '' });
      setAddDialogOpen(false);
    } catch {
      // The page reports the localized API error.
    }
  };

  const handleRemoveMembers = async () => {
    try {
      await onRemoveMembers(selectedMemberIds);
      setSelectedMemberIds([]);
    } catch {
      // The page reports the localized API error.
    }
  };

  const memberFiltersApplied = memberViewState.role !== 'all'
    || memberViewState.accountState !== 'all'
    || memberViewState.source !== 'all';

  return (
    <section className="flex h-full min-h-0 flex-col">
      <FeatureHeader
        title={group.name}
        icon={UsersRound}
        breadcrumbs={[t('userManagement.navigation.title'), t('userManagement.groups.title')]}
        info={(
          <div className="flex min-w-0 items-center gap-2">
            <Badge variant="secondary" className="shrink-0 gap-1">
              <UsersRound className="h-3 w-3" />
              {group.memberCount}
            </Badge>
            {group.description ? (
              <span className="truncate text-xs text-muted-foreground">{group.description}</span>
            ) : null}
          </div>
        )}
        actions={(
          <>
            {onBack ? (
              <Button type="button" size="sm" variant="outline" className="h-7 gap-1 px-2 text-xs" onClick={onBack}>
                <ArrowLeft className="h-3.5 w-3.5" />
                {t('userManagement.groups.actions.backToGroups')}
              </Button>
            ) : null}
            <Button type="button" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={() => setAddDialogOpen(true)}>
              <UserPlus className="h-3.5 w-3.5" />
              {t('userManagement.groups.actions.addMember')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1 px-2 text-xs"
              disabled={selectedMemberIds.length === 0}
              onClick={() => void handleRemoveMembers()}
            >
              <UserMinus className="h-3.5 w-3.5" />
              {t('userManagement.groups.actions.removeSelectedMembers')}
            </Button>
          </>
        )}
      />

      <ListFilterBar
        searchLabel="userManagement.groups.members.searchLabel"
        searchPlaceholder="userManagement.groups.members.searchPlaceholder"
        query={memberViewState.q}
        onQueryChange={q => updateMemberQuery({ q })}
        selectFilters={[
          {
            id: 'role',
            labelKey: 'userManagement.filters.role',
            value: memberViewState.role,
            onChange: value => updateMemberQuery({ role: value as 'all' | PlatformRole }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              ...PLATFORM_ROLES.map(role => ({
                value: role,
                labelKey: `userManagement.roles.${role}`,
              })),
            ],
          },
          {
            id: 'accountState',
            labelKey: 'userManagement.filters.accountState',
            value: memberViewState.accountState,
            onChange: value => updateMemberQuery({ accountState: value as MemberAccountStateFilter }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
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
            id: 'source',
            labelKey: 'userManagement.filters.source',
            value: memberViewState.source,
            onChange: value => updateMemberQuery({ source: value as 'all' | 'manual' }),
            options: [
              { value: 'all', labelKey: 'userManagement.filters.all' },
              { value: 'manual', labelKey: 'userManagement.filters.sourceValue.manual' },
            ],
          },
        ]}
        sortOptions={[
          { value: 'usernameAsc', labelKey: 'userManagement.sort.members.usernameAsc' },
          { value: 'emailAsc', labelKey: 'userManagement.sort.members.emailAsc' },
          { value: 'joinedDesc', labelKey: 'userManagement.sort.members.joinedDesc' },
          { value: 'updatedDesc', labelKey: 'userManagement.sort.members.updatedDesc' },
        ]}
        sortValue={memberViewState.sort}
        onSortChange={value => updateMemberQuery({ sort: value as MemberSort })}
        hasAppliedFilters={memberFiltersApplied}
        resultLabelKey="userManagement.filters.summary"
        resultCount={membersTotal}
        totalCount={group.memberCount}
        onClearAll={() => {
          const defaults = defaultGroupMemberListViewState();
          onMemberViewStateChange({
            ...defaults,
            sort: memberViewState.sort,
            pageSize: memberViewState.pageSize,
          });
        }}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {members.map(member => {
          const checkboxId = `group-member-${member.userId}`;
          return (
            <div key={member.userId} className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <Checkbox
                  id={checkboxId}
                  checked={selectedMemberIds.includes(member.userId)}
                  onCheckedChange={checked => toggleMember(member.userId, checked === true)}
                />
                <label htmlFor={checkboxId} className="min-w-0 cursor-pointer">
                  <div className="truncate text-sm font-medium">{getAdminUserDisplayName(member)}</div>
                  <div className="truncate text-xs text-muted-foreground">{member.email ?? member.username}</div>
                </label>
              </div>
              <Badge variant="outline" className="shrink-0">
                {member.role ? t(`userManagement.roles.${member.role}`) : t('userManagement.roles.none')}
              </Badge>
            </div>
          );
        })}
      </div>

      <div className="flex shrink-0 items-center justify-between border-t">
        <span className="px-3 text-xs text-muted-foreground">
          {t('userManagement.groups.selection.count', { count: selectedMemberIds.length })}
        </span>
        <ListPagination
          page={memberViewState.page}
          pageSize={memberViewState.pageSize}
          total={membersTotal}
          onPageChange={page => onMemberViewStateChange({ ...memberViewState, page })}
          onPageSizeChange={nextPageSize => updateMemberQuery({ pageSize: nextPageSize })}
        />
      </div>

      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-2xl p-0">
          <div className="p-6 pb-0">
            <DialogHeader>
              <DialogHeading icon={UserPlus}>
                {t('userManagement.groups.addUsers.title')}
              </DialogHeading>
              <DialogDescription>{t('userManagement.groups.addUsers.description')}</DialogDescription>
            </DialogHeader>
          </div>

          <div className="border-y bg-muted/20 px-4 py-3">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={candidateViewState.q}
                onChange={event => updateCandidateQuery({ q: event.target.value })}
                onKeyDown={handleCandidateSearchKeyDown}
                className="h-8 pl-8 text-xs"
                placeholder={t('userManagement.groups.addUsers.searchPlaceholder')}
                aria-label={t('userManagement.groups.addUsers.searchLabel')}
              />
              {candidateViewState.q.trim() && selectableAutocompleteCandidates.length > 0 ? (
                <div
                  role="listbox"
                  className="absolute left-0 right-0 top-10 z-10 overflow-hidden rounded-md border bg-popover shadow-md"
                >
                  {selectableAutocompleteCandidates.map(candidate => (
                    <button
                      key={candidate.userId}
                      type="button"
                      role="option"
                      aria-selected={selectedCandidateIds.includes(candidate.userId)}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent focus:bg-accent focus:outline-none"
                      onClick={() => selectCandidate(candidate.userId)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{getAdminUserDisplayName(candidate)}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {candidate.email ?? candidate.username}
                        </span>
                      </span>
                      <Badge variant="outline" className="shrink-0">
                        {candidate.role ? t(`userManagement.roles.${candidate.role}`) : t('userManagement.roles.none')}
                      </Badge>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="max-h-[420px] overflow-y-auto">
            {candidates.map(candidate => {
              const checkboxId = `group-candidate-${candidate.userId}`;
              const disabled = !candidate.enabled || candidate.roleStatus !== 'valid';
              return (
                <div key={candidate.userId} className="flex items-center justify-between gap-2 border-b px-4 py-3 last:border-b-0">
                  <div className="flex min-w-0 items-center gap-3">
                    <Checkbox
                      id={checkboxId}
                      checked={selectedCandidateIds.includes(candidate.userId)}
                      disabled={disabled}
                      onCheckedChange={checked => toggleCandidate(candidate.userId, checked === true)}
                    />
                    <label htmlFor={checkboxId} className="min-w-0 cursor-pointer">
                      <div className="truncate text-sm font-medium">{getAdminUserDisplayName(candidate)}</div>
                      <div className="truncate text-xs text-muted-foreground">{candidate.email ?? candidate.username}</div>
                    </label>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge variant="outline">
                      {candidate.role ? t(`userManagement.roles.${candidate.role}`) : t('userManagement.roles.none')}
                    </Badge>
                    <Badge variant={disabled ? 'outline' : 'secondary'}>
                      {t(`userManagement.groups.membership.${candidate.membershipStatus}`)}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>

          <ListPagination
            page={candidateViewState.page}
            pageSize={candidateViewState.pageSize}
            total={candidatesTotal}
            onPageChange={page => onCandidateViewStateChange({ ...candidateViewState, page })}
            onPageSizeChange={nextPageSize => updateCandidateQuery({ pageSize: nextPageSize })}
          />

          <DialogFooter className="border-t px-4 py-3">
            <div className="flex flex-1 items-center text-xs text-muted-foreground">
              {t('userManagement.groups.selection.count', { count: selectedCandidateIds.length })}
            </div>
            <Button type="button" variant="outline" onClick={() => setAddDialogOpen(false)}>
              {t('userManagement.groups.addUsers.actions.cancel')}
            </Button>
            <Button
              type="button"
              disabled={selectedCandidateIds.length === 0}
              onClick={() => void handleAddMembers()}
            >
              {t('userManagement.groups.actions.addSelectedMembers')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
};
