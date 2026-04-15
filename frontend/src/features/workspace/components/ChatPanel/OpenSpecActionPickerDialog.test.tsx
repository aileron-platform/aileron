import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { OpenSpecActionPickerDialog } from './OpenSpecActionPickerDialog';
import type { OpenSpecActionItem, OpenSpecNavigationChange, OpenSpecWorkspaceState } from './openSpecApi';

const { tMock } = vi.hoisted(() => ({
  tMock: (key: string, params?: Record<string, unknown>) =>
    ({
      'workspace.chat.dialogs.openspec.title': 'OpenSpec actions',
      'workspace.chat.dialogs.openspec.description': 'Choose an OpenSpec workflow action and insert its command into the composer.',
      'workspace.chat.dialogs.openspec.searchPlaceholder': 'Search OpenSpec actions...',
      'workspace.chat.dialogs.openspec.empty': 'No OpenSpec actions match the current filters.',
      'workspace.chat.dialogs.openspec.recommended': 'Recommended',
      'workspace.chat.dialogs.openspec.version': `CLI version: ${String(params?.version ?? '')}`,
      'workspace.chat.dialogs.openspec.profile.core': 'Core workflow',
      'workspace.chat.dialogs.openspec.profile.expanded': 'Expanded workflow',
      'workspace.chat.dialogs.openspec.profile.custom': 'Custom workflow',
      'workspace.chat.dialogs.openspec.status.initialized': 'Initialized',
      'workspace.chat.dialogs.openspec.status.notInitialized': 'Not initialized',
      'workspace.chat.dialogs.openspec.groups.start': 'Start',
      'workspace.chat.dialogs.openspec.groups.plan': 'Planning',
      'workspace.chat.dialogs.openspec.groups.implement': 'Implement',
      'workspace.chat.dialogs.openspec.groups.finalize': 'Finalize',
      'workspace.chat.dialogs.openspec.groups.learn': 'Learn',
      'workspace.chat.dialogs.openspec.filters.all': 'All',
      'workspace.chat.dialogs.openspec.filters.recommended': 'Recommended',
      'workspace.chat.dialogs.openspec.filters.enabled': 'Enabled',
      'workspace.chat.dialogs.openspec.filters.blocked': 'Blocked',
      'workspace.chat.dialogs.openspec.filters.setup': 'Setup required',
      'workspace.chat.dialogs.openspec.showHidden': 'Show hidden commands',
      'workspace.chat.dialogs.openspec.hideHidden': 'Hide hidden commands',
      'workspace.chat.dialogs.openspec.hiddenByProfile': 'Hidden by profile',
      'workspace.chat.dialogs.openspec.expandedLocked.title': 'Expanded commands are locked',
      'workspace.chat.dialogs.openspec.expandedLocked.count': `${String(params?.count ?? '')} expanded command(s) are currently locked.`,
      'workspace.chat.dialogs.openspec.expandedLocked.chip': `${String(params?.count ?? '')} locked`,
      'workspace.chat.dialogs.openspec.expandedLocked.cta': 'View steps',
      'workspace.chat.dialogs.openspec.expandedLocked.inlineCta': 'Why is this locked?',
      'workspace.chat.dialogs.openspec.expandedGuide.title': 'Enable expanded workflow',
      'workspace.chat.dialogs.openspec.expandedGuide.description': 'Expanded commands appear after you choose a workflow profile and apply it to this workspace.',
      'workspace.chat.dialogs.openspec.expandedGuide.currentStateTitle': 'What is happening now',
      'workspace.chat.dialogs.openspec.expandedGuide.currentStateDescription': 'This workspace is still on the core workflow, so commands like new, continue, verify, sync, and bulk-archive remain unavailable.',
      'workspace.chat.dialogs.openspec.expandedGuide.stepOneLabel': 'Step 1',
      'workspace.chat.dialogs.openspec.expandedGuide.stepOneDescription': 'Choose the workflow profile you want. This decides whether the project uses the core path or the expanded command set.',
      'workspace.chat.dialogs.openspec.expandedGuide.stepTwoLabel': 'Step 2',
      'workspace.chat.dialogs.openspec.expandedGuide.stepTwoDescription': 'Apply that selection to the current workspace so OpenSpec regenerates the command files for this project.',
      'workspace.chat.dialogs.openspec.expandedGuide.note': 'Only running profile selection is not enough. The workspace still needs an update before the expanded commands show up here.',
      'workspace.chat.dialogs.openspec.expandedGuide.close': 'Close',
      'workspace.chat.dialogs.openspec.detailTitle': 'Command details',
      'workspace.chat.dialogs.openspec.detailPlaceholder': 'Select an OpenSpec action to see its details.',
      'workspace.chat.dialogs.openspec.recommendationReason': 'Why this is recommended',
      'workspace.chat.dialogs.openspec.availability': 'Availability',
      'workspace.chat.dialogs.openspec.syntax': 'Syntax',
      'workspace.chat.dialogs.openspec.example': 'Example',
      'workspace.chat.dialogs.openspec.whenToUse': 'When to use',
      'workspace.chat.dialogs.openspec.parameters': 'Parameters',
      'workspace.chat.dialogs.openspec.noParameters': 'No parameters required.',
      'workspace.chat.dialogs.openspec.selectChange': 'Target change',
      'workspace.chat.dialogs.openspec.selectChanges': 'Target changes',
      'workspace.chat.dialogs.openspec.noTargetChanges': 'No target changes available in the current context.',
      'workspace.chat.dialogs.openspec.changeName': 'Change name',
      'workspace.chat.dialogs.openspec.descriptionInput': 'Change name or description',
      'workspace.chat.dialogs.openspec.schemaLabel': 'Schema',
      'workspace.chat.dialogs.openspec.insertDraft': 'Insert command',
      'workspace.chat.dialogs.openspec.unavailable': 'Unavailable',
      'workspace.chat.dialogs.openspec.available': 'Available',
      'workspace.chat.dialogs.openspec.setupRequired': 'Setup required',
      'workspace.chat.dialogs.openspec.syncRequired': 'Update required',
      'workspace.chat.dialogs.openspec.blocked': 'Blocked',
      'workspace.chat.dialogs.openspec.hidden': 'Hidden',
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
  profile: 'custom',
  projectSynced: false,
  activeChanges: [],
};

const changes: OpenSpecNavigationChange[] = [
  {
    name: 'add-auth',
    status: 'in-progress',
    archived: false,
    proposalPath: '/openspec/changes/add-auth/proposal.md',
    designPath: '/openspec/changes/add-auth/design.md',
    tasksPath: '/openspec/changes/add-auth/tasks.md',
    specs: [],
    completedTasks: 1,
    totalTasks: 3,
  },
  {
    name: 'done-change',
    status: 'complete',
    archived: false,
    proposalPath: '/openspec/changes/done-change/proposal.md',
    designPath: '/openspec/changes/done-change/design.md',
    tasksPath: '/openspec/changes/done-change/tasks.md',
    specs: [],
    completedTasks: 2,
    totalTasks: 2,
  },
];

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
    recommendedReason: 'There is an active change with work ready to implement',
    requiresChange: true,
    supportsChangeArgument: true,
    inputKind: 'change',
    exampleCommand: '/opsx:apply add-auth',
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
    recommended: false,
    recommendedReason: null,
    requiresChange: true,
    supportsChangeArgument: true,
    inputKind: 'change',
    exampleCommand: '/opsx:archive done-change',
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
    recommended: false,
    recommendedReason: null,
    requiresChange: false,
    supportsChangeArgument: false,
    inputKind: 'structured',
    exampleCommand: '/opsx:bulk-archive add-auth done-change',
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
    recommendedReason: null,
    requiresChange: false,
    supportsChangeArgument: false,
    inputKind: 'structured',
    exampleCommand: '/opsx:new add-auth --schema spec-driven',
    draftTemplate: '/opsx:new ',
  },
];

describe('OpenSpecActionPickerDialog', () => {
  it('renders recommendation reason and runtime-provided metadata', () => {
    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="add-auth"
        state={baseState}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText('OpenSpec actions')).toBeInTheDocument();
    expect(screen.getAllByText('Apply').length).toBeGreaterThan(0);
    expect(screen.getByText('There is an active change with work ready to implement')).toBeInTheDocument();
    expect(screen.getAllByText('Update required').length).toBeGreaterThan(0);
  });

  it('can reveal hidden profile commands', async () => {
    const user = userEvent.setup();

    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="add-auth"
        state={baseState}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByText('New')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show hidden commands' }));
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('Hidden by profile')).toBeInTheDocument();
  });

  it('shows a compact expanded workflow entry for core workspaces', () => {
    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="add-auth"
        state={{ ...baseState, profile: 'core', projectSynced: true }}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '1 locked' })).toBeInTheDocument();
  });

  it('opens the expanded workflow guide from the locked command card', async () => {
    const user = userEvent.setup();

    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="add-auth"
        state={{ ...baseState, profile: 'core', projectSynced: true }}
        onSelect={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: '1 locked' }));

    expect(screen.getByRole('heading', { name: 'Enable expanded workflow' })).toBeInTheDocument();
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('openspec config profile')).toBeInTheDocument();
    expect(screen.getByText('openspec update /workspace')).toBeInTheDocument();
  });

  it('opens the expanded workflow guide when selecting a hidden expanded command', async () => {
    const user = userEvent.setup();

    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="add-auth"
        state={{ ...baseState, profile: 'core', projectSynced: true }}
        onSelect={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Show hidden commands' }));
    await user.click(screen.getByText('New'));

    expect(screen.getByRole('heading', { name: 'Enable expanded workflow' })).toBeInTheDocument();
    expect(screen.getByText('What is happening now')).toBeInTheDocument();
  });

  it('builds a single-change draft from the selected target', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={englishActions}
        changes={changes}
        focusedChangeName="done-change"
        state={{ ...baseState, projectSynced: true }}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByText('Archive'));
    await user.click(screen.getByRole('button', { name: 'Insert command' }));

    expect(onSelect).toHaveBeenCalledWith('/opsx:archive done-change');
  });

  it('builds a structured draft for propose-like commands', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const proposeAction: OpenSpecActionItem = {
      id: 'propose',
      title: 'Propose',
      description: 'Create a change and draft the planning artifacts',
      group: 'start',
      profile: 'core',
      availability: 'enabled',
      reason: null,
      recommended: true,
      recommendedReason: 'There is no active change yet, so proposing a new change is the next step',
      requiresChange: false,
      supportsChangeArgument: false,
      inputKind: 'structured',
      exampleCommand: '/opsx:propose add-dark-mode',
      draftTemplate: '/opsx:propose ',
    };

    render(
      <OpenSpecActionPickerDialog
        open
        onOpenChange={vi.fn()}
        actions={[proposeAction]}
        changes={[]}
        focusedChangeName={null}
        state={{ ...baseState, profile: 'core', projectSynced: true }}
        onSelect={onSelect}
      />,
    );

    await user.type(screen.getByPlaceholderText('Change name or description'), 'improve auth flow');
    await user.click(screen.getByRole('button', { name: 'Insert command' }));

    expect(onSelect).toHaveBeenCalledWith('/opsx:propose improve auth flow');
  });
});
