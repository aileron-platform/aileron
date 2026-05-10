import React from 'react';
import { fireEvent } from '@testing-library/react';
import { render } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';

import {
  MarketplaceEditorHookSection,
  formatMarketplaceHookTimeout,
  marketplaceHookResourceItemFromValue,
  type MarketplaceHookDialogValue,
} from './MarketplaceEditorHookSection';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

describe('MarketplaceEditorHookSection helpers', () => {
  it('formats provider-specific hook timeout units', () => {
    expect(formatMarketplaceHookTimeout('codex', 180)).toBe('180s');
    expect(formatMarketplaceHookTimeout('claude-code')).toBe('60s');
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

    const nextItem = marketplaceHookResourceItemFromValue(item, 'gemini', value, key => key);

    expect(nextItem).toEqual(expect.objectContaining({
      title: 'test-before-finish',
      description: 'BeforeTool',
      path: 'hooks/test-before-finish.json',
      badge: 'BeforeTool',
      code: 'gemini test',
      data: {
        name: 'test-before-finish',
        event: 'BeforeTool',
        matchers: value.matchers,
      },
      meta: [
        { labelKey: 'marketplace.editor.featureMeta.labels.type', value: 'command' },
        { labelKey: 'marketplace.editor.featureMeta.labels.matcher', value: '*' },
        { labelKey: 'marketplace.editor.featureMeta.labels.timeout', value: '60000ms' },
        { labelKey: 'marketplace.editor.featureMeta.labels.sequential', value: 'marketplace.common.labels.enabled' },
      ],
    }));
    expect(JSON.parse(nextItem.content)).toEqual({
      hooks: {
        BeforeTool: value.matchers,
      },
    });
  });

  it('removes hook cards through the trash button', () => {
    const onItemsChange = vi.fn();
    const onDirty = vi.fn();
    const items: MarketplaceEditorResourceItem[] = [
      {
        id: 'hook-one',
        title: 'Hook one',
        path: 'hooks/hook-one.json',
        content: '{}',
        data: {
          name: 'Hook one',
          event: 'BeforeTool',
          matchers: [{ matcher: '*', sequential: true, hooks: [{ type: 'command', command: 'one', timeout: 60000 }] }],
        },
      },
      {
        id: 'hook-two',
        title: 'Hook two',
        path: 'hooks/hook-two.json',
        content: '{}',
        data: {
          name: 'Hook two',
          event: 'BeforeTool',
          matchers: [{ matcher: '*', sequential: true, hooks: [{ type: 'command', command: 'two', timeout: 60000 }] }],
        },
      },
    ];
    const Icon = () => React.createElement('span');
    const { container } = render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'gemini',
        icon: Icon,
        items,
        onItemsChange,
        onDirty,
      }),
    );

    const buttons = Array.from(container.querySelectorAll('button'));
    fireEvent.click(buttons[2]);

    expect(onItemsChange).toHaveBeenCalledWith([items[1]]);
    expect(onDirty).toHaveBeenCalled();
  });
});
