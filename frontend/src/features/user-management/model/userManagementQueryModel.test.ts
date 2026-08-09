import { describe, expect, it } from 'vitest';
import {
  defaultGroupCandidateListViewState,
  defaultGroupListViewState,
  defaultGroupMemberListViewState,
  defaultUserListViewState,
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
} from './userManagementQueryModel';

describe('userManagementQueryModel', () => {
  it('omits default user query values from the URL but keeps a complete backend query', () => {
    const state = defaultUserListViewState('all');

    expect(userListViewStateToSearchParams(state, 'all').toString()).toBe('');
    expect(toUserListQuery(state)).toEqual({
      page: 1,
      pageSize: 25,
      sortBy: 'username',
      sortDirection: 'asc',
    });
  });

  it('normalizes route presets and supported user filters', () => {
    const roleIssues = parseUserListViewState('', 'roleIssues');
    expect(toUserListQuery(roleIssues)).toEqual(expect.objectContaining({
      roleStatus: 'missing,multiple',
    }));

    const disabled = parseUserListViewState('?q=%20Amelia%20&role=admin&page=2&pageSize=50', 'disabled');
    expect(disabled.q).toBe('Amelia');
    expect(toUserListQuery(disabled)).toEqual({
      q: 'Amelia',
      role: 'admin',
      accountState: 'local_disabled,identity_disabled',
      page: 2,
      pageSize: 50,
      sortBy: 'username',
      sortDirection: 'asc',
    });
  });

  it('resets unsupported URL values to canonical defaults', () => {
    const state = parseUserListViewState('?page=0&pageSize=500&role=owner&sort=emailAsc', 'all');

    expect(state).toEqual(defaultUserListViewState('all'));
  });

  it('maps group list filters to the documented server contract', () => {
    const state = parseGroupListViewState(
      '?q=platform&memberCount=small&description=withDescription&updated=7d&sort=membersDesc&page=3',
      'all',
    );

    expect(toUserGroupListQuery(state)).toEqual({
      q: 'platform',
      memberCountRange: '1_10',
      hasDescription: true,
      updatedWithinDays: 7,
      page: 3,
      pageSize: 25,
      sortBy: 'memberCount',
      sortDirection: 'desc',
    });
    expect(groupListViewStateToSearchParams(defaultGroupListViewState('all'), 'all').toString())
      .toBe('');
  });

  it('maps member and candidate filters without local list filtering', () => {
    const memberState = parseGroupMemberListViewState(
      '?q=amelia&role=member&accountState=active&source=manual&sort=joinedDesc&pageSize=100',
    );
    expect(toUserGroupMemberListQuery(memberState)).toEqual({
      q: 'amelia',
      role: 'member',
      accountState: 'active',
      source: 'manual',
      page: 1,
      pageSize: 100,
      sortBy: 'joinedAt',
      sortDirection: 'desc',
    });
    expect(groupMemberListViewStateToSearchParams(defaultGroupMemberListViewState()).toString())
      .toBe('');

    expect(toUserGroupMemberCandidateListQuery({
      ...defaultGroupCandidateListViewState(),
      roleStatus: 'issue',
    })).toEqual({
      membership: 'not_member',
      roleStatus: 'missing,multiple',
      page: 1,
      pageSize: 25,
      sortBy: 'username',
      sortDirection: 'asc',
    });
  });
});
