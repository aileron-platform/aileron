/**
 * Agent Settings module exports.
 */

// Types.
export type {
  AgentToolType,
  AgentToolConfig,
  AgentToolScopeOption,
  AgentToolMd,
  HookEventOption,
} from './types';

// Configuration constants.
export {
  AGENT_TOOL_CONFIGS,
  AGENT_NAVIGATION_IDS,
} from './agentToolConfigs';

// Utilities.
export {
  normalizeAgentType,
  getAgentToolConfig,
  isAgentToolFeature,
  getAgentTypeFromFeatureId,
  getDefaultSubView,
} from './utils';

// API factory.
export { createAgentSettingsApi } from './services/agentSettingsApi';
export type { AgentSettingsApi } from './services/agentSettingsApi';

// Shared constants.
export { SCOPE_BADGE_CLASSES } from './constants/scopeStyles';
