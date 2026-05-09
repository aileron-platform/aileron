import { describe, expect, it } from 'vitest';

import {
  createInitialMarketplaceRequiredDraft,
  mergeMarketplaceListingJson,
  parseMarketplaceJsonObject,
} from './marketplaceEditorRequiredDraft';

const fallbacks = {
  packageName: 'sample-package',
  codexMarketplaceName: 'Codex Marketplace',
  claudeMarketplaceName: 'Claude Marketplace',
  ownerName: 'Default Owner',
  description: 'Default description',
};

describe('marketplaceEditorRequiredDraft', () => {
  it('creates codex listing and manifest drafts from form values', () => {
    const draft = createInitialMarketplaceRequiredDraft('codex', 'review-bot', 'Review Bot', 'Reviews code', fallbacks);

    expect(parseMarketplaceJsonObject(draft.listingJson)).toEqual({
      name: 'review-bot',
      source: {
        source: 'local',
        path: './plugins/review-bot',
      },
      policy: {
        installation: 'AVAILABLE',
        authentication: 'ON_INSTALL',
      },
      category: 'Productivity',
    });
    expect(parseMarketplaceJsonObject(draft.manifestJson)).toEqual({
      name: 'review-bot',
      version: '0.1.0',
      description: 'Reviews code',
    });
  });

  it('preserves unknown listing fields when required values are merged', () => {
    const draft = createInitialMarketplaceRequiredDraft('codex', 'review-bot', 'Review Bot', 'Reviews code', fallbacks);
    const merged = mergeMarketplaceListingJson(
      'codex',
      JSON.stringify({ tags: ['code'], policy: { approval: 'manual' } }),
      {
        ...draft,
        packageName: 'reviewer',
        sourcePath: './plugins/reviewer',
      },
    );

    expect(parseMarketplaceJsonObject(merged)).toEqual({
      tags: ['code'],
      name: 'reviewer',
      source: {
        source: 'local',
        path: './plugins/reviewer',
      },
      policy: {
        approval: 'manual',
        installation: 'AVAILABLE',
        authentication: 'ON_INSTALL',
      },
      category: 'Productivity',
    });
  });
});
