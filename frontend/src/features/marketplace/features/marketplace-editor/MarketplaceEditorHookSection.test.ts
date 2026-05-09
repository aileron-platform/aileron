import { describe, expect, it } from 'vitest';

import {
  formatMarketplaceHookTimeout,
  marketplaceHookResourceItemFromValue,
  type MarketplaceHookDialogValue,
} from './MarketplaceEditorHookSection';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

describe('MarketplaceEditorHookSection helpers', () => {
  it('formats provider-specific hook timeout units', () => {
    expect(formatMarketplaceHookTimeout('codex', 180)).toBe('180s');
    expect(formatMarketplaceHookTimeout('claude-code')).toBe('120s');
    expect(formatMarketplaceHookTimeout('gemini', 60000)).toBe('60000ms');
  });

  it('projects hook dialog values back into resource item metadata', () => {
    const item: MarketplaceEditorResourceItem = {
      id: 'test-before-finish',
      title: 'old',
      description: 'old',
      path: 'hooks/test-before-finish.json',
      content: '{}',
    };
    const value: MarketplaceHookDialogValue = {
      name: 'test-before-finish',
      event: 'BeforeTool',
      matchers: [
        {
          matcher: '*',
          sequential: true,
          hooks: [
            {
              type: 'command',
              command: 'gemini test',
              timeout: 60000,
            },
          ],
        },
      ],
    };

    expect(marketplaceHookResourceItemFromValue(item, 'gemini', value, key => key)).toEqual(expect.objectContaining({
      title: 'test-before-finish',
      description: 'BeforeTool',
      path: 'hooks/test-before-finish.json',
      badge: 'BeforeTool',
      code: 'gemini test',
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
        { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: '*' },
        { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '60000ms' },
        { labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: 'marketplace.common.labels.enabled' },
      ],
    }));
  });
});
