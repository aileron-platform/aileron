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

  it('shows plugin scope whenever Codex skills support plugins', async () => {
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('workspace.agentSettings.common.skills.scope.project')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.skills.scope.plugin')).toBeInTheDocument();
    expect(apiMock.listCodexPlugins).not.toHaveBeenCalled();
  });

  it('does not show extension scope for non-Gemini skills', async () => {
    render(
      <AgentFileManager
        config={AGENT_TOOL_CONFIGS.codex}
        collectionType="skills"
        workspaceId="ws-1"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('workspace.agentSettings.common.skills.scope.plugin')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.skills.scope.extension')).not.toBeInTheDocument();
  });
});
