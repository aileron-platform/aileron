import React from 'react';
import { QueryClient } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AgentFileManager from './AgentFileManager';
import { AGENT_TOOL_CONFIGS } from '../agentToolConfigs';

const { settingsWorkflowPropsMock, workspacePermissions } = vi.hoisted(() => ({
  settingsWorkflowPropsMock: vi.fn(),
  workspacePermissions: {
    canWrite: true,
  },
}));

const apiMock = {
  listCodexFiles: vi.fn(),
  listCodexPlugins: vi.fn(),
  listPluginSkills: vi.fn(),
  refreshCache: vi.fn(),
};

const tMock = (key: string) => key;
vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
    permissions: workspacePermissions,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('./SettingsFileTreeWorkflow', () => ({
  SettingsFileTreeWorkflow: ({
    scopeOptions,
    isCollapsed,
    onToggleCollapse,
    onRefresh,
    ...props
  }: {
    scopeOptions: Array<{ value: string; label: string }>;
    isCollapsed: boolean;
    onToggleCollapse: () => void;
    onRefresh?: () => Promise<void>;
    resourceIdentity: {
      kind: string;
      attributes: Record<string, unknown>;
    };
  }) => {
    settingsWorkflowPropsMock({ scopeOptions, isCollapsed, onRefresh, ...props });
    return (
      <div>
      <button type="button" aria-label="toggle second column" onClick={onToggleCollapse}>
        {isCollapsed ? 'expand' : 'collapse'}
      </button>
      {onRefresh ? (
        <button type="button" aria-label="refresh collection" onClick={() => void onRefresh()}>
          refresh
        </button>
      ) : null}
      {scopeOptions.map((option) => (
        <span key={option.value}>{option.label}</span>
      ))}
      </div>
    );
  },
}));

vi.mock('../api/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('AgentFileManager Codex plugin scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspacePermissions.canWrite = true;
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [] });
    apiMock.refreshCache.mockResolvedValue({ refreshed: true });
  });

  it('shows plugin scope whenever Codex skills support plugins', async () => {
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('workspace.agentSettings.common.skills.scope.all')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.skills.scope.project')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.skills.scope.plugin')).toBeInTheDocument();
    expect(settingsWorkflowPropsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      resourceIdentity: {
        kind: 'agent-settings',
        attributes: {
          workspaceId: 'ws-1',
          provider: 'codex',
          scope: 'all',
          scopes: ['project', 'user', 'plugin'],
          collection: 'skills',
          runtimeBaseUrl: 'http://runtime.test',
        },
      },
    });
    expect(apiMock.listCodexPlugins).not.toHaveBeenCalled();
  });

  it('marks every visible scope read-only without workspace write access', () => {
    workspacePermissions.canWrite = false;

    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(settingsWorkflowPropsMock.mock.calls.at(-1)?.[0]).toMatchObject({
      readOnlyScopes: ['all', 'project', 'user', 'plugin'],
      onRefresh: undefined,
    });
  });

  it('clears the scoped backend cache before refreshing a collection', async () => {
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'refresh collection' }));

    expect(apiMock.refreshCache).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      {
        provider: 'codex',
        capability: 'skills',
        scope: 'all',
      },
    );
  });

  it('clears the OpenCode frontend collection cache without calling backend refresh', async () => {
    const removeQueries = vi.spyOn(QueryClient.prototype, 'removeQueries');
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.opencode}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'refresh collection' }));

    expect(apiMock.refreshCache).not.toHaveBeenCalled();
    expect(removeQueries).toHaveBeenCalledWith({
      queryKey: [
        'agent-settings',
        'http://runtime.test',
        'ws-1',
        'opencode',
        'skills',
        'all',
        'collection',
      ],
      exact: true,
    });
  });
});
