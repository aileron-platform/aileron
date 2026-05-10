import React from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HooksSettingsPage from './HooksSettingsPage';

const apiMock = {
  listHookScopes: vi.fn(),
  updateHookScope: vi.fn(),
  deleteHookScope: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
      error: null,
      isLoading: false,
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values?.count !== undefined ? `${key}:${values.count}` : key
    ),
  }),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

vi.mock('./dialogs/WorkspaceHookDialog', () => ({
  WorkspaceHookDialog: ({
    open,
    mode,
    hook,
    onClose,
  }: {
    open: boolean;
    mode: 'create' | 'edit';
    hook: { eventName: string } | null;
    onClose: () => void;
  }) => (open ? (
    <div>
      <p data-testid="hook-dialog-state">
        {mode}:{hook?.eventName ?? 'none'}
      </p>
      <button type="button" onClick={onClose}>
        workspace.agentSettings.common.hooks.dialog.actions.cancel
      </button>
    </div>
  ) : null),
}));

const installSelectPolyfills = () => {
  Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
    configurable: true,
    value: () => false,
  });
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: () => undefined,
  });
};

describe('HooksSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listHookScopes.mockResolvedValue({
      workspaceId: 'ws-1',
      scopes: [
        {
          scope: 'project',
          hooks: {
            PreToolUse: [
              {
                matcher: 'Bash',
                hooks: [{ type: 'command', command: 'echo project', timeout: 30 }],
              },
            ],
          },
        },
        {
          scope: 'user',
          hooks: {
            SessionStart: [
              {
                matcher: 'startup',
                hooks: [{ type: 'command', command: 'echo user', timeout: 30 }],
              },
            ],
          },
        },
      ],
    });
    apiMock.updateHookScope.mockImplementation((_baseUrl, _workspaceId, scope, hooks) => Promise.resolve({ scope, hooks }));
    apiMock.deleteHookScope.mockResolvedValue({ scope: 'project' });
  });

  it('filters hooks by search and scope dropdown', async () => {
    const user = userEvent.setup();
    installSelectPolyfills();

    render(<HooksSettingsPage availableScopes={['project', 'user']} />);

    expect(await screen.findByText('echo project')).toBeInTheDocument();
    expect(screen.getByText('echo user')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('workspace.agentSettings.common.hooks.search.placeholder'), 'startup');

    expect(screen.queryByText('echo project')).not.toBeInTheDocument();
    expect(screen.getByText('echo user')).toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText('workspace.agentSettings.common.hooks.search.placeholder'));
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: /workspace\.agentSettings\.common\.hooks\.filters\.scope\.options\.project/ }));

    expect(screen.getByText('echo project')).toBeInTheDocument();
    expect(screen.queryByText('echo user')).not.toBeInTheDocument();
  });

  it('opens create and edit dialogs through the shared workbench controller', async () => {
    const user = userEvent.setup();

    render(<HooksSettingsPage availableScopes={['project', 'user']} />);

    expect(await screen.findByText('echo project')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /workspace\.agentSettings\.common\.hooks\.actions\.create/ }));
    expect(await screen.findByTestId('hook-dialog-state')).toHaveTextContent('create:none');
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.hooks.dialog.actions.cancel' }));
    await waitFor(() => expect(screen.queryByTestId('hook-dialog-state')).not.toBeInTheDocument());

    await user.click(screen.getAllByLabelText('workspace.agentSettings.common.hooks.actions.edit')[0]);
    expect(await screen.findByTestId('hook-dialog-state')).toHaveTextContent('edit:PreToolUse');
  });

  it('deletes hooks from the page callback', async () => {
    const user = userEvent.setup();

    render(<HooksSettingsPage availableScopes={['project', 'user']} />);

    expect(await screen.findByText('echo project')).toBeInTheDocument();
    await user.click(screen.getAllByLabelText('workspace.agentSettings.common.hooks.actions.delete')[0]);

    await waitFor(() => expect(apiMock.deleteHookScope).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
    ));
  });

  it('renders every matcher and action in hook cards', async () => {
    apiMock.listHookScopes.mockResolvedValue({
      workspaceId: 'ws-1',
      scopes: [
        {
          scope: 'project',
          hooks: {
            PreToolUse: [
              {
                matcher: 'Bash',
                hooks: [
                  { type: 'command', command: 'echo one', timeout: 30 },
                  { type: 'command', command: 'echo two', timeout: 30 },
                ],
              },
              {
                matcher: 'Write',
                hooks: [
                  { type: 'command', command: 'write one', timeout: 30 },
                  { type: 'command', command: 'write two', timeout: 30 },
                ],
              },
            ],
          },
        },
        { scope: 'user', hooks: {} },
      ],
    });

    render(<HooksSettingsPage availableScopes={['project', 'user']} />);

    expect(await screen.findByText('echo one')).toBeInTheDocument();
    expect(screen.getByText('echo two')).toBeInTheDocument();
    expect(screen.getByText('write one')).toBeInTheDocument();
    expect(screen.getByText('write two')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.claude.hooks.card.summary.matchers:2')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.claude.hooks.card.summary.commands:4')).toBeInTheDocument();
  });

  it('renders installed plugin hooks grouped by event type as read-only hook cards', async () => {
    apiMock.listHookScopes.mockResolvedValue({
      workspaceId: 'ws-1',
      scopes: [
        { scope: 'project', hooks: {} },
        { scope: 'user', hooks: {} },
        { scope: 'local', hooks: {} },
        {
          scope: 'plugin',
          hooks: {
            SessionStart: [
              {
                matcher: 'm1',
                pluginName: 'asdf',
                marketplaceName: 'local-marketplace',
                hooks: [{ type: 'command', command: 'echo "m1"', timeout: 600 }],
              },
              {
                matcher: 'm2',
                pluginName: 'asdf',
                marketplaceName: 'local-marketplace',
                hooks: [{ type: 'http', url: 'http://m2', timeout: 30 }],
              },
            ],
          },
        },
      ],
    });

    render(<HooksSettingsPage availableScopes={['project', 'user', 'local', 'plugin']} />);

    expect(await screen.findByText('echo "m1"')).toBeInTheDocument();
    expect(screen.getByText('http://m2')).toBeInTheDocument();
    expect(screen.getByText('common.hookEvents.SessionStart.description')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.hooks.stats.hooks:1')).toBeInTheDocument();
    expect(screen.getByText('asdf@local-marketplace')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.claude.hooks.card.summary.matchers:2')).toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.hooks.actions.edit')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.hooks.actions.delete')).not.toBeInTheDocument();
  });
});
