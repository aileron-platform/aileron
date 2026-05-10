import React from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { render } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';

import {
  MarketplaceEditorHookSection,
  formatMarketplaceHookTimeout,
  marketplaceHookResourceItemFromValue,
  type MarketplaceHookDialogValue,
} from './MarketplaceEditorHookSection';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceEditorHookSection helpers', () => {
  it('formats provider-specific hook timeout units', () => {
    expect(formatMarketplaceHookTimeout('codex', 180)).toBe('180s');
    expect(formatMarketplaceHookTimeout('claude-code')).toBe('600s');
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

  it('renders all matchers and actions in hook cards', () => {
    const items: MarketplaceEditorResourceItem[] = [
      {
        id: 'hook-many',
        title: 'Hook many',
        path: 'hooks/hook-many.json',
        content: '{}',
        data: {
          name: 'Hook many',
          event: 'BeforeTool',
          matchers: [
            {
              matcher: 'Read',
              sequential: true,
              hooks: [
                { type: 'command', command: 'read one', timeout: 60000 },
                { type: 'command', command: 'read two', timeout: 60000 },
              ],
            },
            {
              matcher: 'Write',
              sequential: true,
              hooks: [
                { type: 'command', command: 'write one', timeout: 60000 },
                { type: 'command', command: 'write two', timeout: 60000 },
              ],
            },
          ],
        },
      },
    ];
    const Icon = () => React.createElement('span');

    render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'gemini',
        icon: Icon,
        items,
      }),
    );

    expect(screen.getByText('read one')).toBeInTheDocument();
    expect(screen.getByText('read two')).toBeInTheDocument();
    expect(screen.getByText('write one')).toBeInTheDocument();
    expect(screen.getByText('write two')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.card.summary.matchers')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.card.summary.commands')).toBeInTheDocument();
  });

  it('hydrates hook cards and edit dialog from native hooks.json content', () => {
    const items: MarketplaceEditorResourceItem[] = [
      {
        id: 'test-before-finish',
        title: 'test-before-finish',
        description: 'Runs targeted verification before finishing.',
        path: 'hooks/test-before-finish.json',
        content: JSON.stringify({
          hooks: {
            Stop: [
              {
                matcher: 'Bash',
                hooks: [
                  {
                    type: 'command',
                    command: 'npm test',
                    timeout: 120,
                  },
                ],
              },
            ],
          },
        }, null, 2),
      },
    ];
    const Icon = () => React.createElement('span');
    const { container } = render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'claude-code',
        icon: Icon,
        items,
      }),
    );

    expect(screen.getByText('npm test')).toBeInTheDocument();
    expect(screen.getByText('Bash')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.events.Stop.label')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.events.Stop.description')).toBeInTheDocument();

    const buttons = Array.from(container.querySelectorAll('button'));
    fireEvent.click(buttons[1]);

    expect(screen.getByDisplayValue('npm test')).toBeInTheDocument();
    expect(screen.getByDisplayValue('120')).toBeInTheDocument();
  });
});
