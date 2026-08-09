import { ApiError } from '@/shared/api/apiClient';
import type { MarketplaceProvider } from './marketplaceTypes';

export const getMarketplaceInstallCommandName = (
  provider: MarketplaceProvider,
  t: (key: string) => string,
) => t(`marketplace.install.commandNames.${provider}`);

export const getMarketplaceErrorCode = (err: unknown, fallback: string) => (
  err instanceof ApiError
    ? (err.errorCode ?? fallback)
    : fallback
);

export type MarketplacePackageActionType =
  | 'export'
  | 'delete';

const PACKAGE_ACTION_ERROR_KEYS: Record<string, string> = {
  'marketplace.package.not_found': 'marketplace.errors.packageNotFound',
  'marketplace.package.path_escape': 'marketplace.errors.packagePathInvalid',
  'marketplace.package.revision_conflict':
    'marketplace.install.errors.packageRevisionConflict',
  'marketplace.permission.denied': 'marketplace.errors.permission.denied',
};

const EXPORT_ERROR_KEYS: Record<string, string> = {
  'marketplace.package.symlink_rejected':
    'marketplace.export.errors.symlinkRejected',
  'marketplace.validation.required_manifest_missing':
    'marketplace.export.errors.validationFailed',
  'marketplace.validation.invalid_manifest_shape':
    'marketplace.export.errors.validationFailed',
  'marketplace.validation.package_identity_mismatch':
    'marketplace.export.errors.validationFailed',
  'marketplace.validation.metadata_conflict':
    'marketplace.export.errors.validationFailed',
  'marketplace.validation.invalid_package_id':
    'marketplace.export.errors.validationFailed',
  'marketplace.validation.path_escape':
    'marketplace.export.errors.validationFailed',
};

export const getMarketplacePackageActionErrorKey = (
  action: MarketplacePackageActionType,
  errorCode: string | null | undefined,
): string => {
  if (!errorCode) {
    return `marketplace.${action}.result.failed`;
  }
  return (
    PACKAGE_ACTION_ERROR_KEYS[errorCode]
    ?? (action === 'export' ? EXPORT_ERROR_KEYS[errorCode] : undefined)
    ?? `marketplace.${action}.result.failed`
  );
};
