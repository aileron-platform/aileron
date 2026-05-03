import React from 'react';
import { render, screen } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AgentFileManager from './AgentFileManager';
import { AGENT_TOOL_CONFIGS } from '../agentToolConfigs';

const apiMock = {
  listCodexFiles: vi.fn(),
  listCodexPlugins: vi.fn(),
  listPluginSkills: vi.fn(),
};

const tMock = (key: string) => key;
const toggleSecondColumnMock = vi.fn();

vi.mock('../../../providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    layout: { secondColumnCollapsed: false },
    toggleSecondColumn: toggleSecondColumnMock,
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('./SettingsFileTreeWorkflow', () => ({
  SettingsFileTreeWorkflow: ({
    scopeOptions,
  }: {
    scopeOptions: Array<{ value: string; label: string }>;
  }) => (
    <div>
      {scopeOptions.map((option) => (
        <span key={option.value}>{option.label}</span>
      ))}
    </div>
  ),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('AgentFileManager Codex plugin scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [] });
  });

  it('hides plugin scope until Codex has enabled plugins', async () => {
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('workspace.agentSettings.common.skills.scope.project')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.skills.scope.plugin')).not.toBeInTheDocument();
    expect(apiMock.listCodexPlugins).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
    );
  });

  it('shows plugin scope when Codex has enabled plugins', async () => {
    apiMock.listCodexPlugins.mockResolvedValue({
      plugins: [{ id: 'demo@local', enabled: true }],
    });

    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('workspace.agentSettings.common.skills.scope.plugin')).toBeInTheDocument();
    expect(apiMock.listCodexPlugins).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
    );
  });
});
