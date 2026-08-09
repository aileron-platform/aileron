import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '@/shared/api/apiClient';
import { createAgentSettingsApi } from './agentSettingsApi';

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn(),
}));

const client = {
  get: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
};

describe('agentSettingsApi Codex scope contract', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ApiClient).mockReturnValue(client as never);
    client.get.mockResolvedValue({});
    client.put.mockResolvedValue({});
    client.patch.mockResolvedValue({});
    client.delete.mockResolvedValue({});
  });

  it('queries Codex files with scope', async () => {
    const api = createAgentSettingsApi();

    await api.listCodexFiles('http://runtime.test', 'workspace-1', 'prompts', 'project');
    await api.getCodexFile('http://runtime.test', 'workspace-1', 'prompts', 'plugin', 'review/SKILL.md', 'demo@local');
    await api.updateCodexFile('http://runtime.test', 'workspace-1', 'prompts', 'user', 'daily.md', '# Daily');
    await api.deleteCodexFile('http://runtime.test', 'workspace-1', 'prompts', 'user', 'daily.md');

    expect(client.get).toHaveBeenNthCalledWith(1, '/api/v1/workspaces/workspace-1/codex/prompts/files?scope=project', undefined);
    expect(client.get).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/workspace-1/codex/prompts/file?scope=plugin&path=review%2FSKILL.md&pluginId=demo%40local',
      undefined,
    );
    expect(client.put).toHaveBeenCalledWith(
      '/api/v1/workspaces/workspace-1/codex/prompts/file?scope=user',
      { path: 'daily.md', content: '# Daily' },
      undefined,
    );
    expect(client.delete).toHaveBeenCalledWith(
      '/api/v1/workspaces/workspace-1/codex/prompts/file?scope=user&path=daily.md',
      undefined,
      undefined,
    );
  });

  it('sends Codex plugin and subagent mutations with scope', async () => {
    const api = createAgentSettingsApi();

    await api.setCodexPluginEnabled('http://runtime.test', 'workspace-1', 'demo@local', 'user', false);
    await api.saveCodexSubagent('http://runtime.test', 'workspace-1', {
      scope: 'project',
      path: 'worker.toml',
      content: 'name = "worker"',
    });
    await api.deleteCodexSubagent('http://runtime.test', 'workspace-1', 'project', 'worker.toml');

    expect(client.patch).toHaveBeenCalledWith(
      '/api/v1/workspaces/workspace-1/codex/plugins/demo%40local',
      { scope: 'user', enabled: false },
      undefined,
    );
    expect(client.put).toHaveBeenCalledWith(
      '/api/v1/workspaces/workspace-1/codex/subagents',
      { scope: 'project', path: 'worker.toml', content: 'name = "worker"' },
      undefined,
    );
    expect(client.delete).toHaveBeenCalledWith(
      '/api/v1/workspaces/workspace-1/codex/subagents?scope=project&path=worker.toml',
      undefined,
      undefined,
    );
  });
});
