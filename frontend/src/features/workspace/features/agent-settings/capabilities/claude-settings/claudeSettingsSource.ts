import { claudeSettingsApi, type ClaudeSettingsScope } from './claudeSettingsApi';
import type { RawSettingsSource } from '../../model/rawSettingsSource';

const SCOPES: ClaudeSettingsScope[] = ['local', 'project', 'user'];
const EMPTY_SETTINGS_JSON = '{}';

const normalizeSettingsContent = (content: unknown): Record<string, unknown> => {
  if (!content || typeof content !== 'object' || Array.isArray(content)) return {};
  return content as Record<string, unknown>;
};

const formatSettingsJson = (content: Record<string, unknown>): string => (
  Object.keys(content).length === 0 ? EMPTY_SETTINGS_JSON : JSON.stringify(content, null, 2)
);

export const createClaudeSettingsSource = (
  runtimeBaseUrl: string,
  workspaceId: string,
): RawSettingsSource => ({
  format: 'json',
  scopes: SCOPES.map((id) => ({
    id,
    labelKey: `workspace.agentSettings.claude.settings.scopes.${id}`,
  })),
  load: async (scopeId) => {
    const response = await claudeSettingsApi.getRawSettings(
      runtimeBaseUrl,
      workspaceId,
      scopeId as ClaudeSettingsScope,
    );
    return { content: formatSettingsJson(normalizeSettingsContent(response.content)) };
  },
  save: async (scopeId, content) => {
    const parsed = JSON.parse(content) as Record<string, unknown>;
    await claudeSettingsApi.updateRawSettings(
      runtimeBaseUrl,
      workspaceId,
      scopeId as ClaudeSettingsScope,
      parsed,
    );
  },
});
