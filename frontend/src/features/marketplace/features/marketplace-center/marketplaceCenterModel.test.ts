import { describe, expect, it } from 'vitest';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import {
  buildMarketplaceListQuery,
  resolveImportedPackageRevealFilters,
  toggleMarketplaceFeature,
  translateMarketplaceMessage,
} from './marketplaceCenterModel';

const createPackage = (
  targetClient: MarketplacePackageSummary['targetClient'],
  packageId: string,
): MarketplacePackageSummary => ({
  targetClient,
  packageType: 'plugin',
  packageId,
  displayName: packageId,
  version: '1.0.0',
  description: `${packageId} description`,
  category: 'coding',
  tags: [],
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: `${targetClient}/plugins/${packageId}`,
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [],
});

describe('marketplaceCenterModel', () => {
  it('builds marketplace list queries from current filters and overrides', () => {
    const query = buildMarketplaceListQuery(
      {
        searchTerm: 'figma',
        targetClient: 'codex',
        category: 'coding',
        activeFeatures: new Set(['mcp', 'skills']),
        page: 3,
        pageSize: 24,
      },
      {
        q: '',
        targetClient: 'all',
        features: [],
        page: 1,
      },
    );

    expect(query).toEqual({
      q: '',
      targetClient: 'all',
      category: 'coding',
      features: [],
      sort: 'updatedAt',
      direction: 'desc',
      page: 1,
      pageSize: 24,
    });
  });

  it('toggles marketplace feature sets without mutating the original set', () => {
    const current = new Set(['mcp'] as const);

    const removed = toggleMarketplaceFeature(current, 'mcp');
    const added = toggleMarketplaceFeature(current, 'skills');

    expect(Array.from(current)).toEqual(['mcp']);
    expect(Array.from(removed)).toEqual([]);
    expect(Array.from(added)).toEqual(['mcp', 'skills']);
  });

  it('reveals imported packages by selecting a single imported targetClient', () => {
    expect(resolveImportedPackageRevealFilters({
      imported: [createPackage('claude-code', 'review-assistant')],
      failed: [],
      warnings: [],
    })).toEqual({
      q: '',
      targetClient: 'claude-code',
      category: 'all',
      features: [],
      page: 1,
    });
  });

  it('reveals mixed-targetClient imports with the all-targetClient filter', () => {
    expect(resolveImportedPackageRevealFilters({
      imported: [
        createPackage('claude-code', 'review-assistant'),
        createPackage('codex', 'figma-context'),
      ],
      failed: [],
      warnings: [],
    })).toEqual({
      q: '',
      targetClient: 'all',
      category: 'all',
      features: [],
      page: 1,
    });
  });

  it('keeps marketplace i18n keys translated and non-keys unchanged', () => {
    const t = (key: string, params?: Record<string, unknown>) => `${key}:${params?.code ?? 'none'}`;

    expect(translateMarketplaceMessage(t, 'marketplace.import.failed', { code: 'E_IMPORT' })).toBe(
      'marketplace.import.failed:E_IMPORT',
    );
    expect(translateMarketplaceMessage(t, 'marketplace.import.validation.clone_failed')).toBe(
      'marketplace.import.validation.cloneFailed:none',
    );
    expect(translateMarketplaceMessage(t, 'raw CLI error')).toBe(
      'marketplace.errors.unknown:none',
    );
  });
});
