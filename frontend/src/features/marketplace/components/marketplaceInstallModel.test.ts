import { describe, expect, it } from 'vitest';
import type {
  MarketplacePackageSummary,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import {
  getMarketplaceInstallErrorKey,
  getMarketplaceInstallResourceTypeLabelKey,
  getMarketplacePluginIndexedResourceTypes,
  marketplaceResourceTypeCounts,
} from './marketplaceInstallModel';

const packageSummary: MarketplacePackageSummary = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  tags: [],
  sourceType: 'created',
  indexedResourceNames: [],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'codex/plugins/review-tools',
  revision: 'revision-1',
  updatedAt: '2026-07-25T00:00:00Z',
  variants: [],
};

const userCopyPreflight: MarketplaceUserCopyPreflightResult = {
  status: 'ready',
  provider: 'codex',
  packageId: 'review-tools',
  workspaceId: 'workspace-1',
  sourceDigest: 'source',
  profileDigest: 'profile',
  materializationDigest: 'plan',
  resources: [
    {
      resourceType: 'skill',
      resourceId: 'one',
      sourceLocator: 'skills/one/SKILL.md',
      targetLocator: '.codex/skills/one/SKILL.md',
      operation: 'create',
    },
    {
      resourceType: 'instructions',
      resourceId: 'root',
      sourceLocator: 'AGENTS.md',
      targetLocator: '.codex/AGENTS.md',
      operation: 'merge',
    },
  ],
  conflicts: [],
  blockingIssues: [],
};

describe('marketplaceInstallModel', () => {
  it('derives user-copy resource counts from its merge plan', () => {
    expect(marketplaceResourceTypeCounts(userCopyPreflight)).toEqual([
      ['instructions', 1],
      ['skill', 1],
    ]);
  });

  it('maps one-shot plugin and user-copy operation errors', () => {
    expect(getMarketplaceInstallErrorKey(
      'marketplace.install.runtime_contract_invalid',
    )).toBe('marketplace.install.errors.runtimeContractInvalid');
    expect(getMarketplaceInstallErrorKey(
      'marketplace.install.package_not_published',
    )).toBe('marketplace.install.errors.packageNotPublished');
    expect(getMarketplaceInstallErrorKey(
      'marketplace.user_copy.plan_stale',
    )).toBe('marketplace.install.errors.userCopyPlanStale');
    expect(getMarketplaceInstallErrorKey('unexpected')).toBe(
      'marketplace.install.errors.unknown',
    );
  });

  it('maps the Codex prompt resource to the Slash Command capability label', () => {
    expect(getMarketplaceInstallResourceTypeLabelKey('codex', 'prompt')).toBe(
      'marketplace.install.resourceTypes.slashCommand',
    );
    expect(getMarketplaceInstallResourceTypeLabelKey('claude-code', 'command')).toBe(
      'marketplace.install.resourceTypes.command',
    );
  });

  it('derives authoring resource hints from package index categories', () => {
    expect(getMarketplacePluginIndexedResourceTypes({
      ...packageSummary,
      indexedResourceNames: ['skills', 'apps', 'mcp', 'hooks', 'prompts'],
    })).toEqual(['skill', 'app', 'mcp', 'hook']);
  });
});
