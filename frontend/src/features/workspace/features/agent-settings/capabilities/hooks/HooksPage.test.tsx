import React from 'react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HooksPage from './HooksPage';
import type { HookSource } from '../../model/hookSource';

const toastMock = vi.fn();

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values?.count !== undefined ? `${key}:${values.count}` : key
    ),
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/shared/components/hook-workflow', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/components/hook-workflow')>();
  return {
    ...actual,
    HookDialog: ({
      open,
      mode,
      hook,
      labels,
      options,
      onSubmit,
      onClose,
    }: {
      open: boolean;
      mode: 'create' | 'edit';
      hook: { eventName: string } | null;
      labels: {
        title: string;
        description: string;
        submit: string;
        event: { label: string };
        matcherActions: {
          matcherSectionTitle: string;
          matcherPatternHelp: (eventName: string) => string[];
          executionTimeoutLabel: string;
          executionCommandLabel: string;
        };
      };
      options: {
        scopes: Array<{ label: string }>;
        executionTypes: Array<{ label: string }>;
        executionShells?: Array<{ label: string }>;
      };
      onSubmit: (hook: { id: string; scope: 'project'; eventName: string; matchers: Array<{ matcher: string; hooks: Array<{ type: 'command'; command: string }> }> }) => void;
      onClose: () => void;
    }) => (open ? (
      <div>
        <p data-testid="hook-dialog-state">{mode}:{hook?.eventName ?? 'none'}</p>
        <p data-testid="hook-dialog-title">{labels.title}</p>
        <p data-testid="hook-dialog-description">{labels.description}</p>
        <p data-testid="hook-dialog-submit-label">{labels.submit}</p>
        <p data-testid="hook-dialog-scope-label">{options.scopes[0]?.label}</p>
        <p data-testid="hook-dialog-event-label">{labels.event.label}</p>
        <p data-testid="hook-dialog-matcher-label">{labels.matcherActions.matcherSectionTitle}</p>
        <p data-testid="hook-dialog-timeout-label">{labels.matcherActions.executionTimeoutLabel}</p>
        <p data-testid="hook-dialog-command-label">{labels.matcherActions.executionCommandLabel}</p>
        <p data-testid="hook-dialog-type-label">{options.executionTypes[0]?.label}</p>
        <p data-testid="hook-dialog-shell-label">{options.executionShells?.[0]?.label}</p>
        <p data-testid="hook-dialog-hint">{labels.matcherActions.matcherPatternHelp('PreToolUse')[0]}</p>
        <button
          type="button"
          onClick={() => onSubmit({
            id: hook?.eventName ? 'project:Edited' : 'project:Created',
            scope: 'project',
            eventName: hook?.eventName ? 'Edited' : 'Created',
            matchers: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'echo saved' }] }],
          })}
        >
          save
        </button>
        <button type="button" onClick={onClose}>cancel</button>
      </div>
    ) : null),
  };
});

const renderHooksPage = (source: HookSource) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <HooksPage
        queryKey={['test-hooks']}
        source={source}
        provider="claude-code"
        availableScopes={['project', 'user']}
        i18nNamespace="workspace.agentSettings.common"
      />
    </QueryClientProvider>,
  );
};

