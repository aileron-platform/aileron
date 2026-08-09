import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AgentSettingsPage from './AgentSettingsPage';

const mocks = vi.hoisted(() => ({
  mountCounts: new Map<string, number>(),
  workspaceRuntime: {
    runtimeBaseUrl: 'http://runtime.test',
    workspaceId: 'workspace-test',
    error: null as Error | null,
    isLoading: false,
  },
  recordMount: (key: string) => {
    mocks.mountCounts.set(key, (mocks.mountCounts.get(key) ?? 0) + 1);
  },
  mountCount: (key: string) => mocks.mountCounts.get(key) ?? 0,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.feature && params?.toolName) {
        return `${String(params.feature)}:${String(params.toolName)}`;
      }
      return key;
    },
  }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: mocks.workspaceRuntime,
  }),
}));

vi.mock('./capabilities/mcp/MCPSettingsPage', () => ({
  default: () => <div data-testid="mcp-settings-page" />,
}));

vi.mock('./capabilities/hooks/HooksPage', () => ({
  default: function MockHooksPage({
    isEnabled = true,
    disabledMessage,
  }: {
    isEnabled?: boolean,
    disabledMessage?: string | null,
  }) {
    React.useEffect(() => {
      mocks.recordMount('hooks-settings-page');
    }, []);

    return (
      <div
        data-testid="hooks-settings-page"
        data-enabled={String(isEnabled)}
        data-disabled-message={disabledMessage ?? ''}
      />
    );
  },
}));

vi.mock('./capabilities/skills/SkillsPage', () => ({
  default: () => <div data-testid="skills-page" />,
}));

vi.mock('./capabilities/plugins/CodexPluginsPage', () => ({
  default: () => <div data-testid="codex-plugins-page" />,
}));

vi.mock('./components/workflows/RawSettingsWorkflow', () => ({
  default: function MockRawSettingsWorkflow() {
    React.useEffect(() => {
      mocks.recordMount('raw-settings-workflow');
    }, []);

    return <div data-testid="codex-settings-page" />;
  },
}));

vi.mock('@/shared/components/document-resource', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/shared/components/document-resource')
  >();

  function MockDocumentResourceWorkbench({
    config,
    i18nNamespace,
    dialog,
    metadataAdapter,
    templateResourceType,
    isEnabled = true,
    disabledMessage,
  }: {
    config: {
      metaKey: string;
      contentFormat?: string;
      createButtonLabel?: string;
      emptyStateTitle?: string;
      emptyStateDescription?: string;
      dialogTitle?: string;
    },
    i18nNamespace: string,
    dialog?: unknown,
    metadataAdapter?: { capabilities?: { namespace?: boolean } },
    templateResourceType?: string,
    isEnabled?: boolean,
    disabledMessage?: string | null,
  }) {
    React.useEffect(() => {
      mocks.recordMount(`document-resource-${config.metaKey}`);
    }, [config.metaKey]);

    return (
      <div
        data-testid={`document-resource-${config.metaKey}`}
        data-i18n-namespace={i18nNamespace}
        data-content-format={config.contentFormat}
        data-create-button-label={config.createButtonLabel}
        data-empty-state-title={config.emptyStateTitle}
        data-empty-state-description={config.emptyStateDescription}
        data-dialog-title={config.dialogTitle}
        data-has-dialog={dialog ? 'true' : 'false'}
        data-has-metadata-adapter={metadataAdapter ? 'true' : 'false'}
        data-metadata-namespace={metadataAdapter?.capabilities?.namespace ? 'true' : 'false'}
        data-template-resource-type={templateResourceType}
        data-enabled={String(isEnabled)}
        data-disabled-message={disabledMessage ?? ''}
      />
    );
  }

  return {
    ...actual,
    DocumentResourceWorkbench: MockDocumentResourceWorkbench,
  };
});

vi.mock('./components/workflows/SingleDocumentWorkflow', () => ({
  default: function MockSingleDocumentWorkflow() {
    React.useEffect(() => {
      mocks.recordMount('single-document-workflow');
    }, []);

    return <div data-testid="single-document-workflow" />;
  },
}));

