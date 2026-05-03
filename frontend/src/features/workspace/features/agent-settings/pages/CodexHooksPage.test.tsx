import React from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CodexHooksPage from './CodexHooksPage';

const apiMock = {
  getCodexHooks: vi.fn(),
  listCodexHooksScopes: vi.fn(),
  listCodexPlugins: vi.fn(),
  updateCodexHooks: vi.fn(),
  enableCodexHooks: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('CodexHooksPage', () => {
  const hooksScopesResponse = (project: Record<string, unknown>, user: Record<string, unknown>) => ({
    workspaceId: 'ws-1',
    scopes: [project, user],
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [] });
    apiMock.updateCodexHooks.mockImplementation((_baseUrl, _workspaceId, layer, content) => Promise.resolve({
      workspaceId: 'ws-1',
      layer,
      path: layer === 'project' ? '/workspace/.codex/hooks.json' : '/home/developer/.codex/hooks.json',
      content,
      exists: true,
      featureEnabled: true,
      inlineHooks: [],
      entries: [],
      eventMetadata: [],
    }));
    apiMock.listCodexHooksScopes.mockResolvedValue(hooksScopesResponse(
      {
        workspaceId: 'ws-1',
        layer: 'project',
        path: '/workspace/.codex/hooks.json',
        content: JSON.stringify({
          PreToolUse: [
            {
              matcher: '*',
              hooks: [{ type: 'command', command: 'echo json', timeout: 600 }],
            },
          ],
        }),
        exists: true,
        featureEnabled: false,
        inlineHooks: [
          {
            layer: 'project',
            event: 'PreToolUse',
            hook: { type: 'command', command: 'echo inline' },
          },
        ],
        entries: [
          {
            id: 'project:PreToolUse:0',
            event: 'PreToolUse',
            index: 0,
            matcher: '*',
            actions: [{ type: 'command', command: 'echo json', timeout: 600, statusMessage: 'Checking JSON' }],
            action: { type: 'command', command: 'echo json', timeout: 600, statusMessage: 'Checking JSON' },
            source: 'hooks_json',
            layer: 'project',
            readOnly: false,
            raw: { matcher: '*', hooks: [{ type: 'command', command: 'echo json', timeout: 600, statusMessage: 'Checking JSON' }] },
          },
          {
            id: 'inline:project:0:PreToolUse:0',
            event: 'PreToolUse',
            index: 0,
            matcher: '*',
            actions: [{ type: 'command', command: 'echo inline', statusMessage: 'Checking inline' }],
            action: { type: 'command', command: 'echo inline', statusMessage: 'Checking inline' },
            source: 'inline_config',
            layer: 'project',
            readOnly: true,
            raw: { type: 'command', command: 'echo inline', statusMessage: 'Checking inline' },
          },
          {
            id: 'plugin:demo@local:SessionStart:0',
            event: 'SessionStart',
            index: 0,
            matcher: 'startup',
            actions: [{ type: 'command', command: 'echo plugin', statusMessage: 'Loading plugin' }],
            action: { type: 'command', command: 'echo plugin', statusMessage: 'Loading plugin' },
            source: 'plugin',
            layer: null,
            readOnly: true,
            pluginId: 'demo@local',
            pluginName: 'Demo',
            marketplaceName: 'local',
            raw: { matcher: 'startup', hooks: [{ type: 'command', command: 'echo plugin', statusMessage: 'Loading plugin' }] },
          },
          {
            id: 'project:requirements:Stop:0',
            event: 'Stop',
            index: 0,
            matcher: null,
            actions: [{ type: 'command', command: 'echo requirements', statusMessage: 'Checking requirements' }],
            action: { type: 'command', command: 'echo requirements', statusMessage: 'Checking requirements' },
            source: 'project',
            layer: 'project',
            readOnly: true,
            raw: { type: 'command', command: 'echo requirements', statusMessage: 'Checking requirements' },
          },
        ],
        eventMetadata: [
          { event: 'SessionStart', scope: 'session_start', matcherSupported: true, matcherTarget: 'source', matcherExamples: ['startup', 'resume', 'clear'] },
          { event: 'PreToolUse', scope: 'turn', matcherSupported: true, matcherTarget: 'tool_name', matcherExamples: ['Bash', 'apply_patch'] },
          { event: 'Stop', scope: 'turn', matcherSupported: false, matcherTarget: 'none', matcherExamples: [] },
        ],
      },
      {
        workspaceId: 'ws-1',
        layer: 'user',
        path: '/home/developer/.codex/hooks.json',
        content: '{}',
        exists: false,
        featureEnabled: false,
        inlineHooks: [],
        entries: [],
        eventMetadata: [],
      },
    ));
    apiMock.enableCodexHooks.mockResolvedValue({ workspaceId: 'ws-1', featureEnabled: true });
  });

  it('renders structured hooks, read-only source hooks, and the feature enable action', async () => {
    const user = userEvent.setup();

    render(<CodexHooksPage />);

    expect(await screen.findByText('workspace.agentSettings.codex.hooks.featureWarning.title')).toBeInTheDocument();
    expect(screen.getByText('echo json')).toBeInTheDocument();
    expect(screen.getByText('echo inline')).toBeInTheDocument();
    expect(screen.getByText('echo plugin')).toBeInTheDocument();
    expect(screen.getByText('echo requirements')).toBeInTheDocument();
    expect(screen.getAllByText('workspace.agentSettings.codex.hooks.sources.inline_config').length).toBeGreaterThan(0);
    expect(screen.getAllByText('workspace.agentSettings.codex.hooks.sources.plugin').length).toBeGreaterThan(0);
    expect(screen.getAllByText('workspace.agentSettings.codex.hooks.sources.project').length).toBeGreaterThan(0);
    expect(screen.queryByText('workspace.agentSettings.codex.hooks.sources.managed')).not.toBeInTheDocument();
    expect(screen.getAllByLabelText('workspace.agentSettings.codex.hooks.actions.edit')).toHaveLength(1);

    await user.click(screen.getByText('workspace.agentSettings.codex.hooks.actions.enableFeature'));

    await waitFor(() => expect(apiMock.enableCodexHooks).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'project',
    ));
  });

  it('saves statusMessage from the structured hook dialog', async () => {
    const user = userEvent.setup();

    render(<CodexHooksPage />);

    await screen.findByText('echo json');
    await user.click(screen.getByLabelText('workspace.agentSettings.codex.hooks.actions.edit'));
    const statusInput = await screen.findByPlaceholderText('workspace.agentSettings.codex.hooks.dialog.execution.statusMessagePlaceholder');
    await user.clear(statusInput);
    await user.type(statusInput, 'Reviewing Bash command');
    await user.click(screen.getByText('workspace.agentSettings.codex.hooks.dialog.actions.save'));

    await waitFor(() => expect(apiMock.updateCodexHooks).toHaveBeenCalled());
    const content = apiMock.updateCodexHooks.mock.calls[0][3];
    expect(JSON.parse(content).PreToolUse[0].hooks[0].statusMessage).toBe('Reviewing Bash command');
  });

  it('hides plugin scope filter when loaded hooks do not include plugin entries or enabled plugins', async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: () => undefined,
    });
    apiMock.listCodexHooksScopes.mockResolvedValueOnce(hooksScopesResponse(
      {
        workspaceId: 'ws-1',
        layer: 'project',
        path: '/workspace/.codex/hooks.json',
        content: '{}',
        exists: true,
        featureEnabled: true,
        inlineHooks: [],
        entries: [],
        eventMetadata: [],
      },
      {
        workspaceId: 'ws-1',
        layer: 'user',
        path: '/home/developer/.codex/hooks.json',
        content: '{}',
        exists: false,
        featureEnabled: false,
        inlineHooks: [],
        entries: [],
        eventMetadata: [],
      },
    ));

    render(<CodexHooksPage />);

    expect(await screen.findByText('workspace.agentSettings.codex.hooks.header.title')).toBeInTheDocument();
    await user.click(screen.getAllByRole('combobox')[0]);

    expect(screen.getByText('workspace.agentSettings.codex.hooks.filters.scope.options.project')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.codex.hooks.filters.scope.options.plugin')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.codex.hooks.filters.scope.options.managed')).not.toBeInTheDocument();
  });

  it('loads all Codex hook scopes through the aggregate endpoint', async () => {
    render(<CodexHooksPage />);

    await screen.findByText('echo json');

    expect(apiMock.listCodexHooksScopes).toHaveBeenCalledTimes(1);
    expect(apiMock.getCodexHooks).not.toHaveBeenCalled();
    expect(apiMock.listCodexPlugins).not.toHaveBeenCalled();
  });
});
