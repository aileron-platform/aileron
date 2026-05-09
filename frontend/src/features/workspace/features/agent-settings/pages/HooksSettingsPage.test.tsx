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
    expect(await screen.findByText('workspace.agentSettings.common.hooks.dialog.title.create')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.hooks.dialog.actions.cancel' }));

    await user.click(screen.getAllByLabelText('workspace.agentSettings.common.hooks.actions.edit')[0]);
    expect(await screen.findByText('workspace.agentSettings.common.hooks.dialog.title.edit')).toBeInTheDocument();
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
});
