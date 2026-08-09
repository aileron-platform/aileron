import { describe, expect, it } from 'vitest';

import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';
import {
  formatMarketplaceHookTimeout,
  marketplaceHookResourceItemFromValue,
  type MarketplaceHookDialogValue,
} from './marketplaceHookModel';

describe('marketplaceHookModel', () => {
  it('formats provider-specific hook timeout units', () => {
    expect(formatMarketplaceHookTimeout('codex', 180)).toBe('180s');
    expect(formatMarketplaceHookTimeout('claude-code')).toBe('600s');
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
              command: 'codex test',
              timeout: 180,
            },
          ],
        },
      ],
    };

    const nextItem = marketplaceHookResourceItemFromValue(item, 'codex', value, key => key);

    expect(nextItem).toEqual(expect.objectContaining({
      id: 'test-before-finish',
      title: 'test-before-finish',
      description: 'BeforeTool',
      path: 'hooks/test-before-finish.json',
      badge: 'BeforeTool',
      code: 'codex test',
      content: expect.any(String),
      data: expect.objectContaining({
        __marketplaceSourceEvent: 'BeforeTool',
        name: 'test-before-finish',
        event: 'BeforeTool',
        matchers: value.matchers,
      }),
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
        { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: '*' },
        { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '180s' },
        { labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: 'marketplace.common.labels.enabled' },
      ],
    }));
    expect(JSON.parse(nextItem.content)).toEqual({
      hooks: {
        BeforeTool: value.matchers,
      },
    });
  });
});
