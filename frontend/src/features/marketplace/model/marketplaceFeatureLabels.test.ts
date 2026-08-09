import { describe, expect, it } from 'vitest';

import { getMarketplaceFeatureLabelKey } from './marketplaceFeatureLabels';

describe('getMarketplaceFeatureLabelKey', () => {
  it('maps provider-specific feature labels', () => {
    expect(getMarketplaceFeatureLabelKey('claude-code', 'agentsMd')).toBe('marketplace.features.claudeMd');
    expect(getMarketplaceFeatureLabelKey('codex', 'agentsMd')).toBe('marketplace.features.agentsMd');
    expect(getMarketplaceFeatureLabelKey('codex', 'agents')).toBe('marketplace.features.subagents');
    expect(getMarketplaceFeatureLabelKey('codex', 'commands')).toBe('marketplace.features.slashCommands');
  });
});
