import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { SlashCommandPickerDialog } from './SlashCommandPickerDialog';
import type { SlashCommandItem } from '@/shared/types/slashCommands';

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string) =>
    ({
      'common.slashCommand.picker.title': 'Select command',
      'common.slashCommand.picker.description': 'Pick an item',
      'common.slashCommand.picker.searchPlaceholder': 'Search...',
      'common.slashCommand.picker.empty': 'No items',
      'common.slashCommand.picker.scope.all': 'All',
      'common.slashCommand.picker.scope.project': 'Project',
      'common.slashCommand.picker.scope.user': 'User',
      'common.slashCommand.picker.scope.plugin': 'Plugin',
      'common.slashCommand.picker.kind.slash-command': 'Command',
      'common.slashCommand.picker.kind.skill': 'Skill',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

const items: SlashCommandItem[] = [
  {
    id: 'project:ops:deploy.md',
    fileName: 'deploy.md',
    kind: 'slash-command',
    scope: 'project',
    namespace: 'ops',
    displayName: 'ops/deploy',
    category: 'ops',
    description: 'Deploy service',
    invocation: '/ops/deploy',
    tags: [],
  },
  {
    id: 'project:skill:openspec-explore',
    fileName: 'SKILL.md',
    kind: 'skill',
    scope: 'project',
    displayName: 'openspec-explore',
    category: 'project',
    description: 'Explore a change',
    invocation: '/openspec-explore',
    tags: [],
  },
];

describe('SlashCommandPickerDialog', () => {
  it('renders both slash command and skill item kinds', () => {
    render(
      <SlashCommandPickerDialog
        open
        onOpenChange={vi.fn()}
        commands={items}
        onSelect={vi.fn()}
        availableScopes={['project', 'user']}
      />,
    );

    expect(screen.getByRole('button', { name: /ops\/deploy/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /openspec-explore/i })).toBeInTheDocument();
    expect(screen.getByText('Command')).toBeInTheDocument();
    expect(screen.getByText('Skill')).toBeInTheDocument();
  });

  it('filters mixed items by search term and returns the selected invocation item', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <SlashCommandPickerDialog
        open
        onOpenChange={vi.fn()}
        commands={items}
        onSelect={onSelect}
        availableScopes={['project', 'user']}
      />,
    );

    await user.type(screen.getByPlaceholderText('Search...'), 'explore');

    expect(screen.queryByText('ops/deploy')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /openspec-explore/i }));

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      invocation: '/openspec-explore',
      kind: 'skill',
    }));
  });
});
