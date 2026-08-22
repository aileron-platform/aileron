import { describe, expect, it } from 'vitest';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import {
  buildMarketplaceDeleteRequest,
  buildMarketplaceExportRequest,
  getMarketplaceActionTextKeys,
} from './marketplacePackageActionModel';

const packageSummary: MarketplacePackageSummary = {
  targetClient: 'codex',
  packageFormat: 'codex-native',
  catalogPluginId: 'figma-context',
  userCopyTargetClient: 'codex',
  packageType: 'plugin',
  packageId: 'figma-context',
  displayName: 'Figma Context',
  version: '0.1.0',
  description: 'Figma context plugin.',
  category: 'coding',
  tags: ['mcp'],
  indexedResourceNames: ['mcp'],
  validationSeverity: 'none',
  authoringCapabilities: {
    basic: 'read-write', agentsMd: 'read-write', hooks: 'read-write',
    mcp: 'read-write', agents: 'read-write', commands: 'read-write',
    outputStyle: 'unsupported', skills: 'read-write', files: 'read-write',
  },
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [],
};

describe('marketplacePackageActionModel', () => {
  it('builds export and delete requests from package action context', () => {
    expect(buildMarketplaceExportRequest(packageSummary)).toEqual({
      targetClient: 'codex',
      packageFormat: 'codex-native',
      packageId: 'figma-context',
    });
    expect(buildMarketplaceDeleteRequest(packageSummary)).toEqual({
      targetClient: 'codex',
      packageFormat: 'codex-native',
      packageId: 'figma-context',
    });
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
