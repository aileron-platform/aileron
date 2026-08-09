import React from 'react';
import userEvent from '@testing-library/user-event';
import { FileCode2 } from 'lucide-react';
import { render as baseRender, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AgentSettingsDocumentSidebar,
  buildSidebarSourceOption,
  type AgentSettingsDocumentSidebarItem,
} from './AgentSettingsDocumentSidebar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const items: AgentSettingsDocumentSidebarItem[] = [
  {
    id: 'project:help.md',
    label: 'Help',
    description: 'help.md',
    source: 'project',
    sourceLabel: 'workspace.agentSettings.common.documents.scope.values.project',
    sizeLabel: '12 B',
  },
  {
    id: 'plugin:demo/review.md',
    label: 'Review',
    description: 'demo/review.md',
    source: 'plugin',
    sourceLabel: 'workspace.agentSettings.common.documents.scope.values.plugin',
    readOnly: true,
    pluginName: 'demo',
    marketplaceName: 'local',
    badges: [
      { key: 'effective', label: 'workspace.agentSettings.common.documents.status.effective' },
    ],
  },
];

const labels = {
  searchPlaceholder: 'workspace.agentSettings.common.documents.sidebar.searchPlaceholder',
  loading: 'workspace.agentSettings.common.documents.sidebar.loading',
  empty: 'workspace.agentSettings.common.documents.sidebar.empty',
  refresh: 'workspace.agentSettings.common.documents.actions.refresh',
  toggleCollapse: 'workspace.agentSettings.common.documents.sidebar.toggle.collapse',
  toggleExpand: 'workspace.agentSettings.common.documents.sidebar.toggle.expand',
  readOnly: 'workspace.agentSettings.common.sourceNotices.readOnly.title',
};

const render = (ui: React.ReactElement, options?: Parameters<typeof baseRender>[1]) => baseRender(ui, options);

