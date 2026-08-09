import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { render } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { Workflow } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';

import {
  MarketplaceEditorHookSection,
} from './MarketplaceEditorHookSection';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceEditorHookSection helpers', () => {
  it('renders through the shared settings list workbench shell', () => {
    const onRefresh = vi.fn();
    render(
      <MarketplaceEditorHookSection
        provider="claude-code"
        icon={Workflow}
        items={[]}
        onDirty={() => undefined}
        onItemsChange={() => undefined}
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByText('marketplace.editor.tabs.hooks')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.featureSections.hooks.emptyTitle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.featureSections.hooks.emptyDescription')).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: 'marketplace.common.actions.refresh' })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.common.actions.refresh' }));
    expect(onRefresh).toHaveBeenCalled();
    const addButton = screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' });
    expect(addButton).toHaveClass('bg-primary');
  });

  it('opens the marketplace hook dialog with existing marketplace labels', async () => {
    const user = userEvent.setup();

    render(
      <MarketplaceEditorHookSection
        provider="claude-code"
        icon={Workflow}
        items={[]}
        onDirty={vi.fn()}
        onItemsChange={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'marketplace.editor.featureSections.actions.add' }));

    expect(screen.getByRole('heading', { name: 'marketplace.editor.hooks.dialog.titleCreate' })).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.description.claude-code')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.fields.event.label')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.matchers.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.timeoutLabel.claude-code')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.commandLabel.claude-code')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.executions.types.command.label')).toBeInTheDocument();
    expect(screen.getAllByText('marketplace.editor.hooks.dialog.executions.shellOptions.bash')).not.toHaveLength(0);
    expect(screen.getByText('marketplace.editor.hooks.dialog.matcherHints.generic.help')).toBeInTheDocument();
    expect(screen.getByText('marketplace.editor.hooks.dialog.validation.commandRequired')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.editor.hooks.dialog.actions.save' })).toBeDisabled();
  });

  it('removes hook cards through the trash button', async () => {
    const onItemsChange = vi.fn().mockResolvedValue(undefined);
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
    const { container } = render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'codex',
        icon: Workflow,
        items,
        onItemsChange,
        onDirty,
      }),
    );

    const buttons = Array.from(container.querySelectorAll('button'));
    fireEvent.click(buttons[3]);

    expect(onItemsChange).toHaveBeenCalledWith([items[1]]);
    await waitFor(() => expect(onDirty).toHaveBeenCalled());
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
    render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'codex',
        icon: Workflow,
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
    const { container } = render(
      React.createElement(MarketplaceEditorHookSection, {
        provider: 'claude-code',
        icon: Workflow,
        items,
      }),
    );

    expect(screen.getByText('npm test')).toBeInTheDocument();
    expect(screen.getByText('Bash')).toBeInTheDocument();
    expect(screen.getByText('common.hookEvents.Stop.label')).toBeInTheDocument();
    expect(screen.getByText('common.hookEvents.Stop.description')).toBeInTheDocument();

    const buttons = Array.from(container.querySelectorAll('button'));
    fireEvent.click(buttons[2]);

    expect(screen.getByDisplayValue('npm test')).toBeInTheDocument();
    expect(screen.getByDisplayValue('120')).toBeInTheDocument();
  });
});
