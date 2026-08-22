import { describe, expect, it } from 'vitest';
import type {
  MarketplacePackageSummary,
  MarketplaceUserCopyPreflightResult,
} from '../model/marketplaceTypes';
import {
  getMarketplaceInstallErrorKey,
  getMarketplaceInstallResourceTypeLabelKey,
  getMarketplaceSkippedReasonKey,
  marketplaceBlockingIssueGroups,
  marketplaceResourceTypeCounts,
} from './marketplaceInstallModel';

const packageSummary: MarketplacePackageSummary = {
  targetClient: 'codex',
  packageType: 'plugin',
  packageId: 'review-tools',
  displayName: 'Review Tools',
  tags: [],
  indexedResourceNames: [],
  validationSeverity: 'none',
  registryPath: 'codex/plugins/review-tools',
  revision: 'revision-1',
  updatedAt: '2026-07-25T00:00:00Z',
  variants: [],
};

const userCopyPreflight: MarketplaceUserCopyPreflightResult = {
  status: 'ready',
  targetClient: 'codex',
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

  it('groups blocking issues by their localized reason', () => {
    expect(marketplaceBlockingIssueGroups({
      ...userCopyPreflight,
      status: 'blocked',
      blockingIssues: [
        {
          resourceType: 'skill',
          resourceId: 'one',
          sourceLocator: 'skills/one/SKILL.md',
          targetLocator: '.codex/skills/one',
          errorCode: 'marketplace.user_copy.target_not_writable',
        },
        {
          resourceType: 'skill',
          resourceId: 'two',
          sourceLocator: 'skills/two/SKILL.md',
          targetLocator: '.codex/skills/two',
          errorCode: 'marketplace.user_copy.target_not_writable',
        },
      ],
    })).toEqual([{
      errorCode: 'marketplace.user_copy.target_not_writable',
      count: 2,
    }]);
  });

  it('maps one-shot plugin and user-copy operation errors', () => {
    expect(getMarketplaceInstallErrorKey(
      'marketplace.install.runtime_contract_invalid',
    )).toBe('marketplace.install.errors.runtimeContractInvalid');
    expect(getMarketplaceInstallErrorKey(
      'marketplace.user_copy.plan_stale',
    )).toBe('marketplace.install.errors.userCopyPlanStale');
    expect(getMarketplaceInstallErrorKey('unexpected')).toBe(
      'marketplace.install.errors.unknown',
    );
  });

  it('maps unsupported package formats to a localized skipped reason', () => {
    expect(getMarketplaceSkippedReasonKey('format-unsupported')).toBe(
      'marketplace.install.skipped.reasons.formatUnsupported',
    );
    expect(getMarketplaceSkippedReasonKey('unknown')).toBe(
      'marketplace.install.skipped.reasons.unsupported',
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
});
