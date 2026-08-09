import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { clearSensitiveAgentSettingsQueries } from './sensitiveAgentSettingsQueries';

describe('clearSensitiveAgentSettingsQueries', () => {
  it('removes MCP and raw settings cache while preserving general Agent Settings data', async () => {
    const queryClient = new QueryClient();
    const mcpKey = [
      'agent-settings',
      'http://runtime.test',
      'ws-1',
      'claude-code',
      'mcp',
      'all',
      'collection',
    ];
    const rawSettingsKey = [
      'raw-settings',
      'claude',
      'http://runtime.test',
      'ws-1',
      'project',
    ];
    const skillsKey = [
      'agent-settings',
      'http://runtime.test',
      'ws-1',
      'claude-code',
      'skills',
      'project',
      'collection',
    ];
    queryClient.setQueryData(mcpKey, [{ name: 'sensitive-mcp' }]);
    queryClient.setQueryData(rawSettingsKey, { content: 'sensitive-raw-settings' });
    queryClient.setQueryData(skillsKey, [{ name: 'safe-skill' }]);

    clearSensitiveAgentSettingsQueries(queryClient);

    expect(queryClient.getQueryData(mcpKey)).toBeUndefined();
    expect(queryClient.getQueryData(rawSettingsKey)).toBeUndefined();
    expect(queryClient.getQueryData(skillsKey)).toEqual([{ name: 'safe-skill' }]);
  });
});
