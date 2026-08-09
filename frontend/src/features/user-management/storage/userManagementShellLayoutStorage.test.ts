import { beforeEach, describe, expect, it } from 'vitest';
import {
  USER_MANAGEMENT_LAYOUT_ENTITY_ID,
  USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS,
  userManagementShellLayoutStorage,
} from './userManagementShellLayoutStorage';

describe('userManagementShellLayoutStorage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('clamps persisted width to the User Management limit', () => {
    userManagementShellLayoutStorage.save(USER_MANAGEMENT_LAYOUT_ENTITY_ID, {
      ...USER_MANAGEMENT_SHELL_LAYOUT_DEFAULTS,
      navSidebarWidth: 9000,
    });

    expect(userManagementShellLayoutStorage.load(USER_MANAGEMENT_LAYOUT_ENTITY_ID)?.navSidebarWidth).toBe(600);
  });
});
