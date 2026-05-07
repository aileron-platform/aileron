import type { MarketplacePermission } from '@/shared/types/marketplace';

export type MarketplacePermissionState = Partial<Record<MarketplacePermission, boolean>>;

export interface MarketplaceActionPermissions {
  canView: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canExport: boolean;
  canImport: boolean;
  canInstall: boolean;
  canManageRegistry: boolean;
}

const defaultPermissionState: Required<MarketplacePermissionState> = {
  'marketplace.view': true,
  'marketplace.edit': true,
  'marketplace.delete': true,
  'marketplace.export': true,
  'marketplace.import': true,
  'marketplace.install': true,
  'marketplace.registry.manage': true,
};

export const resolveMarketplacePermissions = (
  permissions: MarketplacePermissionState = defaultPermissionState,
): MarketplaceActionPermissions => {
  const has = (permission: MarketplacePermission) => permissions[permission] ?? defaultPermissionState[permission];

  return {
    canView: has('marketplace.view'),
    canEdit: has('marketplace.edit'),
    canDelete: has('marketplace.delete'),
    canExport: has('marketplace.export'),
    canImport: has('marketplace.import'),
    canInstall: has('marketplace.install'),
    canManageRegistry: has('marketplace.registry.manage'),
  };
};
