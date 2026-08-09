import type { AgentSettingsToolId, AgentToolConfig } from './capabilities';
import { AGENT_TOOL_CONFIGS } from '../agentToolConfigs';

/**
 * Normalize agent type names to stable keys.
 * Mirrors the CLI mapping in agentContentTypes.ts.
 */
const normalizeAgentTypeKey = (value: string): string =>
  value.trim().toLowerCase().replace(/[\s-]+/g, '');

/**
 * Normalize a raw agent type string to AgentSettingsToolId.
 */
export const normalizeAgentType = (raw: string | null | undefined): AgentSettingsToolId => {
  if (!raw) return 'claude';
  const normalized = normalizeAgentTypeKey(raw);

  switch (normalized) {
    case 'claude':
    case 'claudecode':
      return 'claude';
    case 'codex':
      return 'codex';
    case 'opencode':
      return 'opencode';
    default:
      return 'claude';
  }
};

/**
 * Return the configuration for an agent tool.
 */
export const getAgentToolConfig = (agentType: AgentSettingsToolId): AgentToolConfig => {
  return AGENT_TOOL_CONFIGS[agentType];
};

/**
 * Resolve AgentSettingsToolId from a feature id.
 */
export const getAgentTypeFromFeatureId = (featureId: string): AgentSettingsToolId | null => {
  for (const config of Object.values(AGENT_TOOL_CONFIGS)) {
    if (config.navigationId === featureId) {
      return config.id;
    }
  }
  return null;
};
