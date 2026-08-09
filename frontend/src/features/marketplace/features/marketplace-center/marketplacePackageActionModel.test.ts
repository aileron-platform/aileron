import { describe, expect, it } from 'vitest';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import {
  buildMarketplaceDeleteRequest,
  buildMarketplaceExportRequest,
  getMarketplaceActionTextKeys,
  isMarketplaceDeleteBlocked,
} from './marketplacePackageActionModel';

const packageSummary: MarketplacePackageSummary = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'figma-context',
  displayName: 'Figma Context',
  version: '0.1.0',
  description: 'Figma context plugin.',
  category: 'coding',
  tags: ['mcp'],
  sourceType: 'created',
  indexedResourceNames: ['mcp'],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [],
};

describe('marketplacePackageActionModel', () => {
  it('builds export and delete requests from package action context', () => {
    expect(buildMarketplaceExportRequest(packageSummary)).toEqual({
      provider: 'codex',
      packageId: 'figma-context',
      revision: 'rev-1',
    });
    expect(buildMarketplaceDeleteRequest(packageSummary)).toEqual({
      provider: 'codex',
      packageId: 'figma-context',
      revision: 'rev-1',
    });
  });

  it('blocks delete actions until the package id is typed exactly', () => {
    expect(isMarketplaceDeleteBlocked('export', '', packageSummary.packageId)).toBe(false);
    expect(isMarketplaceDeleteBlocked('delete', '', packageSummary.packageId)).toBe(true);
    expect(isMarketplaceDeleteBlocked('delete', 'Figma-Context', packageSummary.packageId)).toBe(true);
    expect(isMarketplaceDeleteBlocked('delete', packageSummary.packageId, packageSummary.packageId)).toBe(false);
  });

  it('resolves localized action text keys by action type', () => {
    expect(getMarketplaceActionTextKeys('export')).toEqual({
      titleKey: 'marketplace.export.title',
      descriptionKey: 'marketplace.export.description',
      resultFailedKey: 'marketplace.export.result.failed',
      actionKey: 'marketplace.export.actions.export',
    });
    expect(getMarketplaceActionTextKeys('delete')).toEqual({
      titleKey: 'marketplace.delete.title',
      descriptionKey: 'marketplace.delete.description',
      resultFailedKey: 'marketplace.delete.result.failed',
      actionKey: 'marketplace.delete.actions.delete',
    });
  });

});
