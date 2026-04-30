/**
 * Agent Settings utilities.
 */

import type { AgentToolType, AgentToolConfig } from './types';
import { AGENT_TOOL_CONFIGS, AGENT_NAVIGATION_IDS } from './agentToolConfigs';

/**
 * Normalize agent type names to stable keys.
 * Mirrors the CLI mapping in agentSessionTypes.ts.
 */
const normalizeAgentTypeKey = (value: string): string =>
  value.trim().toLowerCase().replace(/[\s-]+/g, '');

/**
 * Normalize a raw agent type string to AgentToolType.
 */
export const normalizeAgentType = (raw: string | null | undefined): AgentToolType => {
  if (!raw) return 'claude';
  const normalized = normalizeAgentTypeKey(raw);

  switch (normalized) {
    case 'claude':
    case 'claudecode':
      return 'claude';
    case 'codex':
      return 'codex';
    case 'gemini':
      return 'gemini';
    case 'opencode':
      return 'opencode';
    default:
      return 'claude';
  }
};

/**
 * Return the configuration for an agent tool.
 */
export const getAgentToolConfig = (agentType: AgentToolType): AgentToolConfig => {
  return AGENT_TOOL_CONFIGS[agentType];
};

/**
 * Check whether a feature id belongs to an agent tool settings feature.
 */
export const isAgentToolFeature = (featureId: string): boolean => {
  return AGENT_NAVIGATION_IDS.includes(featureId);
};

/**
 * Resolve AgentToolType from a feature id.
 */
export const getAgentTypeFromFeatureId = (featureId: string): AgentToolType | null => {
  for (const config of Object.values(AGENT_TOOL_CONFIGS)) {
    if (config.navigationId === featureId) {
      return config.id;
    }
  }
  return null;
};

/**
 * Return the default instruction-file subview for an agent tool.
 */
export const getDefaultSubView = (agentType: AgentToolType): string => {
  const config = getAgentToolConfig(agentType);
  return config.agentsMd.subViewId;
};
