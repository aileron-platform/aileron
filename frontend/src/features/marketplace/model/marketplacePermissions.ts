import type { PlatformRole } from '@/features/auth/public';

export interface MarketplaceActionPermissions {
  canEdit: boolean;
  canDelete: boolean;
  canExport: boolean;
  canImport: boolean;
  canInstall: boolean;
  canManageRegistry: boolean;
}

export type MarketplacePackageAction = 'install' | 'export' | 'delete';

export const canRunMarketplacePackageAction = (
  action: MarketplacePackageAction,
  permissions: MarketplaceActionPermissions,
): boolean => {
  if (action === 'install') return permissions.canInstall;
  if (action === 'delete') return permissions.canDelete;
  return permissions.canExport;
};

export const resolveMarketplacePermissions = (
  platformRole: PlatformRole | null,
): MarketplaceActionPermissions => {
  const isMember = platformRole === 'member' || platformRole === 'admin';
  const isAdmin = platformRole === 'admin';
  return {
    canEdit: isAdmin,
    canDelete: isAdmin,
    canExport: isMember,
    canImport: isAdmin,
    canInstall: isMember,
    canManageRegistry: isAdmin,
  };
};