describe('AgentSettingsDocumentSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: () => undefined,
    });
  });

  it('auto selects the first filtered item and switches selection by click after search', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onFilterChange = vi.fn();

    render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.common.documents.meta.slash-commands.title"
        icon={FileCode2}
        items={items}
        selectedId={null}
        onSelect={onSelect}
        filterValue="all"
        onFilterChange={onFilterChange}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.common.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.common.documents.scope.values.project'),
          buildSidebarSourceOption('plugin', 'workspace.agentSettings.common.documents.scope.values.plugin'),
        ]}
        filterLabel="workspace.agentSettings.common.documents.sidebar.scope.label"
        labels={labels}
      />,
    );

    expect(screen.getByText('workspace.agentSettings.common.documents.meta.slash-commands.title')).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:help.md'));

    await user.type(screen.getByPlaceholderText(labels.searchPlaceholder), 'review');
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.queryByText('Help')).not.toBeInTheDocument();

    await user.click(screen.getByText('Review'));
    expect(onSelect).toHaveBeenCalledWith('plugin:demo/review.md');
  });

  it('emits source filter changes and renders read-only metadata badges', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onFilterChange = vi.fn();

    render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.codex.documents.meta.prompts.title"
        icon={FileCode2}
        items={items}
        selectedId="plugin:demo/review.md"
        onSelect={onSelect}
        filterValue="all"
        onFilterChange={onFilterChange}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.codex.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.codex.documents.scope.values.project'),
          buildSidebarSourceOption('plugin', 'workspace.agentSettings.codex.documents.scope.values.plugin'),
        ]}
        filterLabel="workspace.agentSettings.codex.hooks.filters.scope.label"
        labels={labels}
      />,
    );

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByText('workspace.agentSettings.codex.documents.scope.values.plugin'));

    expect(onFilterChange).toHaveBeenCalledWith('plugin');
    expect(screen.getByText('workspace.agentSettings.common.sourceNotices.readOnly.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.documents.status.effective')).toBeInTheDocument();
    expect(screen.getByText('demo@local')).toBeInTheDocument();
  });

  it('preserves the selected document when search returns no results', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.common.documents.meta.slash-commands.title"
        icon={FileCode2}
        items={items}
        selectedId="project:help.md"
        onSelect={onSelect}
        filterValue="all"
        onFilterChange={vi.fn()}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.common.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.common.documents.scope.values.project'),
          buildSidebarSourceOption('plugin', 'workspace.agentSettings.common.documents.scope.values.plugin'),
        ]}
        filterLabel="workspace.agentSettings.common.documents.sidebar.scope.label"
        labels={labels}
      />,
    );

    await user.type(screen.getByPlaceholderText(labels.searchPlaceholder), 'not-found');

    expect(screen.getByText(labels.empty)).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalledWith(null);
  });

  it('shows the empty state instead of loading when filtered results are empty during refresh', async () => {
    const user = userEvent.setup();

    render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.common.documents.meta.slash-commands.title"
        icon={FileCode2}
        items={items}
        selectedId="project:help.md"
        onSelect={vi.fn()}
        isLoading
        filterValue="all"
        onFilterChange={vi.fn()}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.common.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.common.documents.scope.values.project'),
          buildSidebarSourceOption('plugin', 'workspace.agentSettings.common.documents.scope.values.plugin'),
        ]}
        filterLabel="workspace.agentSettings.common.documents.sidebar.scope.label"
        labels={labels}
      />,
    );

    await user.type(screen.getByPlaceholderText(labels.searchPlaceholder), 'not-found');

    expect(screen.getByText(labels.empty)).toBeInTheDocument();
    expect(screen.queryByText(labels.loading)).not.toBeInTheDocument();
  });

  it('renders the shared document list without nesting a second sidebar shell', () => {
    const { container } = render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.common.documents.meta.slash-commands.title"
        icon={FileCode2}
        items={items}
        selectedId="project:help.md"
        onSelect={vi.fn()}
        filterValue="all"
        onFilterChange={vi.fn()}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.common.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.common.documents.scope.values.project'),
        ]}
        filterLabel="workspace.agentSettings.common.documents.sidebar.scope.label"
        labels={labels}
      />,
    );

    expect(container.querySelectorAll('.border-r')).toHaveLength(0);
    expect(container.querySelectorAll('.overflow-y-auto')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /Help/ })).toBeInTheDocument();
  });

  it('separates the source scope filter from search with a divider row', () => {
    render(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.common.documents.meta.slash-commands.title"
        icon={FileCode2}
        items={items}
        selectedId="project:help.md"
        onSelect={vi.fn()}
        filterValue="all"
        onFilterChange={vi.fn()}
        filterOptions={[
          buildSidebarSourceOption('all', 'workspace.agentSettings.common.documents.sidebar.scope.all'),
          buildSidebarSourceOption('project', 'workspace.agentSettings.common.documents.scope.values.project'),
        ]}
        filterLabel="workspace.agentSettings.common.documents.sidebar.scope.label"
        labels={labels}
      />,
    );

    const scopeRow = screen.getByRole('combobox').parentElement;

    expect(scopeRow).toHaveClass('border-t');
    expect(scopeRow).toHaveClass('pt-2');
  });

  it('renders collapsed placeholder and toggle control', () => {
    baseRender(
      <AgentSettingsDocumentSidebar
        title="workspace.agentSettings.codex.documents.meta.rules.title"
        icon={FileCode2}
        items={items}
        selectedId={null}
        onSelect={vi.fn()}
        collapsed
        filterValue="all"
        onFilterChange={vi.fn()}
        filterOptions={[buildSidebarSourceOption('all', 'workspace.agentSettings.codex.documents.sidebar.scope.all')]}
        filterLabel="workspace.agentSettings.codex.hooks.filters.scope.label"
        labels={labels}
      />,
    );

    expect(screen.queryByPlaceholderText(labels.searchPlaceholder)).not.toBeInTheDocument();
    expect(screen.getByLabelText(labels.toggleExpand)).toBeInTheDocument();
  });
});