describe('HooksPage', () => {
  let source: HookSource;

  beforeEach(() => {
    toastMock.mockReset();
    source = {
      list: vi.fn().mockResolvedValue([
        {
          id: 'project:PreToolUse',
          scope: 'project',
          eventName: 'PreToolUse',
          matchers: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'echo project' }] }],
        },
      ]),
      save: vi.fn().mockResolvedValue(undefined),
      remove: vi.fn().mockResolvedValue(undefined),
    };
  });

  it('renders, searches, saves, and removes hooks through the source', async () => {
    const user = userEvent.setup();
    renderHooksPage(source);

    expect(await screen.findByText('echo project')).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText('workspace.agentSettings.common.hooks.search.placeholder'), 'missing');
    expect(screen.queryByText('echo project')).not.toBeInTheDocument();
    await user.clear(screen.getByPlaceholderText('workspace.agentSettings.common.hooks.search.placeholder'));

    await user.click(screen.getByLabelText('workspace.agentSettings.common.hooks.actions.edit'));
    expect(await screen.findByTestId('hook-dialog-state')).toHaveTextContent('edit:PreToolUse');
    expect(screen.getByTestId('hook-dialog-title')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.title.edit');
    expect(screen.getByTestId('hook-dialog-description')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.description');
    expect(screen.getByTestId('hook-dialog-submit-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.actions.save');
    expect(screen.getByTestId('hook-dialog-scope-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.scope.options.project');
    expect(screen.getByTestId('hook-dialog-event-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.event.label');
    expect(screen.getByTestId('hook-dialog-matcher-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.matcher.sectionTitle');
    expect(screen.getByTestId('hook-dialog-timeout-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.execution.timeoutLabel');
    expect(screen.getByTestId('hook-dialog-command-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.execution.commandLabel');
    expect(screen.getByTestId('hook-dialog-type-label')).toHaveTextContent('workspace.agentSettings.claude.hooks.dialog.types.command.label');
    expect(screen.getByTestId('hook-dialog-shell-label')).toHaveTextContent('workspace.agentSettings.claude.hooks.dialog.execution.shell.options.bash');
    expect(screen.getByTestId('hook-dialog-hint')).toHaveTextContent('workspace.agentSettings.claude.hooks.dialog.matcherHints.tool.help');
    await user.click(screen.getByText('save'));
    await waitFor(() => expect(source.save).toHaveBeenCalledWith(
      expect.objectContaining({ eventName: 'Edited' }),
      expect.objectContaining({ eventName: 'PreToolUse' }),
    ));

    await user.click(screen.getByLabelText('workspace.agentSettings.common.hooks.actions.delete'));
    await waitFor(() => expect(source.remove).toHaveBeenCalledWith(expect.objectContaining({ eventName: 'PreToolUse' })));
  });

  it('opens the create dialog from the header action when the list is empty', async () => {
    const user = userEvent.setup();
    source.list = vi.fn().mockResolvedValue([]);
    renderHooksPage(source);

    await waitFor(() => expect(source.list).toHaveBeenCalled());
    await user.click(screen.getByText('workspace.agentSettings.common.hooks.actions.create'));
    expect(await screen.findByTestId('hook-dialog-state')).toHaveTextContent('create:none');
    expect(screen.getByTestId('hook-dialog-title')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.title.create');
    expect(screen.getByTestId('hook-dialog-submit-label')).toHaveTextContent('workspace.agentSettings.common.hooks.dialog.actions.create');
  });

  it('shows optional feature enablement banner', async () => {
    const user = userEvent.setup();
    source.featureEnablement = {
      isEnabled: vi.fn().mockResolvedValue(false),
      enable: vi.fn().mockResolvedValue(undefined),
    };
    renderHooksPage(source);

    expect(await screen.findByText('workspace.agentSettings.common.hooks.featureWarning.title')).toBeInTheDocument();
    await user.click(screen.getByText('workspace.agentSettings.common.hooks.actions.enableFeature'));
    await waitFor(() => expect(source.featureEnablement?.enable).toHaveBeenCalled());
  });

  it('keeps an untrusted Codex plugin hook visible while updating trust independently', async () => {
    const user = userEvent.setup();
    const onProviderResourceMutation = vi.fn().mockResolvedValue(undefined);
    source = {
      list: vi.fn().mockResolvedValue([{
        id: 'plugin:demo:SessionStart',
        scope: 'plugin',
        eventName: 'SessionStart',
        matchers: [{
          matcher: '*',
          hooks: [{ type: 'command', command: 'echo plugin' }],
        }],
        pluginId: 'demo@local',
        pluginName: 'Demo',
        marketplaceName: 'local',
        readOnly: true,
        source: 'plugin',
        trustState: 'untrusted',
        trusted: false,
        effective: false,
        trustRevision: 'trust-r1',
      }]),
      save: vi.fn().mockResolvedValue(undefined),
      remove: vi.fn().mockResolvedValue(undefined),
      pluginTrust: {
        update: vi.fn().mockResolvedValue(undefined),
      },
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <HooksPage
          queryKey={['codex-plugin-hooks']}
          source={source}
          provider="codex"
          availableScopes={['project', 'user', 'plugin']}
          i18nNamespace="workspace.agentSettings.common"
          onProviderResourceMutation={onProviderResourceMutation}
        />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('echo plugin')).toBeInTheDocument();
    expect(screen.getByRole('region', {
      name: 'workspace.agentSettings.common.hooks.pluginTrust.title',
    })).toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.hooks.actions.edit')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.hooks.actions.delete')).not.toBeInTheDocument();

    await user.click(screen.getByRole('switch', {
      name: 'workspace.agentSettings.common.hooks.pluginTrust.fields.trusted',
    }));

    await waitFor(() => expect(source.pluginTrust?.update).toHaveBeenCalledWith(
      expect.objectContaining({
        pluginId: 'demo@local',
        trustRevision: 'trust-r1',
      }),
      true,
    ));
    await waitFor(() => expect(onProviderResourceMutation).toHaveBeenCalledTimes(1));
    expect(screen.getByText('echo plugin')).toBeInTheDocument();
  });

  it('maps hook trust backend errors without exposing raw messages', async () => {
    const user = userEvent.setup();
    source = {
      list: vi.fn().mockResolvedValue([{
        id: 'plugin:demo:SessionStart',
        scope: 'plugin',
        eventName: 'SessionStart',
        matchers: [{
          matcher: '*',
          hooks: [{ type: 'command', command: 'echo plugin' }],
        }],
        pluginId: 'demo@local',
        pluginName: 'Demo',
        marketplaceName: 'local',
        readOnly: true,
        source: 'plugin',
        trustState: 'untrusted',
        trusted: false,
        effective: false,
        trustRevision: 'trust-r1',
      }]),
      save: vi.fn().mockResolvedValue(undefined),
      remove: vi.fn().mockResolvedValue(undefined),
      pluginTrust: {
        update: vi.fn().mockRejectedValue(
          Object.assign(new Error('sensitive runtime detail'), {
            errorCode:
              'marketplace.settings.plugin_hook_trust_not_supported',
          }),
        ),
      },
    };
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <HooksPage
          queryKey={['codex-plugin-hook-error']}
          source={source}
          provider="codex"
          availableScopes={['project', 'user', 'plugin']}
          i18nNamespace="workspace.agentSettings.common"
        />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('echo plugin')).toBeInTheDocument();
    await user.click(screen.getByRole('switch', {
      name: 'workspace.agentSettings.common.hooks.pluginTrust.fields.trusted',
    }));

    await waitFor(() => expect(toastMock).toHaveBeenCalledWith({
      variant: 'destructive',
      title:
        'workspace.agentSettings.common.hooks.pluginTrust.messages.updateFailed',
      description:
        'workspace.agentSettings.pluginResources.controlErrors.hookTrustNotSupported',
    }));
    expect(JSON.stringify(toastMock.mock.calls)).not.toContain(
      'sensitive runtime detail',
    );
  });
});
