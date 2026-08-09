import { describe, expect, it } from 'vitest';

import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { getMarketplaceDetailFeatureItems } from './marketplaceDetailNavigationModel';

describe('getMarketplaceDetailFeatureItems', () => {
  it('builds navigation without reading resource content from the overview', () => {
    const detail = {
      provider: 'codex',
    } as MarketplacePackageDetail;

    const items = getMarketplaceDetailFeatureItems(detail, key => key);

    expect(items.find(item => item.id === 'skills')?.count).toBe(0);
    expect(items.map(item => item.id)).toContain('readme');
    expect(items.map(item => item.id)).not.toContain('output-style');
  });
});
