import { describe, expect, it } from 'vitest';
import {
  resolveMarketplacePermissions,
  type MarketplaceActionPermissions,
} from './marketplacePermissions';

const noPermissions: MarketplaceActionPermissions = {
  canEdit: false,
  canDelete: false,
  canExport: false,
  canInstall: false,
  canManageRegistry: false,
};

describe('resolveMarketplacePermissions', () => {
  it('fails closed without a valid platform role', () => {
    expect(resolveMarketplacePermissions(null)).toEqual(noPermissions);
  });

  it('allows a member to browse, export, and install only', () => {
    expect(resolveMarketplacePermissions('member')).toEqual({
      ...noPermissions,
      canExport: true,
      canInstall: true,
    });
  });

  it('allows an admin to manage canonical content and registry', () => {
    expect(resolveMarketplacePermissions('admin')).toEqual({
      canEdit: true,
      canDelete: true,
      canExport: true,
      canInstall: true,
      canManageRegistry: true,
    });
  });
});
