import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { OpenSpecActionPickerDialog } from './OpenSpecActionPickerDialog';
import type { OpenSpecActionItem, OpenSpecWorkspaceState } from './openSpecApi';

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string, params?: Record<string, unknown>) =>
    ({
      'workspace.chat.dialogs.openspec.title': 'OpenSpec actions',
      'workspace.chat.dialogs.openspec.description': 'Choose an OpenSpec workflow action and insert its draft command into the composer.',
      'workspace.chat.dialogs.openspec.searchPlaceholder': 'Search OpenSpec actions...',
      'workspace.chat.dialogs.openspec.empty': 'No OpenSpec actions match the current filters.',
      'workspace.chat.dialogs.openspec.recommended': 'Recommended',
      'workspace.chat.dialogs.openspec.version': `CLI version: ${String(params?.version ?? '')}`,
      'workspace.chat.dialogs.openspec.profile.core': 'Core workflow',
      'workspace.chat.dialogs.openspec.profile.expanded': 'Expanded workflow',
      'workspace.chat.dialogs.openspec.status.initialized': 'Initialized',
      'workspace.chat.dialogs.openspec.status.notInitialized': 'Not initialized',
      'workspace.chat.dialogs.openspec.groups.start': 'Start',
      'workspace.chat.dialogs.openspec.groups.plan': 'Planning',
      'workspace.chat.dialogs.openspec.groups.implement': 'Implement',
      'workspace.chat.dialogs.openspec.groups.finalize': 'Finalize',
      'workspace.chat.dialogs.openspec.groups.learn': 'Learn',
    }[key] ?? key),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

const baseState: OpenSpecWorkspaceState = {
  cliInstalled: true,
  cliVersion: '1.3.0',
  initialized: true,
  profile: 'core',
  projectSynced: true,
  activeChanges: [],
};

const englishActions: OpenSpecActionItem[] = [
  {
    id: 'apply',
    title: 'Apply',
    description: 'Implement the current change by following its tasks',
    group: 'implement',
    profile: 'core',
    availability: 'enabled',
    reason: null,
    recommended: true,
    requiresChange: true,
    supportsChangeArgument: true,
    draftTemplate: '/opsx:apply add-auth',
  },
  {
    id: 'archive',
    title: 'Archive',
    description: 'Archive a completed change',
    group: 'finalize',
    profile: 'core',
    availability: 'enabled',
    reason: null,
    recommended: true,
    requiresChange: true,
    supportsChangeArgument: true,
    draftTemplate: '/opsx:archive done-change',
  },
  {
    id: 'bulk-archive',
    title: 'Bulk Archive',
    description: 'Archive multiple completed changes in one pass',
    group: 'finalize',
    profile: 'expanded',
    availability: 'enabled',
    reason: null,
    recommended: true,
    requiresChange: false,
    supportsChangeArgument: false,
    draftTemplate: '/opsx:bulk-archive',
  },
  {
    id: 'new',
    title: 'New',
    description: 'Create a new change scaffold',
    group: 'plan',
    profile: 'expanded',
    availability: 'hidden',
    reason: 'Expanded workflows are not enabled yet',
    recommended: false,
    requiresChange: false,
    supportsChangeArgument: false,
    draftTemplate: '/opsx:new ',
  },
];

describe('OpenSpecActionPickerDialog', () => {
  it('renders runtime-provided action metadata without changing the contract', () => {
    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        state={baseState}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText('OpenSpec actions')).toBeInTheDocument();
    expect(screen.getByText('Apply')).toBeInTheDocument();
    expect(screen.getByText('Implement the current change by following its tasks')).toBeInTheDocument();
    expect(screen.getByText('/opsx:apply add-auth')).toBeInTheDocument();
    expect(screen.getAllByText('Recommended').length).toBeGreaterThan(0);
  });

  it('does not show Chinese action copy in the English dialog view', () => {
    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        state={baseState}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByText('依目前 change 的 tasks 進行實作')).not.toBeInTheDocument();
    expect(screen.queryByText('目前沒有可用的 OpenSpec change')).not.toBeInTheDocument();
    expect(screen.getByText('Implement the current change by following its tasks')).toBeInTheDocument();
  });

  it('renders archive and bulk-archive exactly as provided by runtime metadata', () => {
    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        state={baseState}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText('/opsx:archive done-change')).toBeInTheDocument();
    expect(screen.getByText('/opsx:bulk-archive')).toBeInTheDocument();
    expect(screen.getByText('Archive')).toBeInTheDocument();
    expect(screen.getByText('Bulk Archive')).toBeInTheDocument();
  });
});
