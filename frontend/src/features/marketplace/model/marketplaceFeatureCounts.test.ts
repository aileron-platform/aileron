import { describe, expect, it } from 'vitest';

import { getMarketplaceFeatureItemCount } from './marketplaceFeatureCounts';

describe('getMarketplaceFeatureItemCount', () => {
  it('counts feature items by top-level folder when grouped', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'review-main', path: 'skills/review/README.md' },
        { id: 'review-config', path: 'skills/review/config.toml' },
        { id: 'auth', path: 'skills/auth/SKILL.md' },
      ], 'skills'),
    ).toBe(2);
  });

  it('groups by first path segment when resource prefix is omitted', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'review-main', path: 'review/README.md' },
        { id: 'review-config', path: 'review/config.toml' },
        { id: 'auth', path: 'auth/SKILL.md' },
      ], 'skills'),
    ).toBe(2);
  });

  it('falls back to item identifiers when path is not under the expected folder', () => {
    expect(
      getMarketplaceFeatureItemCount([
        { id: 'discord', path: '.mcp.json' },
        { id: 'playwright', path: '.mcp.json' },
      ], 'mcp'),
    ).toBe(2);
  });
});
