import { ApiError } from '@/shared/api/apiClient';
import type { MarketplaceTargetClient } from './marketplaceTypes';

export const getMarketplaceInstallCommandName = (
  targetClient: MarketplaceTargetClient,
  t: (key: string) => string,
) => t(`marketplace.install.commandNames.${targetClient}`);

export const getMarketplaceErrorCode = (err: unknown, fallback: string) => (
  err instanceof ApiError
    ? (err.errorCode ?? fallback)
    : fallback
);

export interface MarketplaceInstallErrorContext {
  stage: string;
  source: string | null;
  destination: string | null;
  category: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null
);

export const getMarketplaceInstallErrorContext = (
  err: unknown,
): MarketplaceInstallErrorContext | null => {
  if (!(err instanceof ApiError) || !isRecord(err.responseData)) return null;
  const detail = err.responseData.detail;
  if (!isRecord(detail)) return null;
  if (typeof detail.stage !== 'string' || typeof detail.category !== 'string') {
    return null;
  }
  const source = typeof detail.source === 'string' ? detail.source : null;
  const destination = typeof detail.destination === 'string'
    ? detail.destination
    : null;
  return {
    stage: detail.stage,
    source,
    destination,
    category: detail.category,
  };
};

export type MarketplacePackageActionType =
  | 'export'
  | 'delete';

const PACKAGE_ACTION_ERROR_KEYS: Record<string, string> = {
  'marketplace.package.not_found': 'marketplace.errors.packageNotFound',
  'marketplace.package.path_escape': 'marketplace.errors.packagePathInvalid',
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
