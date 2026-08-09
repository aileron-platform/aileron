import { codexSettingsApi, type CodexConfigLayer } from './codexSettingsApi';
import type { RawSettingsSource } from '../../model/rawSettingsSource';

const LAYERS: CodexConfigLayer[] = ['user', 'project'];

export const createCodexSettingsSource = (
  runtimeBaseUrl: string,
  workspaceId: string,
): RawSettingsSource => ({
  format: 'toml',
  scopes: LAYERS.map((id) => ({
    id,
    labelKey: `workspace.agentSettings.codex.settings.layers.${id}`,
  })),
  load: async (scopeId, signal) => {
    const response = await codexSettingsApi.getRawConfig(
      runtimeBaseUrl,
      workspaceId,
      scopeId as CodexConfigLayer,
      { signal },
    );
    return { content: response.content };
  },
  save: async (scopeId, content) => {
    await codexSettingsApi.updateRawConfig(runtimeBaseUrl, workspaceId, scopeId as CodexConfigLayer, content);
  },
});