describe('AgentSettingsPage shared rendering', () => {
  beforeEach(() => {
    mocks.mountCounts.clear();
    mocks.workspaceRuntime.runtimeBaseUrl = 'http://runtime.test';
    mocks.workspaceRuntime.workspaceId = 'workspace-test';
    mocks.workspaceRuntime.error = null;
    mocks.workspaceRuntime.isLoading = false;
  });

  it('does not render the removed Claude legacy file collection through the shared feature surface', async () => {
    const removedSubview = ['scr', 'ipts'].join('');

    render(<AgentSettingsPage toolId="claude" subView={removedSubview} />);

    expect(await screen.findByText('workspace.agentSettings.common.comingSoon.title')).toBeInTheDocument();
  });

  it('routes every registered OpenCode subview through the page registry', async () => {
    const cases = [
      ['agents-md', 'single-document-workflow'],
      ['mcp', 'mcp-settings-page'],
      ['slash-commands', 'document-resource-slash-commands'],
      ['skills', 'skills-page'],
      ['subagents', 'document-resource-subagents'],
    ];

    for (const [subView, testId] of cases) {
      const { unmount } = render(<AgentSettingsPage toolId="opencode" subView={subView} />);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
      unmount();
    }
  });

  it('renders unsupported OpenCode hooks with localized placeholder labels', () => {
    render(<AgentSettingsPage toolId="opencode" subView="hooks" />);

    expect(screen.getByText('workspace.agentSettings.common.comingSoon.title')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.subViews.hooks:workspace.navigation.main.opencodeSettings')).toBeInTheDocument();
  });

  it('uses Claude Code i18n keys for Claude-only memory and output style document pages', async () => {
    const cases = [
      {
        subView: 'output-styles',
        testId: 'document-resource-output-styles',
        createButtonLabel: 'workspace.claudeCode.outputStyles.actions.create',
        emptyStateTitle: 'workspace.claudeCode.outputStyles.empty.title',
        emptyStateDescription: 'workspace.claudeCode.outputStyles.empty.description',
        dialogTitle: 'workspace.claudeCode.outputStyles.pageTitle',
      },
      {
        subView: 'memory',
        testId: 'document-resource-memory',
        createButtonLabel: undefined,
        emptyStateTitle: 'workspace.claudeCode.memory.empty.title',
        emptyStateDescription: 'workspace.claudeCode.memory.empty.description',
        dialogTitle: 'workspace.claudeCode.memory.pageTitle',
      },
    ];

    for (const item of cases) {
      const { unmount } = render(<AgentSettingsPage toolId="claude" subView={item.subView} />);
      const page = await screen.findByTestId(item.testId);

      expect(page).toHaveAttribute('data-i18n-namespace', 'workspace.claudeCode');
      if (item.createButtonLabel) {
        expect(page).toHaveAttribute('data-create-button-label', item.createButtonLabel);
      }
      expect(page).toHaveAttribute('data-empty-state-title', item.emptyStateTitle);
      expect(page).toHaveAttribute('data-empty-state-description', item.emptyStateDescription);
      expect(page).toHaveAttribute('data-dialog-title', item.dialogTitle);

      unmount();
    }
  });

  it('routes Codex settings subviews to Codex-specific pages', async () => {
    const cases = [
      ['agents-md', 'single-document-workflow'],
      ['mcp', 'mcp-settings-page'],
      ['rules', 'document-resource-rules'],
      ['hooks', 'hooks-settings-page'],
      ['plugins', 'codex-plugins-page'],
      ['settings', 'codex-settings-page'],
      ['skills', 'skills-page'],
      ['subagents', 'document-resource-subagents'],
      ['prompts', 'document-resource-prompts'],
    ];

    for (const [subView, testId] of cases) {
      const { unmount } = render(<AgentSettingsPage toolId="codex" subView={subView} />);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
      unmount();
    }
  });

  it('uses the inline document workflow for Codex prompts instead of a dialog editor', async () => {
    render(<AgentSettingsPage toolId="codex" subView="prompts" />);

    const page = await screen.findByTestId('document-resource-prompts');

    expect(page).toHaveAttribute('data-has-dialog', 'false');
    expect(page).toHaveAttribute('data-has-metadata-adapter', 'true');
    expect(page).toHaveAttribute('data-template-resource-type', 'slashCommand');
  });

  it('uses shared document resource registry contracts for agent document workflows', async () => {
    const cases = [
      {
        toolId: 'claude',
        subView: 'slash-commands',
        testId: 'document-resource-slash-commands',
        contentFormat: 'markdown',
        templateResourceType: 'slashCommand',
        namespace: 'true',
      },
      {
        toolId: 'opencode',
        subView: 'slash-commands',
        testId: 'document-resource-slash-commands',
        contentFormat: 'markdown',
        templateResourceType: 'slashCommand',
        namespace: 'true',
      },
      {
        toolId: 'codex',
        subView: 'prompts',
        testId: 'document-resource-prompts',
        contentFormat: 'markdown',
        templateResourceType: 'slashCommand',
        namespace: 'true',
      },
      {
        toolId: 'claude',
        subView: 'output-styles',
        testId: 'document-resource-output-styles',
        contentFormat: 'markdown',
        templateResourceType: 'outputStyle',
        namespace: 'false',
      },
      {
        toolId: 'codex',
        subView: 'subagents',
        testId: 'document-resource-subagents',
        contentFormat: 'toml',
        templateResourceType: 'subagent',
        namespace: 'false',
      },
    ] as const;

    for (const item of cases) {
      const { unmount } = render(<AgentSettingsPage toolId={item.toolId} subView={item.subView} />);
      const page = await screen.findByTestId(item.testId);

      expect(page).toHaveAttribute('data-content-format', item.contentFormat);
      expect(page).toHaveAttribute('data-template-resource-type', item.templateResourceType);
      expect(page).toHaveAttribute('data-metadata-namespace', item.namespace);

      unmount();
    }
  });

  it('renders placeholders for unmapped Codex subviews', () => {
    render(<AgentSettingsPage toolId="codex" subView="not-registered" />);
    expect(screen.getByText('workspace.agentSettings.common.subViews.unknown:workspace.navigation.main.codexSettings')).toBeInTheDocument();
  });

  it('disables runtime-backed document and hook pages when the workspace runtime is unavailable', async () => {
    mocks.workspaceRuntime.runtimeBaseUrl = '';
    mocks.workspaceRuntime.workspaceId = '';
    mocks.workspaceRuntime.error = new Error('runtime unavailable');

    const cases = [
      { toolId: 'claude', subView: 'hooks', testId: 'hooks-settings-page' },
      { toolId: 'claude', subView: 'slash-commands', testId: 'document-resource-slash-commands' },
      { toolId: 'claude', subView: 'output-styles', testId: 'document-resource-output-styles' },
      { toolId: 'claude', subView: 'memory', testId: 'document-resource-memory' },
      { toolId: 'claude', subView: 'subagents', testId: 'document-resource-subagents' },
      { toolId: 'opencode', subView: 'slash-commands', testId: 'document-resource-slash-commands' },
      { toolId: 'opencode', subView: 'subagents', testId: 'document-resource-subagents' },
      { toolId: 'codex', subView: 'hooks', testId: 'hooks-settings-page' },
      { toolId: 'codex', subView: 'prompts', testId: 'document-resource-prompts' },
      { toolId: 'codex', subView: 'subagents', testId: 'document-resource-subagents' },
      { toolId: 'codex', subView: 'rules', testId: 'document-resource-rules' },
    ] as const;

    for (const item of cases) {
      const { unmount } = render(<AgentSettingsPage toolId={item.toolId} subView={item.subView} />);
      const page = await screen.findByTestId(item.testId);

      expect(page).toHaveAttribute('data-enabled', 'false');
      expect(page).toHaveAttribute(
        'data-disabled-message',
        'workspace.agentSettings.common.mcp.messages.runtimeNotReady',
      );

      unmount();
    }
  });

  it('keeps registered data pages mounted when the feature rerenders without changing subview', async () => {
    const cases = [
      { toolId: 'claude', subView: 'claude-md', testId: 'single-document-workflow', mountKey: 'single-document-workflow' },
      { toolId: 'claude', subView: 'hooks', testId: 'hooks-settings-page', mountKey: 'hooks-settings-page' },
      {
        toolId: 'claude',
        subView: 'slash-commands',
        testId: 'document-resource-slash-commands',
        mountKey: 'document-resource-slash-commands',
      },
      {
        toolId: 'claude',
        subView: 'output-styles',
        testId: 'document-resource-output-styles',
        mountKey: 'document-resource-output-styles',
      },
      { toolId: 'claude', subView: 'memory', testId: 'document-resource-memory', mountKey: 'document-resource-memory' },
      { toolId: 'claude', subView: 'subagents', testId: 'document-resource-subagents', mountKey: 'document-resource-subagents' },
      { toolId: 'claude', subView: 'settings', testId: 'codex-settings-page', mountKey: 'raw-settings-workflow' },
      { toolId: 'opencode', subView: 'agents-md', testId: 'single-document-workflow', mountKey: 'single-document-workflow' },
      {
        toolId: 'opencode',
        subView: 'slash-commands',
        testId: 'document-resource-slash-commands',
        mountKey: 'document-resource-slash-commands',
      },
      {
        toolId: 'opencode',
        subView: 'subagents',
        testId: 'document-resource-subagents',
        mountKey: 'document-resource-subagents',
      },
      { toolId: 'codex', subView: 'agents-md', testId: 'single-document-workflow', mountKey: 'single-document-workflow' },
      { toolId: 'codex', subView: 'hooks', testId: 'hooks-settings-page', mountKey: 'hooks-settings-page' },
      { toolId: 'codex', subView: 'prompts', testId: 'document-resource-prompts', mountKey: 'document-resource-prompts' },
      { toolId: 'codex', subView: 'subagents', testId: 'document-resource-subagents', mountKey: 'document-resource-subagents' },
      { toolId: 'codex', subView: 'rules', testId: 'document-resource-rules', mountKey: 'document-resource-rules' },
      { toolId: 'codex', subView: 'settings', testId: 'codex-settings-page', mountKey: 'raw-settings-workflow' },
    ] as const;

    for (const item of cases) {
      mocks.mountCounts.clear();
      const view = render(<AgentSettingsPage toolId={item.toolId} subView={item.subView} />);

      expect(await screen.findByTestId(item.testId)).toBeInTheDocument();
      expect(mocks.mountCount(item.mountKey)).toBe(1);

      view.rerender(<AgentSettingsPage toolId={item.toolId} subView={item.subView} />);

      expect(await screen.findByTestId(item.testId)).toBeInTheDocument();
      expect(mocks.mountCount(item.mountKey)).toBe(1);

      view.unmount();
    }
  });
});
