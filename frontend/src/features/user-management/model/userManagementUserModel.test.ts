import { describe, expect, it } from 'vitest';
import type { AdminUser } from '../api/userManagementTypes';
import {
  getAdminUserDisplayName,
  PLATFORM_ROLES,
} from './userManagementUserModel';

const user: AdminUser = {
  id: 'user-1',
  issuer: 'https://issuer.example.com/tenant',
  subject: 'provider-user-1',
  username: 'platform-owner',
  email: 'owner@example.com',
  firstName: 'Amelia',
  lastName: 'Stone',
  enabled: true,
  localActive: true,
  identityEnabled: true,
  accountState: 'active',
  role: 'member',
  roleStatus: 'valid',
  roleIssues: [],
  syncStatus: 'synced',
  createdAt: '2026-07-18T00:00:00.000Z',
  updatedAt: '2026-07-18T00:00:00.000Z',
};

describe('userManagementUserModel', () => {
  it('keeps the platform role order stable', () => {
    expect(PLATFORM_ROLES).toEqual([
      'admin',
      'member',
    ]);
  });

  it('uses the full name with a username fallback', () => {
    expect(getAdminUserDisplayName(user)).toBe('Amelia Stone');
    expect(getAdminUserDisplayName({
      ...user,
      firstName: null,
      lastName: null,
    })).toBe('platform-owner');
  });
});
