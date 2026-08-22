import { describe, expect, it } from 'vitest';

import type { MarketplacePackageSummary } from './marketplaceTypes';
import {
  getMarketplaceFeatureLabelKey,
  getMarketplacePackageFeatures,
} from './marketplaceFeatureLabels';

const packageSummary: MarketplacePackageSummary = {
  targetClient: 'codex',
  packageType: 'plugin',
  packageId: 'figma',
  displayName: 'figma',
  tags: [],
  indexedResourceNames: ['hooks', 'mcp', 'agents', 'commands', 'skills'],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/figma',
  revision: 'revision-1',
  updatedAt: '2026-08-22T00:00:00Z',
  variants: [],
};

describe('getMarketplaceFeatureLabelKey', () => {
  it('maps targetClient-specific feature labels', () => {
    expect(getMarketplaceFeatureLabelKey('claude-code', 'agentsMd')).toBe('marketplace.features.claudeMd');
    expect(getMarketplaceFeatureLabelKey('codex', 'agentsMd')).toBe('marketplace.features.agentsMd');
    expect(getMarketplaceFeatureLabelKey('codex', 'agents')).toBe('marketplace.features.subagents');
    expect(getMarketplaceFeatureLabelKey('codex', 'commands')).toBe('marketplace.features.slashCommands');
  });

  it('derives the ordered package features shared by package and install cards', () => {
    expect(getMarketplacePackageFeatures(packageSummary)).toEqual([
      'hooks',
      'mcp',
      'agents',
      'commands',
      'skills',
    ]);
  });
});
