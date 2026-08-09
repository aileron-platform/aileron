import { describe, expect, it } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';
import {
  getMarketplaceErrorCode,
  getMarketplaceInstallCommandName,
  getMarketplacePackageActionErrorKey,
} from './marketplacePackageActionModel';

describe('marketplacePackageActionModel', () => {
  it('resolves localized install command names by provider', () => {
    const t = (key: string) => key;

    expect(getMarketplaceInstallCommandName('codex', t)).toBe('marketplace.install.commandNames.codex');
  });

  it('only preserves structured API error codes and never promotes raw messages', () => {
    expect(getMarketplaceErrorCode(
      new ApiError('request failed', 500, 'marketplace.package.failed'),
      'marketplace.fallback',
    )).toBe('marketplace.package.failed');
    expect(getMarketplaceErrorCode(new Error('runtime failed'), 'marketplace.fallback')).toBe('marketplace.fallback');
    expect(getMarketplaceErrorCode('raw failure', 'marketplace.fallback')).toBe('marketplace.fallback');
    expect(getMarketplaceErrorCode(null, 'marketplace.fallback')).toBe('marketplace.fallback');
  });

  it('maps known package action errors and falls back to localized action errors', () => {
    expect(getMarketplacePackageActionErrorKey(
      'export',
      'marketplace.package.symlink_rejected',
    )).toBe('marketplace.export.errors.symlinkRejected');
    expect(getMarketplacePackageActionErrorKey(
      'delete',
      'marketplace.package.revision_conflict',
    )).toBe('marketplace.install.errors.packageRevisionConflict');
    expect(getMarketplacePackageActionErrorKey(
      'delete',
      'marketplace.package.path_escape',
    )).toBe('marketplace.errors.packagePathInvalid');
    expect(getMarketplacePackageActionErrorKey(
      'export',
      'runtime leaked secret',
    )).toBe('marketplace.export.result.failed');
  });
});
